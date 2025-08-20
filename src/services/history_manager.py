"""
History manager for DM agent message history.
Handles PydanticAI ModelMessage storage with player action filtering and dynamic summarization.
"""

from typing import List, Optional, Callable, Awaitable
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python
import json
import os
import asyncio

from ..models.formatted_game_message import FormattedGameMessage
from ..services.message_formatter import MessageFormatter
from ..memory.history_processor import HistoryConfig
from ..memory import create_summarizer, MemoryConfig, DEFAULT_MEMORY_CONFIG


class HistoryManager:
    """
    Manages message history for the DM agent using PydanticAI ModelMessage objects.
    
    Handles clean conversational message storage (using player actions only from MessageFormatter),
    implements dynamic summarization and token management similar to MessageHistoryProcessor.
    """
    
    def __init__(
        self,
        history_file: str = "message_trace/dm_history.json",
        memory_config: Optional[MemoryConfig] = None,
        summarizer_func: Optional[Callable[[List[ModelMessage]], Awaitable[List[ModelMessage]]]] = None
    ):
        """
        Initialize the history manager.
        
        Args:
            history_file: Path to store message history JSON
            memory_config: Memory configuration for token management
            summarizer_func: Optional summarizer function for dynamic summarization
        """
        self.history_file = history_file
        self.memory_config = memory_config or DEFAULT_MEMORY_CONFIG
        self.summarizer_func = summarizer_func
        
        # Initialize message formatter for player action extraction
        self.message_formatter = MessageFormatter()
        
        # History configuration for token management
        self.config = HistoryConfig(
            max_tokens=self.memory_config.max_tokens,
            min_tokens=self.memory_config.min_tokens,
            summary_file="message_trace/history_summary.json"
        )
        
        # Load existing history and summary
        self._current_history: List[ModelMessage] = self._load_history()
        self.accumulated_summary: List[ModelMessage] = self._load_summary()
        self.summary_token_count: int = self._calculate_summary_tokens()
        
        # Storage for current FormattedGameMessage objects (needed for player action extraction)
        self._current_formatted_messages: List[FormattedGameMessage] = []
        
        # Initialize summarizer if not provided but enabled
        if (self.summarizer_func is None and 
            self.memory_config.enable_memory and 
            self.memory_config.enable_summarization):
            try:
                summarizer_agent = create_summarizer(self.memory_config.summarizer_model)
                
                async def summarize_func(messages: List[ModelMessage]) -> List[ModelMessage]:
                    return await summarizer_agent.create_integrated_summary(messages)
                
                self.summarizer_func = summarize_func
            except ValueError as e:
                print(f"Warning: Could not initialize summarizer: {e}")
                self.summarizer_func = None
    
    async def get_history(self) -> List[ModelMessage]:
        """
        Get current message history with token management and summarization applied.
        
        Returns:
            List of ModelMessage objects ready for agent consumption
        """
        if not self._current_history:
            return self.accumulated_summary
        
        # Apply token management similar to MessageHistoryProcessor
        content_tokens = self.count_tokens(self._current_history) 
        effective_max, effective_min = self._get_effective_token_limits()
        
        # If content under effective max threshold, return messages as-is
        if content_tokens <= effective_max:
            return self.accumulated_summary + self._current_history
        
        # Need to trim - find cutoff point to get down to min_tokens
        messages_to_keep = []
        messages_to_summarize = []
        
        # Work backwards to find where to cut for effective min_tokens
        running_tokens = 0
        cutoff_index = len(self._current_history)
        
        for i in range(len(self._current_history) - 1, -1, -1):
            message_tokens = self.count_tokens([self._current_history[i]])
            if running_tokens + message_tokens <= effective_min:
                running_tokens += message_tokens
                cutoff_index = i
            else:
                break
        
        messages_to_keep = self._current_history[cutoff_index:]
        messages_to_summarize = self._current_history[:cutoff_index]
        
        # Summarize trimmed messages if summarizer is available
        if messages_to_summarize and self.summarizer_func:
            try:
                # Combine old summary + new messages for integrated summarization
                all_messages_to_summarize = self.accumulated_summary + messages_to_summarize
                new_summary = await self.summarizer_func(all_messages_to_summarize)
                self.accumulated_summary = new_summary
                self.summary_token_count = self._calculate_summary_tokens()
                self._save_summary()
                
                # Update current history to only keep recent messages
                self._current_history = messages_to_keep
                self._save_history()
                
            except Exception as e:
                print(f"Summarization failed: {e}")
        
        # Return summary + kept messages
        return self.accumulated_summary + messages_to_keep
    
    def get_history_sync(self) -> List[ModelMessage]:
        """Synchronous version of get_history for non-async contexts."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                print("Warning: Running in async context, returning unprocessed history")
                return self.accumulated_summary + self._current_history
            else:
                return loop.run_until_complete(self.get_history())
        except RuntimeError:
            return asyncio.run(self.get_history())
    
    def store_formatted_messages(self, messages: List[FormattedGameMessage]) -> None:
        """
        Store FormattedGameMessage objects for player action extraction after agent run.
        
        Args:
            messages: List of FormattedGameMessage objects from current turn
        """
        self._current_formatted_messages = messages
    
    
    def add_new_messages_from_result(self, new_messages: List[ModelMessage]) -> None:
        """
        Add new messages from agent result.new_messages() to history.
        Filters user messages to keep only player actions using MessageFormatter.
        
        Args:
            new_messages: New messages from agent result.new_messages()
        """
        filtered_messages = []
        #TODO: Right now, only user message and DM response are included, 
        # however, other types of messages such as tool calls and returns may be needed in future
        # for context.
        for message in new_messages:
            if isinstance(message, ModelRequest):
                # This is a user message - filter to keep only player actions
                filtered_message = self._create_player_actions_message(message)
                if filtered_message:
                    filtered_messages.append(filtered_message)
            elif isinstance(message, ModelResponse):
                # This is a DM response - extract narrative if structured
                filtered_message = self._extract_narrative_from_structured_response(message)
                filtered_messages.append(filtered_message)
        
        # Add filtered messages to history
        self._current_history.extend(filtered_messages)
        
        # Clear stored formatted messages
        self._current_formatted_messages = []
        
        # Save to file
        self._save_history()
    
    def _create_player_actions_message(self, request_message: ModelRequest) -> Optional[ModelMessage]:
        """
        Create a clean ModelRequest containing only player actions using MessageFormatter.
        
        Args:
            request_message: Original ModelRequest from agent
            
        Returns:
            Filtered ModelRequest with only player actions or None
        """
        if not self._current_formatted_messages:
            # No formatted messages stored, return original
            return request_message
        
        # Use MessageFormatter to extract player actions only
        player_actions = self.message_formatter.messages_to_history(self._current_formatted_messages)
        
        if not player_actions:
            return None
        
        # Create new UserPromptPart with player actions only
        actions_text = '\n'.join(player_actions)
        filtered_parts = [UserPromptPart(content=actions_text)]
        
        # Create new ModelRequest with filtered content
        return ModelRequest(
            parts=filtered_parts,
            kind=request_message.kind if hasattr(request_message, 'kind') else 'request'
        )
    
    def _extract_narrative_from_structured_response(self, message: ModelResponse) -> ModelResponse:
        """
        Extract narrative from DMResponse structured output in ModelResponse.
        Replaces JSON content with just the narrative field for cleaner history.
        """
        
        # Process each TextPart in the response
        modified_parts = []
        for part in message.parts:
            if isinstance(part, TextPart):
                try:
                    # Try to parse as DMResponse JSON
                    response_data = json.loads(part.content)
                    if isinstance(response_data, dict) and 'narrative' in response_data:
                        # Replace JSON with just the narrative
                        modified_part = TextPart(content=response_data['narrative'])
                        modified_parts.append(modified_part)
                    else:
                        # Not a valid DMResponse, keep original
                        modified_parts.append(part)
                except (json.JSONDecodeError, KeyError):
                    # Not JSON or missing narrative field, keep original
                    modified_parts.append(part)
            else:
                # Non-text parts, keep as-is
                modified_parts.append(part)
        
        # Create new ModelResponse with modified parts
        return ModelResponse(
            parts=modified_parts,
            usage=message.usage,
            model_name=message.model_name,
            timestamp=message.timestamp,
            vendor_details=message.vendor_details,
            vendor_id=message.vendor_id
        )
    
    def count_tokens(self, messages: List[ModelMessage]) -> int:
        """Count tokens from ModelResponse usage data with fallback estimation."""
        total_tokens = 0
        
        for message in messages:
            if isinstance(message, ModelResponse) and message.usage:
                # Use actual token counts from the model
                total_tokens += message.usage.total_tokens
            else:
                # Fallback estimation for ModelRequest or messages without usage
                total_tokens += self._estimate_tokens_from_content(message)
        
        return total_tokens
    
    def _estimate_tokens_from_content(self, message: ModelMessage) -> int:
        """Estimate tokens from message content (fallback method)."""
        total_chars = 0
        
        if hasattr(message, 'parts'):
            for part in message.parts:
                if hasattr(part, 'content') and part.content:
                    total_chars += len(str(part.content))
        
        return total_chars // 4  # Rough approximation: 4 chars per token
    
    def _get_effective_token_limits(self) -> tuple[int, int]:
        """Calculate effective token limits accounting for summary size."""
        max_summary_allowed = int(self.config.max_tokens * self.config.max_summary_ratio)
        
        # Check if summary is too large
        if self.summary_token_count > max_summary_allowed:
            print(f"Warning: Summary ({self.summary_token_count} tokens) exceeds max allowed "
                  f"({max_summary_allowed} tokens, {self.config.max_summary_ratio:.1%} of budget)")
        
        effective_max = self.config.max_tokens - self.summary_token_count
        effective_min = self.config.min_tokens - self.summary_token_count
        
        # Ensure we have at least some budget for content
        effective_max = max(effective_max, 1000)  # Always leave room for at least 1000 tokens
        effective_min = max(effective_min, 500)   # Always leave room for at least 500 tokens
        
        return effective_max, effective_min
    
    def _calculate_summary_tokens(self) -> int:
        """Calculate token count of the accumulated summary."""
        if not self.accumulated_summary:
            return 0
        
        total_tokens = 0
        for message in self.accumulated_summary:
            if isinstance(message, ModelResponse) and message.usage:
                # Use actual response tokens from the summarization
                total_tokens += message.usage.response_tokens
            else:
                # Fallback for other message types
                total_tokens += self._estimate_tokens_from_content(message)
        
        return total_tokens
    
    def _load_history(self) -> List[ModelMessage]:
        """Load message history from JSON file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'messages' in data:
                        return ModelMessagesTypeAdapter.validate_python(data['messages'])
        except Exception as e:
            print(f"Failed to load history from {self.history_file}: {e}")
        return []
    
    def _save_history(self) -> None:
        """Save current message history to JSON file."""
        try:
            if os.path.dirname(self.history_file):
                os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            messages_data = to_jsonable_python(self._current_history)
            
            try:
                loop = asyncio.get_running_loop()
                last_updated = str(loop.time())
            except RuntimeError:
                last_updated = 'sync'
            
            data = {
                'messages': messages_data,
                'message_count': len(self._current_history),
                'last_updated': last_updated
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Failed to save history to {self.history_file}: {e}")
    
    def _load_summary(self) -> List[ModelMessage]:
        """Load accumulated summary from file."""
        try:
            if os.path.exists(self.config.summary_file):
                with open(self.config.summary_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'summary_messages' in data:
                        return ModelMessagesTypeAdapter.validate_python(data['summary_messages'])
        except Exception as e:
            print(f"Failed to load summary: {e}")
        return []
    
    def _save_summary(self) -> None:
        """Save accumulated summary to file."""
        try:
            os.makedirs(os.path.dirname(self.config.summary_file), exist_ok=True)
            
            summary_data = to_jsonable_python(self.accumulated_summary)
            
            try:
                loop = asyncio.get_running_loop()
                last_updated = str(loop.time())
            except RuntimeError:
                last_updated = 'sync'
            
            data = {
                'summary_messages': summary_data,
                'summary_token_count': self.summary_token_count,
                'message_count': len(self.accumulated_summary),
                'last_updated': last_updated
            }
            
            with open(self.config.summary_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save summary: {e}")
    
    def clear_history(self) -> None:
        """Clear all history and summary."""
        self._current_history = []
        self.accumulated_summary = []
        self.summary_token_count = 0
        self._current_formatted_messages = []
        
        # Remove files
        for file_path in [self.history_file, self.config.summary_file]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Failed to remove file {file_path}: {e}")
    
    def get_stats(self) -> dict:
        """Get current history and memory statistics."""
        effective_max, effective_min = self._get_effective_token_limits()
        max_summary_allowed = int(self.config.max_tokens * self.config.max_summary_ratio)
        
        return {
            'history_message_count': len(self._current_history),
            'summary_message_count': len(self.accumulated_summary),
            'summary_token_count': self.summary_token_count,
            'max_summary_allowed': max_summary_allowed,
            'summary_ratio': self.summary_token_count / self.config.max_tokens if self.config.max_tokens > 0 else 0,
            'effective_max_tokens': effective_max,
            'effective_min_tokens': effective_min,
            'config_max_tokens': self.config.max_tokens,
            'config_min_tokens': self.config.min_tokens,
            'history_file': self.history_file,
            'summary_file': self.config.summary_file
        }


def create_history_manager(
    history_file: str = "message_trace/dm_history.json",
    memory_config: Optional[MemoryConfig] = None,
    enable_memory: bool = True
) -> HistoryManager:
    """
    Factory function to create a configured history manager.
    
    Args:
        history_file: Path to store message history JSON
        memory_config: Memory configuration for history processing
        enable_memory: Whether to enable memory management and summarization
    
    Returns:
        Configured HistoryManager instance
    """
    config = memory_config or DEFAULT_MEMORY_CONFIG
    
    if not enable_memory:
        config = MemoryConfig(enable_memory=False, enable_summarization=False)
    
    return HistoryManager(
        history_file=history_file,
        memory_config=config
    )
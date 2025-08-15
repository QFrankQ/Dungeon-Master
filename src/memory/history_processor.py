"""
Message history processor for token-based trimming and summarization.
"""

from typing import List, Optional, Callable, Awaitable
from dataclasses import dataclass
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, SystemPromptPart, ModelMessagesTypeAdapter, TextPart
from pydantic_core import to_jsonable_python
import asyncio
import json
import os

#TODO: total_tokens != request tokens + response tokens
#TODO: filter out unrelated parts when summarizing

@dataclass
class HistoryConfig:
    """Configuration for message history management."""
    max_tokens: int = 10000
    min_tokens: int = 5000
    max_summary_ratio: float = 0.3
    summary_file: str = "message_trace/conversation_summary.json"


class MessageHistoryProcessor:
    """
    Processes message history with token-based trimming and summarization.
    Implements PydanticAI's history processor pattern.
    """
    
    def __init__(
        self, 
        config: HistoryConfig,
        summarizer_func: Optional[Callable[[List[ModelMessage]], Awaitable[List[ModelMessage]]]] = None
    ):
        self.config = config
        self.summarizer_func = summarizer_func
        self.accumulated_summary: List[ModelMessage] = self._load_summary()
        self.summary_token_count: int = self._calculate_summary_tokens()
    
    #TODO: count tokens
    def _extract_narrative_from_structured_response(self, message: ModelMessage) -> ModelMessage:
        """
        Extract narrative from DMResponse structured output in ModelResponse.
        Replaces JSON content with just the narrative field for cleaner history.
        """
        if not isinstance(message, ModelResponse):
            return message
        
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
        """
        Count tokens from ModelResponse usage data.
        Falls back to character-based estimation for ModelRequest.
        """
        total_tokens = 0
        
        for message in messages:
            if isinstance(message, ModelResponse) and message.usage:
                # Use actual token counts from the model
                total_tokens += message.usage.total_tokens
            #TODO: instance of ModelRequest, confirm that the token count is accounted by the ModelResponse
            # else:
            #     # Fallback estimation for ModelRequest or messages without usage
            #     total_tokens += self._estimate_tokens_from_content(message)
        
        return total_tokens
    
    def _estimate_tokens_from_content(self, message: ModelMessage) -> int:
        """Estimate tokens from message content (fallback method)."""
        total_chars = 0
        
        if hasattr(message, 'parts'):
            for part in message.parts:
                if hasattr(part, 'content') and part.content:
                    total_chars += len(str(part.content))
        
        return total_chars // 4  # Rough approximation: 4 chars per token
    
    async def __call__(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """
        Process message history with token-based trimming.
        This is the main entry point called by PydanticAI.
        """
        if not messages:
            return self.accumulated_summary
        
        # Extract narratives from structured responses for cleaner history
        processed_messages = [self._extract_narrative_from_structured_response(msg) for msg in messages]
        
        content_tokens = self.count_tokens(processed_messages) - self.summary_token_count
        effective_max, effective_min = self._get_effective_token_limits()
        
        # If content under effective max threshold, return messages as-is
        if content_tokens <= effective_max:
            return processed_messages
        
        # Need to trim - find cutoff point to get down to min_tokens
        messages_to_keep = []
        messages_to_summarize = []
        
        # Work backwards to find where to cut for effective min_tokens
        running_tokens = 0
        cutoff_index = len(processed_messages)
        
        for i in range(len(processed_messages) - 1, -1, -1):
            message_tokens = self.count_tokens([processed_messages[i]])
            if running_tokens + message_tokens <= effective_min:
                running_tokens += message_tokens
                cutoff_index = i
            else:
                break
        
        messages_to_keep = processed_messages[cutoff_index:]
        messages_to_summarize = processed_messages[:cutoff_index]
        #TODO: work from here
        # Summarize trimmed messages if summarizer is available
        if messages_to_summarize and self.summarizer_func:
            try:
                # Combine old summary + new messages for integrated summarization
                all_messages_to_summarize = self.accumulated_summary + messages_to_summarize
                new_summary = await self.summarizer_func(all_messages_to_summarize)
                self.accumulated_summary = new_summary
                self.summary_token_count = self._calculate_summary_tokens()
                self._save_summary()
            except Exception as e:
                print(f"Summarization failed: {e}")
        
        # Return new summary + kept messages
        return self.accumulated_summary + messages_to_keep
    
    def _get_effective_token_limits(self) -> tuple[int, int]:
        """Calculate effective token limits accounting for summary size."""
        max_summary_allowed = int(self.config.max_tokens * self.config.max_summary_ratio)
        
        # Check if summary is too large #TODO: may have other ways to handle this in the future
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
        """Calculate token count of the accumulated summary using ModelResponse.usage.response_tokens."""
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
    
    def _load_summary(self) -> List[ModelMessage]:
        """Load accumulated summary from file using ModelMessagesTypeAdapter."""
        try:
            if os.path.exists(self.config.summary_file):
                with open(self.config.summary_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'summary_messages' in data:
                        # Deserialize ModelMessage objects using PydanticAI's adapter
                        return ModelMessagesTypeAdapter.validate_python(data['summary_messages'])
        except Exception as e:
            print(f"Failed to load summary: {e}")
        return []
    
    def _save_summary(self) -> None:
        """Save accumulated summary to file using to_jsonable_python."""
        try:
            os.makedirs(os.path.dirname(self.config.summary_file), exist_ok=True)
            with open(self.config.summary_file, 'w', encoding='utf-8') as f:
                # Serialize ModelMessage objects using PydanticAI's recommended approach
                summary_as_json = to_jsonable_python(self.accumulated_summary)
                
                json.dump({
                    'summary_messages': summary_as_json,
                    'summary_token_count': self.summary_token_count,
                    'message_count': len(self.accumulated_summary),
                    'last_updated': str(asyncio.get_event_loop().time())
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save summary: {e}")
    
    def clear_summary(self) -> None:
        """Clear the accumulated summary."""
        self.accumulated_summary = []
        self.summary_token_count = 0
        try:
            if os.path.exists(self.config.summary_file):
                os.remove(self.config.summary_file)
        except Exception as e:
            print(f"Failed to clear summary file: {e}")
    
    def get_memory_stats(self) -> dict:
        """Get current memory usage statistics."""
        effective_max, effective_min = self._get_effective_token_limits()
        max_summary_allowed = int(self.config.max_tokens * self.config.max_summary_ratio)
        
        return {
            "summary_token_count": self.summary_token_count,
            "summary_message_count": len(self.accumulated_summary),
            "max_summary_allowed": max_summary_allowed,
            "summary_ratio": self.summary_token_count / self.config.max_tokens if self.config.max_tokens > 0 else 0,
            "effective_max_tokens": effective_max,
            "effective_min_tokens": effective_min,
            "config_max_tokens": self.config.max_tokens,
            "config_min_tokens": self.config.min_tokens
        }


def create_history_processor(
    max_tokens: int = 10000,
    min_tokens: int = 5000,
    summarizer_func: Optional[Callable[[List[ModelMessage]], Awaitable[List[ModelMessage]]]] = None
) -> MessageHistoryProcessor:
    """Factory function to create a configured history processor."""
    config = HistoryConfig(
        max_tokens=max_tokens,
        min_tokens=min_tokens
    )
    return MessageHistoryProcessor(config, summarizer_func)
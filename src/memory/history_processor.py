"""
Message history processor for token-based trimming and summarization.
"""

from typing import List, Optional, Callable, Awaitable
from dataclasses import dataclass
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, SystemPromptPart
import asyncio
import json
import os


@dataclass
class HistoryConfig:
    """Configuration for message history management."""
    max_tokens: int = 10000
    min_tokens: int = 5000
    summary_file: str = "message_trace/conversation_summary.json"


class MessageHistoryProcessor:
    """
    Processes message history with token-based trimming and summarization.
    Implements PydanticAI's history processor pattern.
    """
    
    def __init__(
        self, 
        config: HistoryConfig,
        summarizer_func: Optional[Callable[[str, List[ModelMessage]], Awaitable[str]]] = None
    ):
        self.config = config
        self.summarizer_func = summarizer_func
        self.accumulated_summary = self._load_summary()
    
    #TODO: count tokens
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
    
    # def _estimate_tokens_from_content(self, message: ModelMessage) -> int:
    #     """Estimate tokens from message content (fallback method)."""
    #     total_chars = 0
        
    #     if hasattr(message, 'parts'):
    #         for part in message.parts:
    #             if hasattr(part, 'content') and part.content:
    #                 total_chars += len(str(part.content))
        
    #     return total_chars // 4  # Rough approximation: 4 chars per token
    
    async def __call__(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """
        Process message history with token-based trimming.
        This is the main entry point called by PydanticAI.
        """
        if not messages:
            return self._add_summary_to_messages([])
        
        current_tokens = self.count_tokens(messages)
        
        # If under max threshold, return as-is with summary
        if current_tokens <= self.config.max_tokens:
            return self._add_summary_to_messages(messages)
        
        # Need to trim - find cutoff point to get down to min_tokens
        messages_to_keep = []
        messages_to_summarize = []
        
        # Work backwards to find where to cut for min_tokens
        running_tokens = 0
        cutoff_index = len(messages)
        
        for i in range(len(messages) - 1, -1, -1):
            message_tokens = self.count_tokens([messages[i]])
            if running_tokens + message_tokens <= self.config.min_tokens:
                running_tokens += message_tokens
                cutoff_index = i
            else:
                break
        
        messages_to_keep = messages[cutoff_index:]
        messages_to_summarize = messages[:cutoff_index]
        #TODO: work from here
        # Summarize trimmed messages if summarizer is available
        if messages_to_summarize and self.summarizer_func:
            try:
                # Pass old summary + new messages for integrated summarization
                new_summary = await self.summarizer_func(
                    self.accumulated_summary, 
                    messages_to_summarize
                )
                self.accumulated_summary = new_summary
                self._save_summary()
            except Exception as e:
                print(f"Summarization failed: {e}")
        
        return self._add_summary_to_messages(messages_to_keep)
    
    def _add_summary_to_messages(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """Add the accumulated summary as a ModelRequest with SystemPromptPart."""
        if not self.accumulated_summary:
            return messages
        
        summary_message = ModelRequest(
            parts=[SystemPromptPart(
                content=f"CONVERSATION HISTORY SUMMARY:\n{self.accumulated_summary}"
            )]
        )
        
        return [summary_message] + messages
    
    def _load_summary(self) -> str:
        """Load accumulated summary from file."""
        try:
            if os.path.exists(self.config.summary_file):
                with open(self.config.summary_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('summary', '')
        except Exception as e:
            print(f"Failed to load summary: {e}")
        return ""
    
    def _save_summary(self) -> None:
        """Save accumulated summary to file."""
        try:
            os.makedirs(os.path.dirname(self.config.summary_file), exist_ok=True)
            with open(self.config.summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'summary': self.accumulated_summary,
                    'last_updated': str(asyncio.get_event_loop().time())
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save summary: {e}")
    
    def clear_summary(self) -> None:
        """Clear the accumulated summary."""
        self.accumulated_summary = ""
        try:
            if os.path.exists(self.config.summary_file):
                os.remove(self.config.summary_file)
        except Exception as e:
            print(f"Failed to clear summary file: {e}")


def create_history_processor(
    max_tokens: int = 10000,
    min_tokens: int = 5000,
    summarizer_func: Optional[Callable[[str, List[ModelMessage]], Awaitable[str]]] = None
) -> MessageHistoryProcessor:
    """Factory function to create a configured history processor."""
    config = HistoryConfig(
        max_tokens=max_tokens,
        min_tokens=min_tokens
    )
    return MessageHistoryProcessor(config, summarizer_func)
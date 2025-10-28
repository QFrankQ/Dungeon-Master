"""
Configuration settings for memory management system.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryConfig:
    """Configuration for memory management system."""
    # Token thresholds
    max_tokens: int = 10000
    min_tokens: int = 5000
    
    # Summary token management
    max_summary_ratio: float = 0.3  # Summary can take max 30% of token budget
    
    # File paths
    summary_file: str = "message_trace/conversation_summary.json"
    
    # Summarization model
    summarizer_model: str = "gemini-2.0-flash"
    
    # Enable/disable features
    enable_memory: bool = True
    enable_summarization: bool = True
    
    @classmethod
    def from_env(cls) -> 'MemoryConfig':
        """Create config from environment variables."""
        return cls(
            max_tokens=int(os.getenv('DM_MAX_TOKENS', '10000')),
            min_tokens=int(os.getenv('DM_MIN_TOKENS', '5000')),
            max_summary_ratio=float(os.getenv('DM_MAX_SUMMARY_RATIO', '0.3')),
            summary_file=os.getenv('DM_SUMMARY_FILE', 'message_trace/conversation_summary.json'),
            summarizer_model=os.getenv('DM_SUMMARIZER_MODEL', 'gemini-2.0-flash'),
            enable_memory=os.getenv('DM_ENABLE_MEMORY', 'true').lower() == 'true',
            enable_summarization=os.getenv('DM_ENABLE_SUMMARIZATION', 'true').lower() == 'true'
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.min_tokens >= self.max_tokens:
            raise ValueError(f"min_tokens ({self.min_tokens}) must be less than max_tokens ({self.max_tokens})")
        
        if self.min_tokens <= 0 or self.max_tokens <= 0:
            raise ValueError("Token limits must be positive")


# Default configuration
DEFAULT_MEMORY_CONFIG = MemoryConfig()
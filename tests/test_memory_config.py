"""
Tests for memory configuration management.
"""

import pytest
import os
from memory.config import MemoryConfig, DEFAULT_MEMORY_CONFIG


class TestMemoryConfig:
    """Test cases for MemoryConfig class."""
    
    def test_default_config_values(self):
        """Test that default configuration has expected values."""
        config = MemoryConfig()
        
        assert config.max_tokens == 10000
        assert config.min_tokens == 5000
        assert config.max_summary_ratio == 0.3
        assert config.summary_file == "message_trace/conversation_summary.json"
        assert config.summarizer_model == "gemini-2.0-flash"
        assert config.enable_memory is True
        assert config.enable_summarization is True
    
    def test_custom_config_values(self):
        """Test creating config with custom values."""
        config = MemoryConfig(
            max_tokens=8000,
            min_tokens=4000,
            max_summary_ratio=0.4,
            summary_file="custom/path.json",
            summarizer_model="gemini-2.0",
            enable_memory=False,
            enable_summarization=False
        )
        
        assert config.max_tokens == 8000
        assert config.min_tokens == 4000
        assert config.max_summary_ratio == 0.4
        assert config.summary_file == "custom/path.json"
        assert config.summarizer_model == "gemini-2.0"
        assert config.enable_memory is False
        assert config.enable_summarization is False
    
    def test_config_validation_success(self):
        """Test that valid configurations pass validation."""
        config = MemoryConfig(max_tokens=1000, min_tokens=500)
        config.validate()  # Should not raise
    
    def test_config_validation_min_greater_than_max(self):
        """Test that min_tokens >= max_tokens raises ValueError."""
        config = MemoryConfig(max_tokens=500, min_tokens=1000)
        
        with pytest.raises(ValueError, match="min_tokens .* must be less than max_tokens"):
            config.validate()
    
    def test_config_validation_min_equal_max(self):
        """Test that min_tokens == max_tokens raises ValueError."""
        config = MemoryConfig(max_tokens=500, min_tokens=500)
        
        with pytest.raises(ValueError, match="min_tokens .* must be less than max_tokens"):
            config.validate()
    
    def test_config_validation_negative_tokens(self):
        """Test that negative token values raise ValueError."""
        config = MemoryConfig(max_tokens=-100, min_tokens=50)
        
        with pytest.raises(ValueError, match="min_tokens .* must be less than max_tokens"):
            config.validate()
        
        config = MemoryConfig(max_tokens=100, min_tokens=-50)
        
        with pytest.raises(ValueError, match="Token limits must be positive"):
            config.validate()
    
    def test_config_validation_zero_tokens(self):
        """Test that zero token values raise ValueError."""
        config = MemoryConfig(max_tokens=0, min_tokens=50)
        
        with pytest.raises(ValueError, match="min_tokens .* must be less than max_tokens"):
            config.validate()
        
        config = MemoryConfig(max_tokens=100, min_tokens=0)
        
        with pytest.raises(ValueError, match="Token limits must be positive"):
            config.validate()


class TestMemoryConfigFromEnv:
    """Test cases for loading configuration from environment variables."""
    
    def test_from_env_default_values(self, env_vars):
        """Test from_env with no environment variables set."""
        # Ensure no relevant env vars are set
        env_vars()
        
        config = MemoryConfig.from_env()
        
        assert config.max_tokens == 10000
        assert config.min_tokens == 5000
        assert config.max_summary_ratio == 0.3
        assert config.summary_file == "message_trace/conversation_summary.json"
        assert config.summarizer_model == "gemini-2.0-flash"
        assert config.enable_memory is True
        assert config.enable_summarization is True
    
    def test_from_env_custom_values(self, env_vars):
        """Test from_env with custom environment variables."""
        env_vars(
            DM_MAX_TOKENS=8000,
            DM_MIN_TOKENS=4000,
            DM_MAX_SUMMARY_RATIO=0.4,
            DM_SUMMARY_FILE="custom/summary.json",
            DM_SUMMARIZER_MODEL="gemini-2.0-flash",
            DM_ENABLE_MEMORY="false",
            DM_ENABLE_SUMMARIZATION="false"
        )
        
        config = MemoryConfig.from_env()
        
        assert config.max_tokens == 8000
        assert config.min_tokens == 4000
        assert config.max_summary_ratio == 0.4
        assert config.summary_file == "custom/summary.json"
        assert config.summarizer_model == "gemini-2.0-flash"
        assert config.enable_memory is False
        assert config.enable_summarization is False
    
    def test_from_env_boolean_parsing(self, env_vars):
        """Test that boolean environment variables are parsed correctly."""
        # Test various true values
        env_vars(DM_ENABLE_MEMORY="true", DM_ENABLE_SUMMARIZATION="TRUE")
        config = MemoryConfig.from_env()
        assert config.enable_memory is True
        assert config.enable_summarization is True
        
        # Test various false values
        env_vars(DM_ENABLE_MEMORY="false", DM_ENABLE_SUMMARIZATION="FALSE")
        config = MemoryConfig.from_env()
        assert config.enable_memory is False
        assert config.enable_summarization is False
        
        # Test other values (should be false)
        env_vars(DM_ENABLE_MEMORY="yes", DM_ENABLE_SUMMARIZATION="no")
        config = MemoryConfig.from_env()
        assert config.enable_memory is False
        assert config.enable_summarization is False
    
    def test_from_env_numeric_parsing(self, env_vars):
        """Test that numeric environment variables are parsed correctly."""
        env_vars(
            DM_MAX_TOKENS="12000",
            DM_MIN_TOKENS="6000", 
            DM_MAX_SUMMARY_RATIO="0.25"
        )
        
        config = MemoryConfig.from_env()
        
        assert config.max_tokens == 12000
        assert config.min_tokens == 6000
        assert config.max_summary_ratio == 0.25


class TestDefaultMemoryConfig:
    """Test the default memory configuration constant."""
    
    def test_default_config_instance(self):
        """Test that DEFAULT_MEMORY_CONFIG is properly initialized."""
        assert isinstance(DEFAULT_MEMORY_CONFIG, MemoryConfig)
        assert DEFAULT_MEMORY_CONFIG.max_tokens == 10000
        assert DEFAULT_MEMORY_CONFIG.min_tokens == 5000
        assert DEFAULT_MEMORY_CONFIG.enable_memory is True
        assert DEFAULT_MEMORY_CONFIG.enable_summarization is True
    
    def test_default_config_validation(self):
        """Test that the default config is valid."""
        DEFAULT_MEMORY_CONFIG.validate()  # Should not raise
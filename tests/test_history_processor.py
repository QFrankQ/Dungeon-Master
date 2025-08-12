"""
Tests for message history processor component.
"""

import pytest
import json
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch, mock_open
from memory.history_processor import MessageHistoryProcessor, HistoryConfig, create_history_processor
from memory.config import MemoryConfig


class TestHistoryConfig:
    """Test cases for HistoryConfig dataclass."""
    
    def test_default_config(self):
        """Test default HistoryConfig values."""
        config = HistoryConfig()
        
        assert config.max_tokens == 10000
        assert config.min_tokens == 5000
        assert config.summary_file == "message_trace/conversation_summary.json"
    
    def test_custom_config(self):
        """Test HistoryConfig with custom values."""
        config = HistoryConfig(
            max_tokens=8000,
            min_tokens=4000,
            summary_file="custom/path.json"
        )
        
        assert config.max_tokens == 8000
        assert config.min_tokens == 4000
        assert config.summary_file == "custom/path.json"


class TestMessageHistoryProcessor:
    """Test cases for MessageHistoryProcessor class."""
    
    @pytest.fixture
    def history_config(self, temp_summary_file):
        """Create test history configuration."""
        return HistoryConfig(
            max_tokens=1000,
            min_tokens=500,
            summary_file=temp_summary_file
        )
    
    @pytest.fixture
    def processor_without_summarizer(self, history_config):
        """Create processor without summarizer function."""
        return MessageHistoryProcessor(history_config, summarizer_func=None)
    
    @pytest.fixture
    def processor_with_summarizer(self, history_config, mock_summarizer_func):
        """Create processor with mock summarizer function."""
        return MessageHistoryProcessor(history_config, summarizer_func=mock_summarizer_func)
    
    def test_init_without_summarizer(self, history_config):
        """Test initialization without summarizer function."""
        processor = MessageHistoryProcessor(history_config, summarizer_func=None)
        
        assert processor.config == history_config
        assert processor.summarizer_func is None
        assert processor.accumulated_summary == []
        assert processor.summary_token_count == 0
    
    def test_init_with_summarizer(self, history_config, mock_summarizer_func):
        """Test initialization with summarizer function."""
        processor = MessageHistoryProcessor(history_config, summarizer_func=mock_summarizer_func)
        
        assert processor.config == history_config
        assert processor.summarizer_func == mock_summarizer_func
        assert processor.accumulated_summary == []
        assert processor.summary_token_count == 0
    
    def test_count_tokens_with_model_responses(self, processor_without_summarizer, mock_model_response, mock_usage):
        """Test token counting with ModelResponse objects that have usage data."""
        usage1 = mock_usage(request_tokens=20, response_tokens=30, total_tokens=50)
        usage2 = mock_usage(request_tokens=40, response_tokens=60, total_tokens=100)
        
        messages = [
            mock_model_response("Response 1", usage1),
            mock_model_response("Response 2", usage2)
        ]
        
        total_tokens = processor_without_summarizer.count_tokens(messages)
        assert total_tokens == 150  # 50 + 100
    
    def test_count_tokens_mixed_messages(self, processor_without_summarizer, mock_model_request, mock_model_response, mock_usage):
        """Test token counting with mixed message types."""
        usage = mock_usage(request_tokens=30, response_tokens=70, total_tokens=100)
        
        messages = [
            mock_model_request("User message"),  # No usage data
            mock_model_response("Assistant response", usage)  # Has usage data
        ]
        
        total_tokens = processor_without_summarizer.count_tokens(messages)
        # Only the ModelResponse with usage should contribute to count
        assert total_tokens == 100
    
    def test_count_tokens_empty_list(self, processor_without_summarizer):
        """Test token counting with empty message list."""
        total_tokens = processor_without_summarizer.count_tokens([])
        assert total_tokens == 0
    
    def test_estimate_tokens_from_content(self, processor_without_summarizer):
        """Test fallback token estimation from content."""
        # Create mock message with content
        mock_message = Mock()
        mock_part = Mock()
        mock_part.content = "A" * 100  # 100 characters
        mock_message.parts = [mock_part]
        
        estimated = processor_without_summarizer._estimate_tokens_from_content(mock_message)
        assert estimated == 25  # 100 / 4 = 25 tokens
    
    @pytest.mark.asyncio
    async def test_call_with_empty_messages(self, processor_without_summarizer):
        """Test processor with empty message list."""
        result = await processor_without_summarizer([])
        assert result == []  # Should return accumulated summary (empty)
    
    @pytest.mark.asyncio
    async def test_call_under_token_limit(self, processor_without_summarizer, sample_conversation):
        """Test processor when messages are under token limit."""
        # Mock count_tokens to return value under max_tokens
        with patch.object(processor_without_summarizer, 'count_tokens', return_value=500):
            result = await processor_without_summarizer(sample_conversation)
            
            # Should return messages as-is since under limit
            assert result == sample_conversation
    
    @pytest.mark.asyncio
    async def test_call_over_token_limit_no_summarizer(self, processor_without_summarizer, sample_conversation):
        """Test processor when over token limit but no summarizer available."""
        # Mock count_tokens to return value over max_tokens
        with patch.object(processor_without_summarizer, 'count_tokens') as mock_count:
            # First call (total) returns high value, subsequent calls return smaller values
            mock_count.side_effect = [1500, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
            
            result = await processor_without_summarizer(sample_conversation)
            
            # Should return trimmed messages (no summarization)
            assert len(result) < len(sample_conversation)
    
    @pytest.mark.asyncio
    async def test_call_over_token_limit_with_summarizer(self, processor_with_summarizer, sample_conversation):
        """Test processor when over token limit with summarizer available."""
        with patch.object(processor_with_summarizer, 'count_tokens') as mock_count:
            # First call (total) returns high value, subsequent calls return smaller values
            mock_count.side_effect = [1500, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
            
            result = await processor_with_summarizer(sample_conversation)
            
            # Should return summary + kept messages
            assert len(result) > 0
            # Verify summarizer was called
            assert processor_with_summarizer.accumulated_summary is not None
    
    @pytest.mark.asyncio
    async def test_call_summarization_error(self, processor_with_summarizer, sample_conversation):
        """Test handling of summarization errors."""
        # Mock summarizer to raise exception
        async def failing_summarizer(messages):
            raise Exception("Summarization failed")
        
        processor_with_summarizer.summarizer_func = failing_summarizer
        
        with patch.object(processor_with_summarizer, 'count_tokens') as mock_count, \
             patch('builtins.print') as mock_print:
            
            mock_count.side_effect = [1500, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
            
            result = await processor_with_summarizer(sample_conversation)
            
            # Should handle error gracefully
            assert len(result) > 0
            mock_print.assert_called_once_with("Summarization failed: Summarization failed")
    
    def test_get_effective_token_limits_normal(self, processor_without_summarizer):
        """Test effective token limit calculations."""
        # Use larger token limits to avoid minimum budget enforcement
        processor_without_summarizer.config.max_tokens = 5000
        processor_without_summarizer.config.min_tokens = 2000
        processor_without_summarizer.config.max_summary_ratio = 0.3
        processor_without_summarizer.summary_token_count = 100
        
        effective_max, effective_min = processor_without_summarizer._get_effective_token_limits()
        
        assert effective_max == 4900  # 5000 - 100
        assert effective_min == 1900   # 2000 - 100
    
    def test_get_effective_token_limits_minimum_budget(self, processor_without_summarizer):
        """Test that minimum token budget is enforced."""
        # Mock config to include max_summary_ratio
        processor_without_summarizer.config.max_summary_ratio = 0.3
        processor_without_summarizer.summary_token_count = 950  # Very high summary
        
        effective_max, effective_min = processor_without_summarizer._get_effective_token_limits()
        
        # Should enforce minimum budgets
        assert effective_max == 1000  # At least 1000 tokens
        assert effective_min == 500   # At least 500 tokens
    
    def test_calculate_summary_tokens(self, processor_without_summarizer, mock_model_response, mock_usage):
        """Test summary token calculation."""
        usage1 = mock_usage(response_tokens=50)
        usage2 = mock_usage(response_tokens=75)
        
        processor_without_summarizer.accumulated_summary = [
            mock_model_response("Summary 1", usage1),
            mock_model_response("Summary 2", usage2)
        ]
        
        total = processor_without_summarizer._calculate_summary_tokens()
        assert total == 125  # 50 + 75 response tokens
    
    def test_load_summary_file_not_exists(self, processor_without_summarizer):
        """Test loading summary when file doesn't exist."""
        # File doesn't exist, should return empty list
        result = processor_without_summarizer._load_summary()
        assert result == []
    
    def test_load_summary_success(self, processor_without_summarizer, sample_summary_file_content):
        """Test successful summary loading."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(sample_summary_file_content))), \
             patch('memory.history_processor.ModelMessagesTypeAdapter') as mock_adapter:
            
            mock_messages = [Mock(), Mock()]
            mock_adapter.validate_python.return_value = mock_messages
            
            result = processor_without_summarizer._load_summary()
            
            assert result == mock_messages
            mock_adapter.validate_python.assert_called_once_with(
                sample_summary_file_content['summary_messages']
            )
    
    def test_load_summary_error(self, processor_without_summarizer):
        """Test summary loading with file error."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("File error")), \
             patch('builtins.print') as mock_print:
            
            result = processor_without_summarizer._load_summary()
            
            assert result == []
            mock_print.assert_called_once_with("Failed to load summary: File error")
    
    def test_save_summary_success(self, processor_without_summarizer, mock_model_response, mock_usage):
        """Test successful summary saving."""
        usage = mock_usage(response_tokens=50)
        processor_without_summarizer.accumulated_summary = [mock_model_response("Summary", usage)]
        processor_without_summarizer.summary_token_count = 50
        
        with patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('memory.history_processor.to_jsonable_python') as mock_to_json, \
             patch('asyncio.get_event_loop') as mock_loop:
            
            mock_to_json.return_value = [{"content": "Summary", "kind": "response"}]
            mock_loop.return_value.time.return_value = 1234567890.0
            
            processor_without_summarizer._save_summary()
            
            mock_makedirs.assert_called_once()
            mock_file.assert_called_once()
            mock_json_dump.assert_called_once()
    
    def test_save_summary_error(self, processor_without_summarizer):
        """Test summary saving with file error."""
        processor_without_summarizer.accumulated_summary = [Mock()]
        
        with patch('os.makedirs', side_effect=OSError("Permission denied")), \
             patch('builtins.print') as mock_print:
            
            processor_without_summarizer._save_summary()
            
            mock_print.assert_called_once_with("Failed to save summary: Permission denied")
    
    def test_clear_summary(self, processor_without_summarizer, temp_summary_file):
        """Test clearing accumulated summary."""
        # Set up some summary data
        processor_without_summarizer.accumulated_summary = [Mock(), Mock()]
        processor_without_summarizer.summary_token_count = 100
        
        # Create the file
        with open(temp_summary_file, 'w') as f:
            f.write('{"test": "data"}')
        
        processor_without_summarizer.clear_summary()
        
        assert processor_without_summarizer.accumulated_summary == []
        assert processor_without_summarizer.summary_token_count == 0
        assert not os.path.exists(temp_summary_file)
    
    def test_clear_summary_file_error(self, processor_without_summarizer):
        """Test clearing summary with file deletion error."""
        processor_without_summarizer.accumulated_summary = [Mock()]
        
        with patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("Permission denied")), \
             patch('builtins.print') as mock_print:
            
            processor_without_summarizer.clear_summary()
            
            # Should clear memory even if file deletion fails
            assert processor_without_summarizer.accumulated_summary == []
            assert processor_without_summarizer.summary_token_count == 0
            mock_print.assert_called_once_with("Failed to clear summary file: Permission denied")
    
    def test_get_memory_stats(self, processor_without_summarizer):
        """Test memory statistics generation."""
        processor_without_summarizer.config.max_summary_ratio = 0.3
        processor_without_summarizer.accumulated_summary = [Mock(), Mock()]
        processor_without_summarizer.summary_token_count = 300
        
        stats = processor_without_summarizer.get_memory_stats()
        
        assert stats["summary_token_count"] == 300
        assert stats["summary_message_count"] == 2
        assert stats["max_summary_allowed"] == 300  # 1000 * 0.3
        assert stats["summary_ratio"] == 0.3  # 300 / 1000
        assert stats["effective_max_tokens"] == 1000  # At least 1000 (due to minimum)
        assert stats["effective_min_tokens"] == 500   # At least 500 (due to minimum)
        assert stats["config_max_tokens"] == 1000
        assert stats["config_min_tokens"] == 500


class TestCreateHistoryProcessor:
    """Test cases for create_history_processor factory function."""
    
    def test_create_with_defaults(self):
        """Test factory function with default parameters."""
        processor = create_history_processor()
        
        assert processor.config.max_tokens == 10000
        assert processor.config.min_tokens == 5000
        assert processor.summarizer_func is None
    
    def test_create_with_custom_params(self, mock_summarizer_func):
        """Test factory function with custom parameters."""
        processor = create_history_processor(
            max_tokens=8000,
            min_tokens=4000,
            summarizer_func=mock_summarizer_func
        )
        
        assert processor.config.max_tokens == 8000
        assert processor.config.min_tokens == 4000
        assert processor.summarizer_func == mock_summarizer_func
    
    def test_create_returns_processor_instance(self):
        """Test that factory function returns MessageHistoryProcessor instance."""
        processor = create_history_processor()
        assert isinstance(processor, MessageHistoryProcessor)
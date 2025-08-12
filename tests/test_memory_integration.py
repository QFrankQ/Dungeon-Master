"""
Integration tests for memory system components working together.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, AsyncMock, patch
from memory.config import MemoryConfig
from memory.summarizer import ConversationSummarizer
from memory.history_processor import MessageHistoryProcessor


class TestMemorySystemIntegration:
    """Integration tests for the complete memory system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def integration_config(self, temp_dir):
        """Create integration test configuration."""
        return MemoryConfig(
            max_tokens=2000,
            min_tokens=1000,
            max_summary_ratio=0.3,
            summary_file=os.path.join(temp_dir, "test_summary.json"),
            enable_memory=True,
            enable_summarization=True
        )
    
    @pytest.fixture
    def mock_summarizer_for_integration(self, mock_model_response, mock_usage):
        """Create mock summarizer that produces realistic summaries."""
        async def mock_create_summary(messages):
            if not messages:
                return []
            
            # Create a realistic D&D summary
            summary_content = f"The party of {len(messages)//2} members continued their adventure, facing various challenges and making progress on their quest."
            
            # Use proper ModelResponse instead of Mock
            usage = mock_usage(response_tokens=25, request_tokens=100, total_tokens=125)
            return [mock_model_response(summary_content, usage)]
        
        mock_summarizer = Mock()
        mock_summarizer.create_integrated_summary = AsyncMock(side_effect=mock_create_summary)
        return mock_summarizer
    
    @pytest.mark.asyncio
    async def test_end_to_end_memory_workflow(self, integration_config, mock_summarizer_for_integration, 
                                            mock_model_request, mock_model_response, mock_usage):
        """Test complete memory workflow from messages to summarization to persistence."""
        
        # Create summarizer function that uses the mock
        async def summarizer_func(messages):
            return await mock_summarizer_for_integration.create_integrated_summary(messages)
        
        # Create history processor with summarizer
        processor = MessageHistoryProcessor(integration_config, summarizer_func)
        
        # Create a long conversation that exceeds token limits
        long_conversation = []
        for i in range(10):
            # Each pair should be ~300 tokens based on our mock usage
            usage = mock_usage(request_tokens=50, response_tokens=100, total_tokens=150)
            long_conversation.extend([
                mock_model_request(f"User message {i}: What should we do next in the dungeon?"),
                mock_model_response(f"DM response {i}: You see a corridor leading deeper into the ancient ruins.", usage)
            ])
        
        # Mock count_tokens to simulate high token usage
        with patch.object(processor, 'count_tokens') as mock_count:
            # Total tokens exceed limit, individual messages are reasonable
            mock_count.side_effect = [3000] + [150] * 20  # First call total, then per message
            
            # Process the conversation
            result = await processor(long_conversation)
            
            # Verify summarization occurred
            assert len(processor.accumulated_summary) > 0
            assert processor.summary_token_count > 0
            
            # Verify result contains summary + recent messages
            assert len(result) > 0
            assert len(result) < len(long_conversation)
            
            # Verify summarizer was called
            mock_summarizer_for_integration.create_integrated_summary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(self, integration_config, mock_summarizer_for_integration,
                                                    mock_model_request, mock_model_response, mock_usage):
        """Test that memory persists across different processor instances."""
        
        # Create summarizer function
        async def summarizer_func(messages):
            return await mock_summarizer_for_integration.create_integrated_summary(messages)
        
        # First session - create summary
        processor1 = MessageHistoryProcessor(integration_config, summarizer_func)
        
        initial_conversation = [
            mock_model_request("We explore the first room"),
            mock_model_response("You find a treasure chest", mock_usage(total_tokens=200))
        ]
        
        # Force summarization by mocking high token count
        # First call: total tokens (2500) > effective_max (2000)
        # Subsequent calls: individual message tokens (1200 > effective_min 1000)
        with patch.object(processor1, 'count_tokens', side_effect=[2500, 1200, 1200]):
            await processor1(initial_conversation)
        
        # Verify summary was created and saved
        assert len(processor1.accumulated_summary) > 0
        assert os.path.exists(integration_config.summary_file)
        
        # Second session - load existing summary
        processor2 = MessageHistoryProcessor(integration_config, summarizer_func)
        
        # Should load the existing summary
        assert len(processor2.accumulated_summary) > 0
        assert processor2.summary_token_count > 0
        
        # Add more conversation
        new_conversation = [
            mock_model_request("We continue to the next room"),
            mock_model_response("You encounter a group of goblins", mock_usage(total_tokens=150))
        ]
        
        # Process complete history (as agent framework would do)
        complete_history = processor2.accumulated_summary + new_conversation
        with patch.object(processor2, 'count_tokens', return_value=300):  # Under limit
            result = await processor2(complete_history)
            
            # Should return complete history since under limit
            assert len(result) == len(complete_history)
    
    @pytest.mark.asyncio
    async def test_config_integration_with_components(self, temp_dir):
        """Test that MemoryConfig integrates properly with other components."""
        
        # Create config with specific settings
        config = MemoryConfig(
            max_tokens=1500,
            min_tokens=750,
            max_summary_ratio=0.4,
            summary_file=os.path.join(temp_dir, "config_test.json"),
            summarizer_model="test-model"
        )
        
        # Validate config
        config.validate()  # Should not raise
        
        # Use config with history processor
        processor = MessageHistoryProcessor(config, summarizer_func=None)
        
        assert processor.config.max_tokens == 1500
        assert processor.config.min_tokens == 750
        assert processor.config.summary_file.endswith("config_test.json")
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_integration(self, integration_config, mock_model_request, mock_model_response, mock_usage):
        """Test that the system handles errors gracefully in integrated scenarios."""
        
        # Create failing summarizer
        async def failing_summarizer(messages):
            raise Exception("API is down")
        
        processor = MessageHistoryProcessor(integration_config, failing_summarizer)
        
        conversation = [
            mock_model_request("Test message"),
            mock_model_response("Test response", mock_usage(total_tokens=2500))
        ]
        
        # Force trimming but summarization will fail
        # Use simpler token counts to ensure trimming logic works
        with patch.object(processor, 'count_tokens', side_effect=[3000, 800, 400]), \
            patch('builtins.print') as mock_print:
            
            result = await processor(conversation)
            
            # Should still return kept messages despite summarization failure
            # Algorithm works backwards: message[1] (400) + message[0] (800) = 1200 > 1000
            # So keeps only message[1] (400 tokens)
            assert len(result) == 1  
            mock_print.assert_called_with("Summarization failed: API is down")
    
    def test_memory_stats_integration(self, integration_config, mock_model_response, mock_usage):
        """Test memory statistics in integrated scenario."""
        processor = MessageHistoryProcessor(integration_config, summarizer_func=None)
        
        # Add some summary data
        summary_message = mock_model_response("Summary", mock_usage(response_tokens=100))
        processor.accumulated_summary = [summary_message]
        processor.summary_token_count = 100
        
        stats = processor.get_memory_stats()
        
        # Verify calculations based on integration_config
        assert stats["summary_token_count"] == 100
        assert stats["summary_message_count"] == 1
        assert stats["max_summary_allowed"] == 600  # 2000 * 0.3
        assert stats["summary_ratio"] == 0.05  # 100 / 2000
        assert stats["config_max_tokens"] == 2000
        assert stats["config_min_tokens"] == 1000
    
    @pytest.mark.asyncio
    async def test_realistic_dnd_scenario(self, integration_config, mock_model_request, mock_model_response, mock_usage):
        """Test with realistic D&D conversation patterns."""
        
        # Create realistic D&D summarizer
        async def dnd_summarizer(messages):
            summary_parts = [
                "The adventuring party explored the ancient temple,",
                "discovered magical artifacts, and defeated several monsters.",
                "They are currently investigating mysterious runes on the wall."
            ]
            summary_content = " ".join(summary_parts)
            
            # Use proper ModelResponse instead of Mock
            usage = mock_usage(response_tokens=30, request_tokens=200, total_tokens=230)
            return [mock_model_response(summary_content, usage)]
        
        processor = MessageHistoryProcessor(integration_config, dnd_summarizer)
        
        # Create realistic D&D conversation
        dnd_conversation = [
            mock_model_request("I want to examine the altar for traps"),
            mock_model_response("Roll a Perception check", mock_usage(total_tokens=50)),
            mock_model_request("I rolled a 18 total"),
            mock_model_response("You notice a hidden pressure plate. The altar appears to be trapped with a poison dart mechanism.", mock_usage(total_tokens=80)),
            mock_model_request("I'll try to disarm the trap using my thieves' tools"),
            mock_model_response("Roll a Sleight of Hand check with advantage due to your expertise", mock_usage(total_tokens=70)),
            mock_model_request("I rolled 22 total with advantage"),
            mock_model_response("Success! You carefully disarm the mechanism. The altar is now safe to examine.", mock_usage(total_tokens=75)),
        ]
        
        # Process conversation (should stay under limit)
        with patch.object(processor, 'count_tokens', return_value=300):  # Under limit
            result = await processor(dnd_conversation)
            
            # Should return all messages since under limit
            assert len(result) == len(dnd_conversation)
        
        # Add more conversation to trigger summarization
        more_conversation = dnd_conversation + [
            mock_model_request("What do I find on the altar?"),
            mock_model_response("You discover an ancient tome and a mysterious crystal orb glowing with inner light.", mock_usage(total_tokens=90)),
        ]
        
        # Force summarization  
        # Total tokens (2500) > effective_max (2000), so trimming occurs
        # Individual messages: most are 800 tokens each, last 2 are 200 tokens each
        # This should keep last 2 messages (400 total < effective_min 1000)
        with patch.object(processor, 'count_tokens', side_effect=[2500] + [800] * 8 + [200, 200]):
            result = await processor(more_conversation)
            
            # Should have summary + recent messages
            assert len(processor.accumulated_summary) > 0
            assert "ancient temple" in processor.accumulated_summary[0].parts[0].content
            assert len(result) > len(processor.accumulated_summary)
            assert len(result) < len(more_conversation)
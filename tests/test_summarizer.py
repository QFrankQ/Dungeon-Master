"""
Tests for conversation summarizer component.
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch
from memory.summarizer import ConversationSummarizer, create_summarizer


class TestConversationSummarizer:
    """Test cases for ConversationSummarizer class."""
    
    @pytest.fixture
    def mock_gemini_env(self, monkeypatch):
        """Set up environment with mock Gemini API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-12345")
    
    def test_init_with_default_model(self, mock_gemini_env):
        """Test initializing summarizer with default model."""
        with patch('memory.summarizer.GeminiModel') as mock_model, \
             patch('memory.summarizer.GoogleGLAProvider') as mock_provider, \
             patch('memory.summarizer.Agent') as mock_agent:
            
            summarizer = ConversationSummarizer()
            
            mock_model.assert_called_once_with(
                "gemini-2.0-flash",
                provider=mock_provider.return_value
            )
            mock_agent.assert_called_once()
            
    def test_init_with_custom_model(self, mock_gemini_env):
        """Test initializing summarizer with custom model."""
        with patch('memory.summarizer.GeminiModel') as mock_model, \
             patch('memory.summarizer.GoogleGLAProvider') as mock_provider, \
             patch('memory.summarizer.Agent') as mock_agent:
            
            summarizer = ConversationSummarizer("gemini-2.0-flash")
            
            mock_model.assert_called_once_with(
                "gemini-2.0-flash",
                provider=mock_provider.return_value
            )
    
    def test_init_missing_api_key(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        # Remove the API key from environment
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is required"):
            ConversationSummarizer()
    
    def test_get_summarizer_prompt(self, mock_gemini_env):
        """Test that summarizer prompt contains expected elements."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            summarizer = ConversationSummarizer()
            prompt = summarizer._get_summarizer_prompt()
            
            # Check that prompt contains key elements
            assert "D&D game session" in prompt
            assert "Dungeon Master" in prompt
            assert "narrative continuity" in prompt
            assert "character states" in prompt
            assert "combat results" in prompt
            assert "integrated summary" in prompt
            assert "chronological flow" in prompt
    
    @pytest.mark.asyncio
    async def test_create_integrated_summary_success(self, mock_gemini_env, sample_conversation):
        """Test successful summary creation."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            # Setup mock agent response
            mock_result = Mock()
            mock_result.new_messages.return_value = [
                Mock(parts=[Mock(content="Integrated summary of the conversation")])
            ]
            mock_agent.return_value.run = AsyncMock(return_value=mock_result)
            
            summarizer = ConversationSummarizer()
            result = await summarizer.create_integrated_summary(sample_conversation)
            
            assert len(result) == 1
            assert result[0].parts[0].content == "Integrated summary of the conversation"
            
            # Verify agent.run was called with message_history
            mock_agent.return_value.run.assert_called_once_with(message_history=sample_conversation)
    
    @pytest.mark.asyncio
    async def test_create_integrated_summary_empty_messages(self, mock_gemini_env):
        """Test summary creation with empty message list."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent'):
            
            summarizer = ConversationSummarizer()
            result = await summarizer.create_integrated_summary([])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_create_integrated_summary_api_error(self, mock_gemini_env, sample_conversation):
        """Test handling of API errors during summarization."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            # Setup mock agent to raise exception
            mock_agent.return_value.run = AsyncMock(side_effect=Exception("API Error"))
            
            summarizer = ConversationSummarizer()
            
            # Should capture the exception and print error message
            with patch('builtins.print') as mock_print:
                result = await summarizer.create_integrated_summary(sample_conversation)
                
                assert result == []
                mock_print.assert_called_once_with("Summarization error: API Error")
    
    @pytest.mark.asyncio
    async def test_create_integrated_summary_network_error(self, mock_gemini_env, sample_conversation):
        """Test handling of network errors during summarization."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            # Setup mock agent to raise network exception
            mock_agent.return_value.run = AsyncMock(side_effect=ConnectionError("Network unavailable"))
            
            summarizer = ConversationSummarizer()
            
            with patch('builtins.print') as mock_print:
                result = await summarizer.create_integrated_summary(sample_conversation)
                
                assert result == []
                mock_print.assert_called_once_with("Summarization error: Network unavailable")
    
    @pytest.mark.asyncio 
    async def test_create_integrated_summary_malformed_response(self, mock_gemini_env, sample_conversation):
        """Test handling of malformed API responses."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            # Setup mock agent with malformed response
            mock_result = Mock()
            mock_result.new_messages.side_effect = AttributeError("Malformed response")
            mock_agent.return_value.run = AsyncMock(return_value=mock_result)
            
            summarizer = ConversationSummarizer()
            
            with patch('builtins.print') as mock_print:
                result = await summarizer.create_integrated_summary(sample_conversation)
                
                assert result == []
                mock_print.assert_called_once_with("Summarization error: Malformed response")


class TestCreateSummarizerFactory:
    """Test cases for create_summarizer factory function."""
    
    @pytest.fixture
    def mock_gemini_env(self, monkeypatch):
        """Set up environment with mock Gemini API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-12345")
    
    def test_create_summarizer_default_model(self, mock_gemini_env):
        """Test factory function with default model."""
        with patch('memory.summarizer.ConversationSummarizer') as mock_class:
            result = create_summarizer()
            
            mock_class.assert_called_once_with("gemini-2.0-flash")
            assert result == mock_class.return_value
    
    def test_create_summarizer_custom_model(self, mock_gemini_env):
        """Test factory function with custom model."""
        with patch('memory.summarizer.ConversationSummarizer') as mock_class:
            result = create_summarizer("gemini-2.0-flash")
            
            mock_class.assert_called_once_with("gemini-2.0-flash")
            assert result == mock_class.return_value
    
    def test_create_summarizer_propagates_errors(self, monkeypatch):
        """Test that factory function propagates initialization errors."""
        # Remove API key to trigger error
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is required"):
            create_summarizer()


class TestSummarizerIntegration:
    """Integration tests for summarizer with mock external dependencies."""
    
    @pytest.fixture
    def mock_gemini_env(self, monkeypatch):
        """Set up environment with mock Gemini API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-12345")
    
    @pytest.mark.asyncio
    async def test_summarizer_with_realistic_conversation(self, mock_gemini_env):
        """Test summarizer with a realistic D&D conversation."""
        with patch('memory.summarizer.GeminiModel'), \
             patch('memory.summarizer.GoogleGLAProvider'), \
             patch('memory.summarizer.Agent') as mock_agent:
            
            # Create realistic D&D conversation messages
            dnd_messages = [
                Mock(parts=[Mock(content="You enter the ancient dungeon")]),
                Mock(parts=[Mock(content="I search for traps")]),
                Mock(parts=[Mock(content="Roll a perception check")]),
                Mock(parts=[Mock(content="I rolled 15")]),
                Mock(parts=[Mock(content="You notice a pressure plate. Combat begins! Roll initiative.")])
            ]
            
            # Setup mock response with D&D-style summary
            mock_result = Mock()
            expected_summary = "The party entered an ancient dungeon and discovered traps through a successful perception check (15). Combat has begun with initiative being rolled."
            mock_result.new_messages.return_value = [
                Mock(parts=[Mock(content=expected_summary)])
            ]
            mock_agent.return_value.run = AsyncMock(return_value=mock_result)
            
            summarizer = ConversationSummarizer()
            result = await summarizer.create_integrated_summary(dnd_messages)
            
            assert len(result) == 1
            assert result[0].parts[0].content == expected_summary
            
            # Verify the agent was called with correct message history
            mock_agent.return_value.run.assert_called_once_with(message_history=dnd_messages)
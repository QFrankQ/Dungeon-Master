"""
Test configuration and fixtures for memory component tests.
"""

import pytest
import tempfile
import os
from typing import List
from unittest.mock import Mock, AsyncMock

# Import memory components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart, Usage
from memory.config import MemoryConfig


@pytest.fixture
def temp_summary_file():
    """Create a temporary file for testing summary persistence."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def memory_config(temp_summary_file):
    """Create a test memory configuration."""
    return MemoryConfig(
        max_tokens=1000,
        min_tokens=500,
        max_summary_ratio=0.3,
        summary_file=temp_summary_file,
        summarizer_model="gemini-1.5-flash",
        enable_memory=True,
        enable_summarization=True
    )


@pytest.fixture
def mock_usage():
    """Create a mock Usage object for testing."""
    def create_usage(request_tokens=50, response_tokens=100, total_tokens=150):
        return Usage(
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens
        )
    return create_usage


@pytest.fixture
def mock_model_request():
    """Create a mock ModelRequest for testing."""
    def create_request(content="Test user message"):
        return ModelRequest(parts=[UserPromptPart(content=content)])
    return create_request


@pytest.fixture
def mock_model_response():
    """Create a mock ModelResponse for testing."""
    def create_response(content="Test assistant response", usage=None):
        if usage is None:
            usage = Usage(request_tokens=50, response_tokens=100, total_tokens=150)
        return ModelResponse(parts=[TextPart(content=content)], usage=usage)
    return create_response


@pytest.fixture
def sample_conversation(mock_model_request, mock_model_response, mock_usage):
    """Create a sample conversation for testing."""
    messages = []
    
    # Add alternating user/assistant messages
    for i in range(5):
        # User message
        messages.append(mock_model_request(f"User message {i+1}"))
        # Assistant response
        usage = mock_usage(request_tokens=20+i*5, response_tokens=40+i*10, total_tokens=60+i*15)
        messages.append(mock_model_response(f"Assistant response {i+1}", usage))
    
    return messages


@pytest.fixture
def mock_gemini_agent():
    """Create a mock Gemini agent for testing summarization."""
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.new_messages.return_value = [
        Mock(parts=[Mock(content="Mock summary of conversation")])
    ]
    mock_agent.run = AsyncMock(return_value=mock_result)
    return mock_agent


@pytest.fixture
def mock_summarizer_func(mock_model_response):
    """Create a mock summarizer function for testing."""
    async def mock_summarize(messages: List[ModelMessage]) -> List[ModelMessage]:
        # Return a mock summary message
        summary_content = f"Summary of {len(messages)} messages"
        usage = Usage(request_tokens=100, response_tokens=50, total_tokens=150)
        return [mock_model_response(summary_content, usage)]
    
    return mock_summarize


@pytest.fixture
def sample_summary_file_content():
    """Sample JSON content for testing summary file operations."""
    return {
        "summary_messages": [
            {
                "parts": [{"content": "Previous conversation summary", "part_kind": "text"}],
                "usage": {"request_tokens": 50, "response_tokens": 100, "total_tokens": 150},
                "kind": "response"
            }
        ],
        "summary_token_count": 100,
        "message_count": 1,
        "last_updated": "1234567890.0"
    }


@pytest.fixture
def env_vars():
    """Fixture for testing environment variable configuration."""
    original_env = os.environ.copy()
    
    def set_env(**kwargs):
        for key, value in kwargs.items():
            os.environ[key] = str(value)
    
    def restore_env():
        os.environ.clear()
        os.environ.update(original_env)
    
    yield set_env
    restore_env()


class MockConversationSummarizer:
    """Mock conversation summarizer for testing."""
    
    def __init__(self, model_name="mock-model"):
        self.model_name = model_name
        self.agent = Mock()
    
    async def create_integrated_summary(self, messages_to_summarize):
        """Mock summary creation."""
        if not messages_to_summarize:
            return []
        
        # Create a mock summary response
        summary_text = f"Mock summary of {len(messages_to_summarize)} messages"
        mock_response = Mock()
        mock_response.parts = [Mock(content=summary_text)]
        mock_response.usage = Usage(request_tokens=50, response_tokens=25, total_tokens=75)
        
        return [mock_response]


@pytest.fixture
def mock_conversation_summarizer():
    """Fixture providing a mock conversation summarizer."""
    return MockConversationSummarizer()
"""
Summarization agent for creating integrated conversation summaries.
"""

from typing import List, Optional
from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.messages import ModelMessage
import os


class ConversationSummarizer:
    """
    A dedicated agent for creating integrated conversation summaries.
    Uses a smaller model for cost efficiency.
    """
    
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        """Initialize with a cost-effective model for summarization."""
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        model = GeminiModel(
            model_name, 
            provider=GoogleGLAProvider(api_key=gemini_api_key)
        )
        
        self.agent = Agent(
            model,
            name="Conversation Summarizer",
            instructions=self._get_summarizer_prompt()
        )
    
    def _get_summarizer_prompt(self) -> str:
        """System prompt for the summarization agent."""
        return """
        You are a conversation summarizer for a D&D game session. Your job is to create 
        integrated, coherent summaries that preserve important context for the Dungeon Master.
        
        Key requirements:
        1. Maintain narrative continuity and story elements
        2. Preserve important character states, locations, and plot points
        3. Keep track of combat results, treasure found, and quest progress
        4. Note important NPC interactions and world developments
        5. Integrate new information with existing summary context
        
        When given an existing summary and new messages:
        - Build upon the existing summary rather than replacing it
        - Identify and integrate new developments 
        - Remove outdated information only when directly contradicted
        - Maintain chronological flow
        - Keep the summary concise but comprehensive
        
        Output only the integrated summary, no additional commentary.
        """
    
    async def create_integrated_summary(
        self, 
        messages_to_summarize: List[ModelMessage]
    ) -> List[ModelMessage]:
        """
        Create an integrated summary from messages.
        
        Args:
            messages_to_summarize: Combined list of old summary + new messages to process
            
        Returns:
            List of ModelMessages containing the integrated summary from new_messages()
        """
        if not messages_to_summarize:
            return []
        
        try:
            # Use PydanticAI pattern: run with message_history, no user prompt
            summary_result = await self.agent.run(message_history=messages_to_summarize)
            return summary_result.new_messages()
        except Exception as e:
            print(f"Summarization error: {e}")
            # Fallback: return empty if summarization fails  
            return []
    


def create_summarizer(model_name: str = "gemini-1.5-flash") -> ConversationSummarizer:
    """Factory function to create a conversation summarizer."""
    return ConversationSummarizer(model_name)
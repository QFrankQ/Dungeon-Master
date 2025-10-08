"""Event detection agent that identifies what types of state changes occurred."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider

from ..models.state_updates import EventDetectionResult
from .prompts import EVENT_DETECTOR_INSTRUCTIONS


class EventDetectorAgent:
    """Lightweight agent that detects which types of state changes occurred."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Initialize the event detector agent."""
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.model = GeminiModel(
            model_name, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        self.agent = Agent(
            model=self.model,
            name="Event Detector",
            instructions=EVENT_DETECTOR_INSTRUCTIONS,
            output_type=EventDetectionResult
        )

    async def detect_events(
        self,
        formatted_turn_context: str,
        game_context: Optional[dict] = None
    ) -> EventDetectionResult:
        """
        Detect which types of state changes occurred in turn context.

        Args:
            formatted_turn_context: XML-formatted turn context with messages
            game_context: Optional additional context

        Returns:
            EventDetectionResult indicating which event types were detected
        """
        try:
            prompt = self._prepare_prompt(formatted_turn_context, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            # Return empty detection on failure
            return EventDetectionResult(
                detected_events=[],
                confidence=0.0,
                reasoning=f"Detection failed: {str(e)}"
            )

    def _prepare_prompt(self, turn_context: str, game_context: Optional[dict] = None) -> str:
        """Prepare detection prompt."""
        sections = [
            "Analyze the following turn context and detect what types of state changes occurred:",
            "",
            "TURN CONTEXT:",
            turn_context,
            ""
        ]

        if game_context:
            sections.extend([
                "GAME CONTEXT:",
                f"Turn: {game_context.get('turn_id', 'N/A')}",
                f"Active Character: {game_context.get('active_character', 'N/A')}",
                ""
            ])

        sections.extend([
            "Detect which event types occurred:",
            "- COMBAT_STATE_CHANGE: HP changes, conditions, death saves, combat stat modifiers",
            "- RESOURCE_USAGE: Spell casting, item usage, inventory changes, hit dice, ability changes",
            "",
            "Return detected event types. Be permissive - better to detect both than miss one."
        ])

        return "\n".join(sections)


def create_event_detector(model_name: str = "gemini-2.5-flash-lite") -> EventDetectorAgent:
    """Factory function to create event detector agent."""
    return EventDetectorAgent(model_name=model_name)

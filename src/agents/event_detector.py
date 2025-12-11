"""Event detection agent that identifies what types of state changes occurred."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()
from ..models.state_updates import EventDetectionResult
from .prompts import EVENT_DETECTOR_INSTRUCTIONS


class EventDetectorAgent:
    """Lightweight agent that detects which types of state changes occurred."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Initialize the event detector agent."""
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
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
            "- HP_CHANGE: HP damage, healing, temporary HP",
            "- EFFECT_APPLIED: Conditions (poisoned, stunned, etc.), buffs, debuffs, spell effects",
            "- RESOURCE_USAGE: Spell slot usage, item consumption, hit dice usage",
            "- STATE_CHANGE: Death saving throws, rest (short/long)",
            "",
            "Return detected event types. Be permissive - better to detect multiple than miss one."
        ])

        return "\n".join(sections)


def create_event_detector(model_name: str = "gemini-2.5-flash-lite") -> EventDetectorAgent:
    """Factory function to create event detector agent."""
    return EventDetectorAgent(model_name=model_name)

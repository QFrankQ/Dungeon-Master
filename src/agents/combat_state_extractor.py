"""Combat state extraction agent focused on HP, conditions, death saves, combat stats."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider

from ..models.state_updates import CombatStateResult
from .prompts import COMBAT_STATE_EXTRACTOR_INSTRUCTIONS


class CombatStateExtractor:
    """Specialized extractor for combat-critical state changes only."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Initialize the combat state extractor."""
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.model = GeminiModel(
            model_name, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        self.agent = Agent(
            model=self.model,
            name="Combat State Extractor",
            instructions=COMBAT_STATE_EXTRACTOR_INSTRUCTIONS,
            output_type=CombatStateResult
        )

    async def extract(
        self,
        formatted_turn_context: str,
        game_context: Optional[dict] = None
    ) -> CombatStateResult:
        """
        Extract combat-critical state changes.

        Focuses on: HP, conditions, death saves, combat stat modifiers.

        Args:
            formatted_turn_context: XML-formatted turn context
            game_context: Optional additional context

        Returns:
            CombatStateResult with extracted combat state changes
        """
        try:
            prompt = self._prepare_prompt(formatted_turn_context, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return CombatStateResult(
                character_updates=[],
                combat_info={},
                notes=f"Combat extraction failed: {str(e)}"
            )

    def _prepare_prompt(self, turn_context: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract combat-critical state changes from the turn context:",
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
            "Extract ONLY these types of changes:",
            "- HP changes (damage, healing, temporary HP)",
            "- Condition changes (added/removed conditions)",
            "- Death saving throws (successes/failures)",
            "- Combat stat modifiers (AC, speed, initiative bonuses)",
            "",
            "Return structured CombatStateResult."
        ])

        return "\n".join(sections)


def create_combat_state_extractor(model_name: str = "gemini-2.5-flash-lite") -> CombatStateExtractor:
    """Factory function to create combat state extractor."""
    return CombatStateExtractor(model_name=model_name)

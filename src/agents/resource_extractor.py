"""Resource extraction agent for spell slots, inventory, items, hit dice, abilities."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()
from ..models.state_updates import ResourceResult
from .prompts import RESOURCE_EXTRACTOR_INSTRUCTIONS


class ResourceExtractor:
    """Specialized extractor for resource consumption and character changes."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Initialize the resource extractor."""
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
        )
        self.agent = Agent(
            model=self.model,
            name="Resource Extractor",
            instructions=RESOURCE_EXTRACTOR_INSTRUCTIONS,
            output_type=ResourceResult
        )

    async def extract(
        self,
        formatted_turn_context: str,
        game_context: Optional[dict] = None
    ) -> ResourceResult:
        """
        Extract resource consumption and character changes.

        Focuses on: Spell slots, inventory, items, hit dice, abilities, new characters.

        Args:
            formatted_turn_context: XML-formatted turn context
            game_context: Optional additional context

        Returns:
            ResourceResult with extracted resource changes
        """
        try:
            prompt = self._prepare_prompt(formatted_turn_context, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return ResourceResult(
                character_updates=[],
                new_characters=[],
                notes=f"Resource extraction failed: {str(e)}"
            )

    def _prepare_prompt(self, turn_context: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract resource consumption and character changes from the turn context:",
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
            "- Spell slot usage (spell casting, slot recovery)",
            "- Inventory changes (items gained/lost/used)",
            "- Item updates (equipment changes)",
            "- Hit dice usage (short rest healing)",
            "- Ability score changes (temporary or permanent)",
            "- New characters (NPCs, monsters, summons introduced)",
            "",
            "Return structured ResourceResult."
        ])

        return "\n".join(sections)


def create_resource_extractor(model_name: str = "gemini-2.5-flash-lite") -> ResourceExtractor:
    """Factory function to create resource extractor."""
    return ResourceExtractor(model_name=model_name)

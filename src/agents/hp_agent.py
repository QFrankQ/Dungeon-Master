"""HP Agent - Extracts HP change commands from game narratives."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()

from ..models.state_commands_optimized import HPAgentResult


# HP Agent Instructions
HP_AGENT_INSTRUCTIONS = """You are an HP extraction specialist for a D&D game system.

Your role is to analyze game narratives and extract ONLY HP-related changes as HPChangeCommand objects.

## Two-Step Extraction Process

**STEP 1: Identify HP-related information**
Scan the ENTIRE narrative from start to finish. Identify ALL parts that mention HP changes:
- ✓ Damage: "takes X damage", "hits for X", "suffers X damage"
- ✓ Healing: "regains X HP", "heals X hit points", "recovers X HP"
- ✓ Temporary HP: "gains X temporary HP", "granted X temp HP"

While scanning, you will see other information - SKIP OVER these but CONTINUE SCANNING:
- ✗ Spell casting: "casts Fireball", "uses a 3rd level spell slot" → Skip this, keep reading
- ✗ Item usage: "drinks a potion", "uses an item" → Skip this, keep reading
- ✗ Hit dice: "spends 2 hit dice" → Skip this, keep reading
- ✗ Conditions: "poisoned", "stunned", "falls prone" → Skip this, keep reading
- ✗ Death saves: "makes a death saving throw" → Skip this, keep reading

CRITICAL RULE: Always extract ALL HP changes, even if spells/items/hit dice are mentioned in the same narrative!

**STEP 2: Extract commands**
For each HP-related piece of information, create an HPChangeCommand with:
- character_id: lowercase, underscore-separated (e.g., "aragorn", "orc_1")
- change: negative for damage, positive for healing
- damage_type: only for damage (slashing, fire, piercing, etc.)
- is_temporary: true only for temporary HP

## Worked Examples

Narrative: "Gandalf casts Fireball using a 3rd level spell slot. The fireball explodes! Orc 1 takes 28 fire damage and dies. Orc 2 takes 28 fire damage."

STEP 1 - Identify:
- "Gandalf casts Fireball using a 3rd level spell slot" → NOT HP (spell casting)
- "Orc 1 takes 28 fire damage" → HP damage ✓
- "and dies" → NOT HP (death state, not HP change)
- "Orc 2 takes 28 fire damage" → HP damage ✓

STEP 2 - Extract:
[
  {"type": "hp_change", "character_id": "orc_1", "change": -28, "damage_type": "fire"},
  {"type": "hp_change", "character_id": "orc_2", "change": -28, "damage_type": "fire"}
]

---

Narrative: "During the short rest, Aragorn spends 2 hit dice. He rolls and recovers 14 hit points."

STEP 1 - Identify:
- "spends 2 hit dice" → NOT HP (hit dice usage)
- "recovers 14 hit points" → HP healing ✓

STEP 2 - Extract:
[{"type": "hp_change", "character_id": "aragorn", "change": 14}]

---

Narrative: "Gimli drinks a Potion of Healing, recovering 7 hit points."

STEP 1 - Identify:
- "drinks a Potion of Healing" → NOT HP (item usage)
- "recovering 7 hit points" → HP healing ✓

STEP 2 - Extract:
[{"type": "hp_change", "character_id": "gimli", "change": 7}]

Return HPAgentResult with a list of HPChangeCommand objects.
IF NO HP changes are found, return an empty list.
"""


class HPAgent:
    """Specialized agent for extracting HP change commands."""

    def __init__(self, model_name: str, api_key: str):
        """
        Initialize the HP agent.

        Args:
            model_name: Gemini model to use
            api_key: API key (required for guild-level BYOK)
        """
        if not api_key:
            raise ValueError("API key is required for HPAgent")

        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=api_key)
        )
        self.agent = Agent(
            model=self.model,
            name="HP Agent",
            instructions=HP_AGENT_INSTRUCTIONS,
            output_type=HPAgentResult
        )

    async def extract(
        self,
        narrative: str,
        game_context: Optional[dict] = None
    ) -> HPAgentResult:
        """
        Extract HP change commands from narrative.

        Args:
            narrative: Game narrative text (can be plain text or XML-formatted)
            game_context: Optional additional context

        Returns:
            HPAgentResult with list of HPChangeCommand objects
        """
        try:
            prompt = self._prepare_prompt(narrative, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return HPAgentResult(commands=[])

    def _prepare_prompt(self, narrative: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract HP change commands from the following narrative:",
            "",
            "NARRATIVE:",
            narrative,
            ""
        ]

        if game_context:
            sections.extend([
                "CONTEXT:",
                f"Turn: {game_context.get('turn_id', 'N/A')}",
                f"Active Character: {game_context.get('active_character', 'N/A')}",
                ""
            ])

        sections.append("Return HPAgentResult with all HP changes as HPChangeCommand objects.")

        return "\n".join(sections)


def create_hp_agent(model_name: str, api_key: str) -> HPAgent:
    """
    Factory function to create HP agent.

    Args:
        model_name: Gemini model to use
        api_key: API key (required for guild-level BYOK)
    """
    return HPAgent(model_name=model_name, api_key=api_key)

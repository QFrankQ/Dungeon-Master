"""Resource Agent - Extracts resource usage commands (spell slots, hit dice, items)."""

from typing import Optional
import os
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()

from ..models.state_commands_optimized import ResourceAgentResult


# Resource Agent Instructions
RESOURCE_AGENT_INSTRUCTIONS = """You are a resource extraction specialist for a D&D game system.

Your role is to analyze game narratives and extract ONLY resource-related changes as command objects.

## Two-Step Extraction Process

**STEP 1: Identify resource-related information**
First, scan the narrative and identify which parts mention resource usage:
- Spell slots: "casts X spell", "uses a 3rd level spell slot", "regains spell slots"
- Hit dice: "spends X hit dice", "uses hit dice", "regains X hit dice"
- Items: "drinks a potion", "uses an item", "finds 50 gold", "loses his rope"

Ignore these (NOT resource-related):
- HP changes: "takes 28 damage", "recovers 14 hit points", "heals for 7 HP"
- Conditions: "poisoned", "stunned", "falls prone"
- Death saves: "makes a death saving throw"
- Rest itself: "takes a long rest" (extract hit dice usage DURING rest, not the rest itself)

**STEP 2: Extract commands**
For each resource-related piece of information, create the appropriate command:

**SpellSlotCommand** (spell casting):
- character_id, action="use", level (1-9), spell_name

**HitDiceCommand** (hit dice usage):
- character_id, action="use" or "restore", count

**ItemCommand** (item interactions):
- character_id, action="use"/"add"/"remove", item_name, quantity

## Worked Examples

Narrative: "Gandalf casts Fireball using a 3rd level spell slot. The fireball explodes! Orc 1 takes 28 fire damage."

STEP 1 - Identify:
- "Gandalf casts Fireball using a 3rd level spell slot" → Spell slot usage ✓
- "Orc 1 takes 28 fire damage" → NOT resource (HP damage)

STEP 2 - Extract:
[{"type": "spell_slot", "character_id": "gandalf", "action": "use", "level": 3, "spell_name": "Fireball"}]

---

Narrative: "During the short rest, Aragorn spends 2 hit dice. He rolls and recovers 14 hit points."

STEP 1 - Identify:
- "During the short rest" → NOT resource (rest event, no extraction needed)
- "spends 2 hit dice" → Hit dice usage ✓
- "recovers 14 hit points" → NOT resource (HP healing)

STEP 2 - Extract:
[{"type": "hit_dice", "character_id": "aragorn", "action": "use", "count": 2}]

---

Narrative: "Gimli drinks a Potion of Healing, recovering 7 hit points."

STEP 1 - Identify:
- "drinks a Potion of Healing" → Item usage ✓
- "recovering 7 hit points" → NOT resource (HP healing)

STEP 2 - Extract:
[{"type": "item", "character_id": "gimli", "action": "use", "item_name": "Potion of Healing"}]

Return ResourceAgentResult with a list of command objects.
If no resource changes are found, return an empty list.
"""


class ResourceAgent:
    """Specialized agent for extracting resource usage commands."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Initialize the resource agent."""
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
        )
        self.agent = Agent(
            model=self.model,
            name="Resource Agent",
            instructions=RESOURCE_AGENT_INSTRUCTIONS,
            output_type=ResourceAgentResult
        )

    async def extract(
        self,
        narrative: str,
        game_context: Optional[dict] = None
    ) -> ResourceAgentResult:
        """
        Extract resource usage commands from narrative.

        Args:
            narrative: Game narrative text (can be plain text or XML-formatted)
            game_context: Optional additional context

        Returns:
            ResourceAgentResult with list of command objects
        """
        try:
            prompt = self._prepare_prompt(narrative, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return ResourceAgentResult(commands=[])

    def _prepare_prompt(self, narrative: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract resource usage commands from the following narrative:",
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

        sections.append("Return ResourceAgentResult with all resource changes as command objects.")

        return "\n".join(sections)


def create_resource_agent(model_name: str = "gemini-2.5-flash-lite") -> ResourceAgent:
    """Factory function to create resource agent."""
    return ResourceAgent(model_name=model_name)

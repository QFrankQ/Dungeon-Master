"""Lifecycle Agent - Extracts death save and rest commands from game narratives."""

from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from ..models.state_commands_optimized import StateAgentResult


# Lifecycle Agent Instructions (agent formally called "StateAgent", renamed to "LifecycleAgent" for clarity)
LIFECYCLE_AGENT_INSTRUCTIONS = """You are a character lifecycle event specialist for a D&D game system.

Your role is to analyze game narratives and extract ONLY lifecycle-related changes as DeathSaveCommand and RestCommand objects.

## Two-Step Extraction Process

**STEP 1: Identify lifecycle-related information**
Scan the ENTIRE narrative from start to finish. Identify ALL parts that mention lifecycle events:
- ✓ Death saves: "makes a death saving throw", "rolls a death save", "succeeds on death save", "fails death save"
- ✓ Stabilization: "becomes stable", "stabilized", "death saves reset"
- ✓ Rest events: "takes a short rest", "takes a long rest", "the party rests"

While scanning, you will see other information - SKIP OVER these but CONTINUE SCANNING:
- ✗ HP healing: "regains 10 HP", "heals 5 hit points" → Skip this, keep reading
- ✗ Spell slot restoration: "regains spell slots" → Skip this, keep reading
- ✗ Condition removal: "no longer poisoned" → Skip this, keep reading
- ✗ Hit dice: "spends 2 hit dice" → Skip this, keep reading

CRITICAL RULE: Extract ONLY death saves and rests. HP recovery, spell slot restoration, and condition removal during rests are handled by other specialized agents.

**STEP 2: Extract commands**
For each lifecycle event, create the appropriate command:

**DeathSaveCommand:**
- character_id: lowercase, underscore-separated (e.g., "aragorn", "legolas")
- result: "success", "failure", or "reset"
- count: number of successes/failures (default 1)

**RestCommand:**
- character_id: lowercase, underscore-separated (or "party" for group rests)
- rest_type: "short" or "long"

## Worked Examples

Narrative: "Legolas, unconscious on the ground, makes a death saving throw. He rolls a 12 - that's a success! He now has 1 successful death save."

STEP 1 - Identify:
- "makes a death saving throw" → Death save ✓
- "rolls a 12 - that's a success" → Death save success ✓

STEP 2 - Extract:
[{"type": "death_save", "character_id": "legolas", "result": "success", "count": 1}]

---

Narrative: "Gimli rolls a natural 1 on his death save. That's an automatic failure - he now has 2 failed death saves."

STEP 1 - Identify:
- "rolls a natural 1 on his death save" → Death save ✓
- "automatic failure" → Death save failure ✓

STEP 2 - Extract:
[{"type": "death_save", "character_id": "gimli", "result": "failure", "count": 1}]

---

Narrative: "The cleric casts Healing Word on Aragorn, restoring 5 hit points. Aragorn is conscious again and his death saves reset."

STEP 1 - Identify:
- "restoring 5 hit points" → NOT lifecycle (HP healing)
- "death saves reset" → Death save reset ✓

STEP 2 - Extract:
[{"type": "death_save", "character_id": "aragorn", "result": "reset", "count": 1}]

---

Narrative: "The party takes a short rest. During the rest, Aragorn spends 2 hit dice and recovers 14 hit points."

STEP 1 - Identify:
- "takes a short rest" → Rest event ✓
- "spends 2 hit dice" → NOT lifecycle (hit dice usage)
- "recovers 14 hit points" → NOT lifecycle (HP healing)

STEP 2 - Extract:
[{"type": "rest", "character_id": "party", "rest_type": "short"}]

---

Narrative: "After defeating the goblins, the party takes a long rest to recover their strength and spell slots."

STEP 1 - Identify:
- "takes a long rest" → Rest event ✓
- "recover their strength and spell slots" → NOT lifecycle (handled by other agents)

STEP 2 - Extract:
[{"type": "rest", "character_id": "party", "rest_type": "long"}]

Return StateAgentResult with a list of DeathSaveCommand and/or RestCommand objects.
IF NO lifecycle events are found, return an empty list.
"""


class LifecycleAgent:
    """Specialized agent for extracting lifecycle event commands."""

    def __init__(self, model_name: str, api_key: str):
        """
        Initialize the lifecycle agent.

        Args:
            model_name: Gemini model to use
            api_key: API key (required for guild-level BYOK)
        """
        if not api_key:
            raise ValueError("API key is required for LifecycleAgent")

        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=api_key)
        )
        self.agent = Agent(
            model=self.model,
            name="Lifecycle Agent",
            instructions=LIFECYCLE_AGENT_INSTRUCTIONS,
            output_type=StateAgentResult
        )

    async def extract(
        self,
        narrative: str,
        game_context: Optional[dict] = None
    ) -> StateAgentResult:
        """
        Extract lifecycle event commands from narrative.

        Args:
            narrative: Game narrative text (can be plain text or XML-formatted)
            game_context: Optional additional context

        Returns:
            StateAgentResult with list of DeathSaveCommand and/or RestCommand objects
        """
        try:
            prompt = self._prepare_prompt(narrative, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return StateAgentResult(commands=[])

    def _prepare_prompt(self, narrative: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract lifecycle event commands from the following narrative:",
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

        sections.append("Return StateAgentResult with all lifecycle events as DeathSaveCommand and/or RestCommand objects.")

        return "\n".join(sections)


def create_lifecycle_agent(model_name: str, api_key: str) -> LifecycleAgent:
    """
    Factory function to create lifecycle agent.

    Args:
        model_name: Gemini model to use
        api_key: API key (required for guild-level BYOK)
    """
    return LifecycleAgent(model_name=model_name, api_key=api_key)

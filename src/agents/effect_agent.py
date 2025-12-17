"""Effect Agent - Extracts effect and condition commands from game narratives."""

from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from ..models.state_commands_optimized import EffectAgentResult


# Effect Agent Instructions
EFFECT_AGENT_INSTRUCTIONS = """You are an Effect extraction specialist for a D&D game system.

Your role is to analyze game narratives and extract ONLY effect-related changes:
- **Conditions** (Poisoned, Stunned, Blinded, etc.) → ConditionCommand
- **Effects** (Bless, Haste, Hunter's Mark, etc.) → EffectCommand

## CONDITIONS vs EFFECTS

**Use ConditionCommand for official D&D 5e conditions:**
- Blinded, Charmed, Deafened, Exhaustion, Frightened
- Grappled, Incapacitated, Invisible, Paralyzed, Petrified
- Poisoned, Prone, Restrained, Stunned, Unconscious

**Use EffectCommand for everything else:**
- Spell buffs: Bless, Haste, Heroism, Guidance, Bardic Inspiration
- Spell debuffs: Bane, Slow, Hex, Hunter's Mark
- Ongoing spell effects: Shield, Fire Resistance, Stoneskin
- Class features: Rage, Sneak Attack bonus
- Custom effects: Any effect that's not an official condition

## DESCRIPTION GENERATION RULES

**For Standard D&D Effects (Bless, Haste, Shield, etc.):**
✓ ALWAYS use complete D&D Rules as Written (RAW) mechanics
✓ Fill in ALL mechanics even if DM only mentions part of it
✓ Example: DM says "grants +1d4 to attacks" → Description is "Whenever you make an attack roll or saving throw, you can roll a d4 and add it to the result"
✓ Example: DM says "you're blessed" → Generate full Bless description
✓ EXCEPTION: If DM explicitly contradicts RAW, use DM's custom version
✓ Example: DM says "Bless but only for attacks, not saves" → Use DM's version only

**For Custom/Homebrew Effects:**
✓ Extract exactly what DM describes
✓ Don't invent additional mechanics beyond what DM stated
✓ Example: "The dragon's aura grants fire resistance" → Use exact DM text

**Detection Rule:**
- If effect name matches a standard D&D spell or feature → Fill in complete RAW mechanics
- If effect description seems custom or unique → Use DM's exact text only

## FIELD GUIDELINES

**EffectCommand Fields:**
- effect_name: Name of the effect (capitalize properly: "Bless", "Haste", not "bless")
- description: 1-2 sentences describing what the effect does mechanically
- summary: Complete but concise summary of all mechanical effects (can be longer if needed)
- duration_type: "concentration", "rounds", "minutes", "hours", "until_long_rest", "until_short_rest", "permanent"
- duration: Numeric value (default 10 for concentration, 1 for rounds if not specified)
- effect_type: "buff", "debuff", "spell", or "condition"
- action: "add" or "remove"

**ConditionCommand Fields:**
- condition: Use the Condition enum (POISONED, STUNNED, etc.)
- duration_type: Same as above
- duration: Numeric value
- action: "add" or "remove"

## CHARACTER ID FORMAT
- Always lowercase
- Use underscores for spaces: "aragorn", "orc_1", "evil_wizard"
- Extract from narrative context

## DURATION EXTRACTION
- "for 1 minute" → duration_type="minutes", duration=1
- "while concentrating" or "concentration" → duration_type="concentration", duration=10
- "until long rest" → duration_type="until_long_rest", duration=1
- "until short rest" → duration_type="until_short_rest", duration=1
- "permanently" → duration_type="permanent", duration=0
- No duration mentioned → duration_type="rounds", duration=1

## WORKED EXAMPLES

**Example 1: Standard spell, DM name-drops**
Narrative: "Gandalf casts Bless on Aragorn"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "aragorn",
      "action": "add",
      "effect_name": "Bless",
      "description": "Whenever you make an attack roll or saving throw, you can roll a d4 and add it to the result",
      "summary": "+1d4 to attack rolls and saving throws",
      "duration_type": "concentration",
      "duration": 10,
      "effect_type": "buff"
    }
  ]
}
```

**Example 2: DM explicit but partial**
Narrative: "The cleric blesses you, granting +1d4 to your attack rolls for the next minute"
Extraction: Same as Example 1 - Agent fills in "and saving throws" because Bless is a standard spell

**Example 3: Homebrew modification**
Narrative: "The wizard casts Modified Bless, granting +1d6 to attack rolls only (not saves)"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "you",
      "action": "add",
      "effect_name": "Modified Bless",
      "description": "Grants +1d6 to attack rolls only (not saving throws)",
      "summary": "+1d6 to attack rolls only",
      "duration_type": "minutes",
      "duration": 1,
      "effect_type": "buff"
    }
  ]
}
```

**Example 4: Complex standard spell (Haste)**
Narrative: "The wizard casts Haste on Aragorn"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "aragorn",
      "action": "add",
      "effect_name": "Haste",
      "description": "Grants +2 AC, advantage on Dexterity saving throws, doubled speed, and one extra action each turn (Attack, Dash, Disengage, Hide, or Use an Object only)",
      "summary": "+2 AC, advantage on Dex saves, doubled speed, extra action (Attack/Dash/Disengage/Hide/Use Object only)",
      "duration_type": "concentration",
      "duration": 10,
      "effect_type": "buff"
    }
  ]
}
```

**Example 5: Custom effect**
Narrative: "The dragon's aura surrounds you, granting resistance to fire damage"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "you",
      "action": "add",
      "effect_name": "Dragon Aura",
      "description": "Grants resistance to fire damage",
      "summary": "Resistance to fire damage",
      "duration_type": "rounds",
      "duration": 1,
      "effect_type": "buff"
    }
  ]
}
```

**Example 6: Condition application**
Narrative: "The orc's poisoned blade strikes Gimli. He becomes poisoned"
Extraction:
```json
{
  "commands": [
    {
      "type": "condition",
      "character_id": "gimli",
      "action": "add",
      "condition": "poisoned",
      "duration_type": "rounds",
      "duration": 10
    }
  ]
}
```

**Example 7: Effect removal**
Narrative: "The Haste spell wears off from Legolas"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "legolas",
      "action": "remove",
      "effect_name": "Haste"
    }
  ]
}
```

**Example 8: Multiple effects**
Narrative: "The cleric casts Bless on Aragorn and Gimli. The orc poisons Legolas with its blade"
Extraction:
```json
{
  "commands": [
    {
      "type": "effect",
      "character_id": "aragorn",
      "action": "add",
      "effect_name": "Bless",
      "description": "Whenever you make an attack roll or saving throw, you can roll a d4 and add it to the result",
      "summary": "+1d4 to attack rolls and saving throws",
      "duration_type": "concentration",
      "duration": 10,
      "effect_type": "buff"
    },
    {
      "type": "effect",
      "character_id": "gimli",
      "action": "add",
      "effect_name": "Bless",
      "description": "Whenever you make an attack roll or saving throw, you can roll a d4 and add it to the result",
      "summary": "+1d4 to attack rolls and saving throws",
      "duration_type": "concentration",
      "duration": 10,
      "effect_type": "buff"
    },
    {
      "type": "condition",
      "character_id": "legolas",
      "action": "add",
      "condition": "poisoned",
      "duration_type": "rounds",
      "duration": 10
    }
  ]
}
```

## IMPORTANT REMINDERS

1. **Skip non-effect information** but continue scanning:
   - HP changes: "takes 10 damage" → Skip, keep reading
   - Resource usage: "uses a 3rd level spell slot" → Skip, keep reading
   - Dice rolls: "rolls a 15" → Skip, keep reading

2. **Always extract ALL effects and conditions**, even if other game events are mentioned

3. **Return empty list if no effects/conditions found**

4. **Character ID normalization**: Always lowercase with underscores

5. **Standard spell knowledge**: Use your D&D knowledge to fill in complete mechanics for standard spells

Return EffectAgentResult with a list of ConditionCommand and EffectCommand objects.
IF NO effects or conditions are found, return an empty list.
"""


class EffectAgent:
    """Specialized agent for extracting effect and condition commands."""

    def __init__(self, model_name: str, api_key: str):
        """
        Initialize the effect agent.

        Args:
            model_name: Gemini model to use
            api_key: API key (required for guild-level BYOK)
        """
        if not api_key:
            raise ValueError("API key is required for EffectAgent")

        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=api_key)
        )
        self.agent = Agent(
            model=self.model,
            name="Effect Agent",
            instructions=EFFECT_AGENT_INSTRUCTIONS,
            output_type=EffectAgentResult
        )

    async def extract(
        self,
        narrative: str,
        game_context: Optional[dict] = None
    ) -> EffectAgentResult:
        """
        Extract effect and condition commands from narrative.

        Args:
            narrative: Game narrative text (can be plain text or XML-formatted)
            game_context: Optional additional context

        Returns:
            EffectAgentResult with list of ConditionCommand and EffectCommand objects
        """
        try:
            prompt = self._prepare_prompt(narrative, game_context)
            result = await self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else result
        except Exception as e:
            return EffectAgentResult(commands=[])

    def _prepare_prompt(self, narrative: str, game_context: Optional[dict] = None) -> str:
        """Prepare extraction prompt."""
        sections = [
            "Extract effect and condition commands from the following narrative:",
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

        sections.append("Return EffectAgentResult with all effects and conditions as ConditionCommand and EffectCommand objects.")

        return "\n".join(sections)


def create_effect_agent(model_name: str, api_key: str) -> EffectAgent:
    """
    Factory function to create Effect agent.

    Args:
        model_name: Gemini model to use
        api_key: API key (required for guild-level BYOK)
    """
    return EffectAgent(model_name=model_name, api_key=api_key)

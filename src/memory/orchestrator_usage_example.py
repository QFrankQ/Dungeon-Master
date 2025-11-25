"""
Example usage of StateCommandOrchestrator for expanding RestCommand.

NOTE: This is a documentation/example file showing usage patterns.
      For runnable examples, see tests/test_state_commands_extended.py

This demonstrates the orchestrator pattern:
    Agent → generates RestCommand
    Orchestrator → expands to atomic commands
    Executor → executes atomic commands
"""

from src.memory.state_command_executor import StateCommandExecutor
from src.memory.state_command_orchestrator import StateCommandOrchestrator
from src.models.state_commands_optimized import (
    RestCommand,
    HPChangeCommand,
    EffectCommand
)
from src.characters.charactersheet import Character


# ==================== Setup ====================

# Mock character registry for examples
# In real usage, this would be your actual character database/registry
mock_characters = {
    "aragorn": None,  # Replace with actual Character instance
    "gimli": None,    # Replace with actual Character instance
    "legolas": None,  # Replace with actual Character instance
}

def get_character(character_id: str) -> Character:
    """Mock character lookup function"""
    # In real usage, this would query your character registry/database
    return mock_characters.get(character_id)


# Create executor and orchestrator
executor = StateCommandExecutor(character_lookup=get_character)
orchestrator = StateCommandOrchestrator(executor)


# ==================== Example 1: RestCommand Expansion ====================

# Agent generates a RestCommand (from state extraction)
commands_from_agent = [
    RestCommand(
        character_id="aragorn",
        rest_type="long"
    )
]

# Process through orchestrator (NOT executor directly!)
result = orchestrator.process_and_execute(
    commands=commands_from_agent,
    character_lookup=get_character
)

# What happens internally:
# 1. Orchestrator sees RestCommand
# 2. Looks up character "aragorn"
# 3. Expands to atomic commands:
#    - HPChangeCommand (heal to full)
#    - HitDiceCommand (restore half)
#    - SpellSlotCommand × N (restore all levels)
#    - EffectCommand × M (remove temporary effects)
# 4. Executor receives only atomic commands
# 5. Returns BatchExecutionResult

print(f"Total commands executed: {result.total_commands}")
print(f"Successful: {result.successful}")
print(f"Failed: {result.failed}")


# ==================== Example 2: Mixed Commands ====================

# Agent can generate mix of RestCommand and atomic commands
mixed_commands = [
    HPChangeCommand(
        character_id="gimli",
        change=-15,
        change_type="damage"
    ),
    RestCommand(
        character_id="gimli",
        rest_type="short",
        hit_dice_spent=2
    ),
    EffectCommand(
        character_id="legolas",
        action="add",
        effect_name="Haste",
        duration_type="concentration",
        duration=10,
        description="+2 AC, advantage on Dex saves, doubled speed",
        summary="+2 AC, adv Dex, 2x speed"
    )
]

# Orchestrator handles all commands appropriately
result = orchestrator.process_and_execute(
    commands=mixed_commands,
    character_lookup=get_character
)

# RestCommand gets expanded, others pass through unchanged


# ==================== Example 3: Short Rest with Hit Dice ====================

short_rest_command = RestCommand(
    character_id="aragorn",
    rest_type="short",
    hit_dice_spent=3  # Spend 3 hit dice for healing
)

# Expands to:
# - HitDiceCommand(action="use", count=3)
# - HPChangeCommand(change=calculated_healing, change_type="heal")

result = orchestrator.process_and_execute(
    commands=[short_rest_command],
    character_lookup=get_character
)


# ==================== Example 4: Error Handling ====================

# If character doesn't exist, orchestrator creates error result
invalid_command = RestCommand(
    character_id="nonexistent_character",
    rest_type="long"
)

result = orchestrator.process_and_execute(
    commands=[invalid_command],
    character_lookup=get_character
)

# result.failed == 1
# result.results[0].success == False
# result.results[0].message == "Character 'nonexistent_character' not found"


# ==================== Integration with State Extraction ====================

class StateExtractionAgent:
    """Example agent that generates RestCommand"""

    def extract_commands(self, narrative: str):
        # Agent detects rest in narrative
        if "long rest" in narrative.lower():
            return [
                RestCommand(
                    character_id=self.extract_character_id(narrative),
                    rest_type="long"
                )
            ]
        # ... other extraction logic


# In session manager or orchestrator:
def process_narrative(narrative: str):
    # Agent extracts commands (may include RestCommand)
    commands = agent.extract_commands(narrative)

    # Use orchestrator to expand and execute
    result = orchestrator.process_and_execute(
        commands=commands,
        character_lookup=get_character
    )

    return result


# ==================== Key Points ====================

"""
1. ALWAYS use StateCommandOrchestrator.process_and_execute() when you have RestCommand
2. NEVER call StateCommandExecutor.execute_batch() directly with RestCommand
3. RestCommand exists in agent schema for simplicity
4. RestCommand never reaches executor (expanded first)
5. Orchestrator can handle mixed commands (RestCommand + atomic commands)
"""

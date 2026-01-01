"""
Simple structured response class for DM agent.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from src.models.response_expectation import ResponseExpectation


# class ToolCall(BaseModel):
#     """Basic tool call structure."""
#     name: str = Field(..., description="Name of the tool/function to call")
#     parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool call")


class MonsterReactionDecision(BaseModel):
    """
    Represents a DM's decision about whether a monster will use their reaction.

    This is used during reaction windows to track which monsters will react.
    The decision is hidden from players until the reaction actually triggers.
    """
    monster_id: str = Field(..., description="The monster's ID (e.g., 'goblin_1', 'orc_chief')")
    reaction_name: str = Field(..., description="Name of the reaction ability (e.g., 'Opportunity Attack', 'Parry')")
    trigger_condition: str = Field(..., description="What triggers this reaction (e.g., 'if targeted by a melee attack')")
    will_use: bool = Field(..., description="Whether the monster will use this reaction when triggered")


# Legacy alias for backward compatibility
EnemyReactionDecision = MonsterReactionDecision


class DungeonMasterResponse(BaseModel):
    """
    Simple structured response from the DM agent.

    Contains the narrative response and optional basic tool calls.
    State extraction will be handled by a separate agent.

    Character validation for awaiting_response happens automatically via
    ResponseExpectation's model_validator when ResponseExpectation.registered_characters
    is set (use character_registry_context before calling the DM agent).
    """
    narrative: str = Field(..., description="The game narrative and your message to the active player(s)")
    # tool_calls: Optional[List[ToolCall]] = Field(None, description="Optional list of tool calls to execute")
    game_step_completed: bool = Field(..., description='''"True" only if current game step objectives are met; "False" if game step objectives are not met or if you're asking the players for more information.''')

    # Multiplayer coordination - REQUIRED field
    awaiting_response: ResponseExpectation = Field(
        ...,
        description=(
            "REQUIRED: Specifies who should respond next and what kind of response is expected. "
            "Set characters to the list of character names who should respond. "
            "Set response_type to: 'action' for normal turns, 'initiative' for initiative rolls, "
            "'saving_throw' for saves, 'reaction' for reaction opportunities, "
            "'free_form' for exploration, 'none' when narrating without expecting a response. "
            "You MUST always include this field in every response."
        )
    )

    # Monster reaction decisions (hidden from players until triggered)
    monster_reactions: Optional[List[MonsterReactionDecision]] = Field(
        None,
        description=(
            "Optional: During reaction windows, list monster reaction decisions. "
            "For each monster with a reaction ability, decide if they will use it based on the trigger. "
            "This is hidden from players - only include monsters that WILL react. "
            "DO NOT announce monster reaction intent in the narrative."
        )
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "narrative": "You successfully cast the healing spell, feeling warmth flow through your wounds. The goblin falls unconscious from its wounds, ending the combat encounter.",
                    "game_step_completed": True,
                    "awaiting_response": {
                        "characters": ["Tharion"],
                        "response_type": "action"
                    }
                },
                {
                    "narrative": "What would you like to do? You can attack, cast a spell, or try to negotiate.",
                    "game_step_completed": False,
                    "awaiting_response": {
                        "characters": ["Lyralei"],
                        "response_type": "action"
                    }
                },
                {
                    "narrative": "A fireball erupts in your midst! Tharion and Lyralei, roll Dexterity saving throws!",
                    "game_step_completed": False,
                    "awaiting_response": {
                        "characters": ["Tharion", "Lyralei"],
                        "response_type": "saving_throw",
                        "prompt": "Roll Dex save DC 15"
                    }
                },
                {
                    "narrative": "Roll for initiative!",
                    "game_step_completed": False,
                    "awaiting_response": {
                        "characters": ["Tharion", "Lyralei", "Kira"],
                        "response_type": "initiative"
                    }
                }
            ]
        }

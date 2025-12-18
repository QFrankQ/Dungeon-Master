"""
Response expectation models for multiplayer coordination.

These models define what kind of response the system expects from players
after a DM message, enabling turn-based coordination in multiplayer D&D sessions.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """
    Type of response expected from players.

    Determines timeout duration, UI presentation, AND collection mode.
    The system infers how to collect responses based on this type.
    """
    ACTION = "action"
    """Normal turn action - wait for 1 response from characters[0]"""

    INITIATIVE = "initiative"
    """Rolling initiative - wait for ALL listed characters"""

    SAVING_THROW = "saving_throw"
    """Saving throw - wait for ALL listed characters"""

    REACTION = "reaction"
    """Reaction opportunity - OPTIONAL, continue on timeout (players can pass)"""

    FREE_FORM = "free_form"
    """Open exploration - wait for ANY 1 response from listed characters"""

    NONE = "none"
    """No response expected - DM is narrating"""


class ResponseExpectation(BaseModel):
    """
    Specifies who should respond and what kind of response is expected.

    The system infers collection mode and timeout from response_type:
    - ACTION: Wait for characters[0] only (single player's turn)
    - INITIATIVE: Wait for ALL listed characters
    - SAVING_THROW: Wait for ALL listed characters
    - REACTION: Optional - continue on timeout, players can pass
    - FREE_FORM: Wait for ANY 1 response from listed characters
    - NONE: No response expected
    """

    characters: List[str] = Field(
        default_factory=list,
        description="Character names who should respond. For ACTION, first character is active. Empty for NONE."
    )

    response_type: ResponseType = Field(
        default=ResponseType.ACTION,
        description=(
            "Type of response expected: "
            "'action' for normal turns, "
            "'initiative' for initiative rolls, "
            "'saving_throw' for saving throws, "
            "'reaction' for reaction opportunities, "
            "'free_form' for exploration, "
            "'none' when narrating"
        )
    )

    prompt: Optional[str] = Field(
        default=None,
        description="Optional hint for players (e.g., 'Roll Dex save DC 15'). If omitted, system generates from response_type."
    )

    def get_collection_mode(self) -> str:
        """
        Derive collection mode from response_type.

        Returns:
            str: One of "single", "all", "optional", "any", "none"
        """
        return {
            ResponseType.ACTION: "single",      # Wait for characters[0]
            ResponseType.INITIATIVE: "all",     # Wait for all
            ResponseType.SAVING_THROW: "all",   # Wait for all
            ResponseType.REACTION: "optional",  # Continue on timeout
            ResponseType.FREE_FORM: "any",      # First response wins
            ResponseType.NONE: "none",          # No response expected
        }[self.response_type]

    def get_active_character(self) -> Optional[str]:
        """
        Get the primary active character for ACTION type.

        Returns:
            Optional[str]: First character in list for ACTION, None otherwise
        """
        if self.response_type == ResponseType.ACTION and self.characters:
            return self.characters[0]
        return None

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "characters": ["Tharion"],
                    "response_type": "action",
                    "prompt": None
                },
                {
                    "characters": ["Tharion", "Lyralei", "Kira"],
                    "response_type": "initiative",
                    "prompt": None
                },
                {
                    "characters": ["Tharion", "Lyralei"],
                    "response_type": "saving_throw",
                    "prompt": "Roll Dex save DC 15"
                },
                {
                    "characters": ["Lyralei"],
                    "response_type": "reaction",
                    "prompt": "Opportunity attack?"
                },
                {
                    "characters": ["Tharion", "Lyralei", "Kira"],
                    "response_type": "free_form",
                    "prompt": None
                },
                {
                    "characters": [],
                    "response_type": "none",
                    "prompt": None
                }
            ]
        }

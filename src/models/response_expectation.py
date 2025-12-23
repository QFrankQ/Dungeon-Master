"""
Response expectation models for multiplayer coordination.

These models define what kind of response the system expects from players
after a DM message, enabling turn-based coordination in multiplayer D&D sessions.
"""

from contextlib import contextmanager
from enum import Enum
from typing import List, Optional, Set, ClassVar, Iterator

from pydantic import BaseModel, Field, model_validator


@contextmanager
def character_registry_context(characters: Set[str]) -> Iterator[None]:
    """
    Context manager to set the registered characters for validation.

    Use this before calling the DM agent to enable character validation:

        with character_registry_context({"Alice", "Bob"}):
            result = await dm_agent.run(...)

    The registry is automatically cleared after the context exits.
    """
    old_value = ResponseExpectation.registered_characters
    ResponseExpectation.registered_characters = characters
    try:
        yield
    finally:
        ResponseExpectation.registered_characters = old_value


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

    Validation:
    - Set `ResponseExpectation.registered_characters` before parsing DM output
    - Characters are validated against registry (unknown chars filtered out)
    - Initiative allows unknown characters (for enemies/NPCs)
    - If ALL characters unknown, raises ValidationError (DM gets feedback)
    """

    # Class-level registry - set before parsing DM output
    registered_characters: ClassVar[Optional[Set[str]]] = None

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

    # Store filtered-out characters for warnings (not part of schema)
    _filtered_characters: List[str] = []

    @model_validator(mode='after')
    def validate_characters_against_registry(self) -> 'ResponseExpectation':
        """
        Validate characters against the registered character set.

        This validator runs at parse time, giving the DM agent immediate
        feedback if it references invalid characters.
        """
        # Skip validation if no registry set (e.g., testing without session)
        if ResponseExpectation.registered_characters is None:
            return self

        # Response types that REQUIRE characters
        requires_characters = {
            ResponseType.ACTION,
            ResponseType.INITIATIVE,
            ResponseType.SAVING_THROW,
            ResponseType.REACTION,
        }

        if self.response_type not in requires_characters:
            return self

        # Check for empty character list
        if not self.characters:
            if self.response_type != ResponseType.NONE:
                raise ValueError(
                    f"response_type '{self.response_type.value}' requires at least one character. "
                    f"Registered characters: {sorted(ResponseExpectation.registered_characters)}"
                )
            return self

        # Initiative can include enemies/NPCs - skip character validation
        if self.response_type == ResponseType.INITIATIVE:
            return self

        # Find unknown characters
        registry = ResponseExpectation.registered_characters
        unknown_chars = [c for c in self.characters if c not in registry]

        if not unknown_chars:
            return self

        known_chars = [c for c in self.characters if c in registry]

        if not known_chars:
            # ALL characters are unknown - raise error so DM can self-correct
            raise ValueError(
                f"None of the specified characters are registered: {unknown_chars}. "
                f"Registered characters: {sorted(registry)}"
            )

        # Some known, some unknown - filter to known only and store filtered for warnings
        self._filtered_characters = unknown_chars
        self.characters = known_chars

        return self

    def get_filtered_characters(self) -> List[str]:
        """Get characters that were filtered out during validation."""
        return self._filtered_characters

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

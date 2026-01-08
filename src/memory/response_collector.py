"""
Response collector for multiplayer coordination.

Collects responses from expected players based on ResponseExpectation,
supporting different collection modes (single, all, any, optional).
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.models.response_expectation import ResponseExpectation, ResponseType


class AddResult(str, Enum):
    """Result of adding a response to the collector."""
    ACCEPTED = "accepted"
    """Response was accepted and added to collection."""

    DUPLICATE = "duplicate"
    """Character already responded - this is a duplicate."""

    UNEXPECTED = "unexpected"
    """Character was not expected to respond."""


@dataclass
class ResponseCollector:
    """
    Collects responses from expected players.

    Supports different collection modes based on ResponseExpectation:
    - single: Wait for one response from characters[0]
    - all: Wait for all listed characters
    - any: Accept first response from any listed character
    - optional: Continue on timeout, players can pass
    - none: No response expected

    Attributes:
        expectation: The ResponseExpectation defining who should respond
        collected: Dict mapping character name to their response data
        started_at: When collection started
        batch_delay: Buffer time for rapid-fire responses (seconds)
    """

    expectation: ResponseExpectation
    collected: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    batch_delay: float = 0.5
    _batch_task: Optional[asyncio.Task] = None

    def add_response(self, character_name: str, data: Any) -> AddResult:
        """
        Add a response from a character.

        Args:
            character_name: Name of the character responding
            data: The response data (message content, roll result, etc.)

        Returns:
            AddResult indicating whether the response was accepted
        """
        # Check if character is expected
        if character_name not in self.expectation.characters:
            return AddResult.UNEXPECTED

        # Check for duplicate
        if character_name in self.collected:
            return AddResult.DUPLICATE

        # Accept the response
        self.collected[character_name] = data
        return AddResult.ACCEPTED

    def remove_response(self, character_name: str) -> bool:
        """
        Remove a previously collected response.

        Used when processing fails (e.g., API errors) and the player
        needs to be able to retry their action.

        Args:
            character_name: Name of the character whose response to remove

        Returns:
            True if response was removed, False if not found
        """
        if character_name in self.collected:
            del self.collected[character_name]
            return True
        return False

    def is_complete(self) -> bool:
        """
        Check if collection is complete based on the collection mode.

        Returns:
            True if enough responses have been collected
        """
        mode = self.expectation.get_collection_mode()

        if mode == "single":
            # For ACTION type, only need one response
            return len(self.collected) >= 1

        elif mode == "all":
            # For INITIATIVE/SAVING_THROW, need all listed characters
            return len(self.collected) >= len(self.expectation.characters)

        elif mode == "any":
            # For FREE_FORM, first response completes
            return len(self.collected) >= 1

        elif mode == "optional":
            # For REACTION, never completes via collection alone
            # Must be completed via timeout or all passing
            return False

        elif mode == "none":
            # For NONE type, immediately complete (no responses expected)
            return True

        return False

    def get_missing_responders(self) -> List[str]:
        """
        Get list of characters who haven't responded yet.

        Returns:
            List of character names who still need to respond
        """
        return [c for c in self.expectation.characters if c not in self.collected]

    def get_active_character(self) -> Optional[str]:
        """
        Get the primary active character (for ACTION type).

        Returns:
            The first character in the expectation list, or None
        """
        return self.expectation.get_active_character()

    def is_valid_responder(self, character_name: str) -> bool:
        """
        Check if a character is expected to respond.

        Args:
            character_name: Name of the character to check

        Returns:
            True if the character is in the expected list
        """
        return character_name in self.expectation.characters

    def get_status_message(self) -> str:
        """
        Get a human-readable status message.

        Returns:
            Status string like "Waiting for: Alice, Bob" or "Complete"
        """
        if self.is_complete():
            return "Complete"

        mode = self.expectation.get_collection_mode()

        if mode == "none":
            return "No response expected"

        missing = self.get_missing_responders()
        if not missing:
            return "Complete"

        if mode == "single":
            return f"Waiting for: {missing[0]}"
        elif mode in ("all", "optional"):
            return f"Waiting for: {', '.join(missing)}"
        elif mode == "any":
            return f"Waiting for any of: {', '.join(self.expectation.characters)}"

        return f"Waiting for: {', '.join(missing)}"

    def reset(self):
        """Reset the collector for a new collection cycle."""
        self.collected.clear()
        self.started_at = datetime.now()
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
        self._batch_task = None


def create_response_collector(expectation: ResponseExpectation) -> ResponseCollector:
    """
    Factory function to create a ResponseCollector.

    Args:
        expectation: The ResponseExpectation defining collection parameters

    Returns:
        A new ResponseCollector instance
    """
    return ResponseCollector(expectation=expectation)

"""
Message Coordinator for multiplayer coordination.

Central message routing based on game state - acts as a gatekeeper to validate
who can send messages and when, supporting both strict combat mode and flexible
exploration mode.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import Enum

from src.models.response_expectation import ResponseExpectation, ResponseType
from src.memory.response_collector import ResponseCollector, AddResult, create_response_collector


class MessageValidationResult(str, Enum):
    """Result of validating an incoming message."""
    VALID = "valid"
    """Message is from an expected responder."""

    INVALID_NOT_YOUR_TURN = "invalid_not_your_turn"
    """Combat mode: message from wrong character."""

    INVALID_NO_RESPONSE_EXPECTED = "invalid_no_response_expected"
    """Combat mode: DM is narrating, no response expected."""

    INVALID_ALREADY_RESPONDED = "invalid_already_responded"
    """Character has already responded in this collection cycle."""


@dataclass
class ValidationResponse:
    """Response from message validation."""
    result: MessageValidationResult
    message: str = ""
    expected_characters: List[str] = field(default_factory=list)


@dataclass
class MessageCoordinator:
    """
    Central message routing based on game state - acts as gatekeeper.

    Responsibilities:
    - Track combat mode vs exploration mode
    - Validate if a character is expected to respond
    - Manage response collection for multi-response scenarios
    - Track DM processing state to handle mid-processing messages

    Attributes:
        combat_mode: When True, strict turn enforcement is enabled
        current_expectation: The current ResponseExpectation from DM
        response_collector: Collects responses for multi-response modes
        dm_processing: Lock flag while DM is generating a response
    """

    combat_mode: bool = False
    current_expectation: Optional[ResponseExpectation] = None
    response_collector: Optional[ResponseCollector] = None
    dm_processing: bool = False

    def validate_responder(self, character_name: str) -> ValidationResponse:
        """
        Validate if a character is allowed to send a message.

        Args:
            character_name: Name of the character trying to send a message

        Returns:
            ValidationResponse with result and descriptive message
        """
        # Exploration mode - accept all messages
        if not self.combat_mode:
            return ValidationResponse(
                result=MessageValidationResult.VALID,
                message="Exploration mode - all messages accepted"
            )

        # No expectation set - accept all (shouldn't happen in combat, but safe default)
        if self.current_expectation is None:
            return ValidationResponse(
                result=MessageValidationResult.VALID,
                message="No expectation set - accepting message"
            )

        # Check response type
        if self.current_expectation.response_type == ResponseType.NONE:
            return ValidationResponse(
                result=MessageValidationResult.INVALID_NO_RESPONSE_EXPECTED,
                message="DM is narrating - no response expected"
            )

        # Check if character is in expected list
        if character_name not in self.current_expectation.characters:
            expected = self.current_expectation.characters
            if expected:
                return ValidationResponse(
                    result=MessageValidationResult.INVALID_NOT_YOUR_TURN,
                    message=f"Not your turn! Waiting for: {', '.join(expected)}",
                    expected_characters=expected
                )
            else:
                return ValidationResponse(
                    result=MessageValidationResult.INVALID_NO_RESPONSE_EXPECTED,
                    message="No characters expected to respond"
                )

        # Check for duplicate responses in multi-response mode
        if self.response_collector and character_name in self.response_collector.collected:
            return ValidationResponse(
                result=MessageValidationResult.INVALID_ALREADY_RESPONDED,
                message=f"{character_name} has already responded"
            )

        # Valid responder
        return ValidationResponse(
            result=MessageValidationResult.VALID,
            message=f"{character_name} is a valid responder"
        )

    def is_valid_responder(self, character_name: str) -> bool:
        """
        Simple boolean check if character is expected to respond.

        Args:
            character_name: Name of the character to check

        Returns:
            True if the character is allowed to send a message
        """
        return self.validate_responder(character_name).result == MessageValidationResult.VALID

    def set_expectation(self, expectation: Optional[ResponseExpectation]):
        """
        Update who we're waiting for (called after DM response).

        Args:
            expectation: The new ResponseExpectation from DM, or None to clear
        """
        self.current_expectation = expectation

        # Create new response collector if we have an expectation
        if expectation is not None:
            self.response_collector = create_response_collector(expectation)
        else:
            self.response_collector = None

    def add_response(self, character_name: str, data: Any) -> AddResult:
        """
        Add a response to the collector.

        Args:
            character_name: Name of the character responding
            data: The response data (message content, roll result, etc.)

        Returns:
            AddResult indicating whether the response was accepted
        """
        if self.response_collector is None:
            return AddResult.UNEXPECTED

        return self.response_collector.add_response(character_name, data)

    def is_collection_complete(self) -> bool:
        """
        Check if response collection is complete.

        Returns:
            True if all expected responses have been collected
        """
        if self.response_collector is None:
            return True  # No collection in progress

        return self.response_collector.is_complete()

    def get_collected_responses(self) -> Dict[str, Any]:
        """
        Get all collected responses.

        Returns:
            Dict mapping character names to their response data
        """
        if self.response_collector is None:
            return {}

        return dict(self.response_collector.collected)

    def get_missing_responders(self) -> List[str]:
        """
        Get list of characters who haven't responded yet.

        Returns:
            List of character names still expected to respond
        """
        if self.response_collector is None:
            return []

        return self.response_collector.get_missing_responders()

    def get_collection_mode(self) -> str:
        """
        Get the current collection mode.

        Returns:
            Collection mode string: "single", "all", "any", "optional", or "none"
        """
        if self.current_expectation is None:
            return "none"

        return self.current_expectation.get_collection_mode()

    def get_status_message(self) -> str:
        """
        Get a human-readable status message.

        Returns:
            Status string describing current coordination state
        """
        if not self.combat_mode:
            return "Exploration mode - all messages accepted"

        if self.current_expectation is None:
            return "No expectation set"

        if self.response_collector:
            return self.response_collector.get_status_message()

        return "Unknown state"

    def enter_combat_mode(self):
        """Enable strict turn enforcement."""
        self.combat_mode = True

    def exit_combat_mode(self):
        """Return to flexible message handling."""
        self.combat_mode = False
        self.current_expectation = None
        self.response_collector = None

    def start_dm_processing(self):
        """Mark that DM is currently generating a response."""
        self.dm_processing = True

    def end_dm_processing(self):
        """Mark that DM has finished generating a response."""
        self.dm_processing = False

    def is_dm_processing(self) -> bool:
        """Check if DM is currently generating a response."""
        return self.dm_processing

    def reset(self):
        """Reset coordinator to initial state."""
        self.combat_mode = False
        self.current_expectation = None
        self.response_collector = None
        self.dm_processing = False


def create_message_coordinator() -> MessageCoordinator:
    """
    Factory function to create a MessageCoordinator.

    Returns:
        A new MessageCoordinator instance
    """
    return MessageCoordinator()

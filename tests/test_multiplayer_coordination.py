"""
Tests for Multiplayer Coordination System (Milestones 1-6).

Tests cover:
- Milestone 1: ResponseExpectation model and ResponseType enum
- Milestone 2: MessageCoordinator validation logic
- Milestone 3: ResponseCollector collection modes
- Milestone 4: Discord Views (ReactionView, InitiativeView, SaveView)
- Milestone 5: Integration between views and DM routing
- Milestone 6: Validation and configurable timeouts
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Set

# Milestone 1: Response models
from src.models.response_expectation import (
    ResponseExpectation,
    ResponseType,
    character_registry_context,
)
from src.models.dm_response import DungeonMasterResponse

# Milestone 2: Message coordination
from src.memory.message_coordinator import (
    MessageCoordinator,
    MessageValidationResult,
    create_message_coordinator,
)

# Milestone 3: Response collection
from src.memory.response_collector import (
    AddResult,
    create_response_collector,
)

# Milestone 6: Configurable timeouts
from src.discord.utils.session_pool import SessionTimeouts


# =============================================================================
# MILESTONE 1: ResponseExpectation and ResponseType
# =============================================================================

class TestResponseType:
    """Test ResponseType enum values and behavior."""

    def test_response_type_values(self):
        """All expected response types exist."""
        assert ResponseType.ACTION == "action"
        assert ResponseType.INITIATIVE == "initiative"
        assert ResponseType.SAVING_THROW == "saving_throw"
        assert ResponseType.REACTION == "reaction"
        assert ResponseType.FREE_FORM == "free_form"
        assert ResponseType.NONE == "none"

    def test_response_type_is_string_enum(self):
        """ResponseType values can be used as strings."""
        # str() returns the enum representation, .value returns the string
        assert ResponseType.ACTION.value == "action"
        # ResponseType inherits from str, so direct comparison works
        assert ResponseType.ACTION == "action"


class TestResponseExpectation:
    """Test ResponseExpectation model."""

    def test_default_values(self):
        """Default values are correct."""
        exp = ResponseExpectation()
        assert exp.characters == []
        assert exp.response_type == ResponseType.ACTION
        assert exp.prompt is None

    def test_get_collection_mode_mapping(self):
        """Collection mode is correctly derived from response type."""
        assert ResponseExpectation(
            response_type=ResponseType.ACTION
        ).get_collection_mode() == "single"

        assert ResponseExpectation(
            response_type=ResponseType.INITIATIVE
        ).get_collection_mode() == "all"

        assert ResponseExpectation(
            response_type=ResponseType.SAVING_THROW
        ).get_collection_mode() == "all"

        assert ResponseExpectation(
            response_type=ResponseType.REACTION
        ).get_collection_mode() == "optional"

        assert ResponseExpectation(
            response_type=ResponseType.FREE_FORM
        ).get_collection_mode() == "any"

        assert ResponseExpectation(
            response_type=ResponseType.NONE
        ).get_collection_mode() == "none"

    def test_get_active_character_for_action(self):
        """Active character is first in list for ACTION type."""
        exp = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.ACTION
        )
        assert exp.get_active_character() == "Alice"

    def test_get_active_character_returns_none_for_non_action(self):
        """Active character is None for non-ACTION types."""
        exp = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        )
        assert exp.get_active_character() is None


class TestResponseExpectationValidation:
    """Test ResponseExpectation validation with registry."""

    def test_no_validation_without_registry(self):
        """Validation is skipped when no registry is set."""
        # Should not raise even with unknown characters
        exp = ResponseExpectation(
            characters=["Unknown1", "Unknown2"],
            response_type=ResponseType.ACTION
        )
        assert exp.characters == ["Unknown1", "Unknown2"]

    def test_valid_characters_pass(self):
        """Valid characters pass validation."""
        with character_registry_context({"Alice", "Bob"}):
            exp = ResponseExpectation(
                characters=["Alice", "Bob"],
                response_type=ResponseType.ACTION
            )
            assert exp.characters == ["Alice", "Bob"]
            assert exp.get_filtered_characters() == []

    def test_unknown_characters_filtered(self):
        """Unknown characters are filtered out."""
        with character_registry_context({"Alice", "Bob"}):
            exp = ResponseExpectation(
                characters=["Alice", "Unknown1", "Unknown2"],
                response_type=ResponseType.SAVING_THROW
            )
            assert exp.characters == ["Alice"]
            assert set(exp.get_filtered_characters()) == {"Unknown1", "Unknown2"}

    def test_all_unknown_raises_error(self):
        """All unknown characters raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            with character_registry_context({"Alice", "Bob"}):
                ResponseExpectation(
                    characters=["Unknown1", "Unknown2"],
                    response_type=ResponseType.ACTION
                )
        assert "None of the specified characters are registered" in str(exc_info.value)
        assert "Unknown1" in str(exc_info.value)

    def test_empty_characters_raises_error(self):
        """Empty characters for ACTION raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            with character_registry_context({"Alice", "Bob"}):
                ResponseExpectation(
                    characters=[],
                    response_type=ResponseType.ACTION
                )
        assert "requires at least one character" in str(exc_info.value)

    def test_initiative_allows_unknown_characters(self):
        """Initiative type allows unknown characters (for enemies)."""
        with character_registry_context({"Alice", "Bob"}):
            exp = ResponseExpectation(
                characters=["Alice", "Goblin1", "Goblin2"],
                response_type=ResponseType.INITIATIVE
            )
            # All characters kept (enemies allowed)
            assert exp.characters == ["Alice", "Goblin1", "Goblin2"]
            assert exp.get_filtered_characters() == []

    def test_none_type_allows_empty_characters(self):
        """NONE type allows empty characters."""
        with character_registry_context({"Alice", "Bob"}):
            exp = ResponseExpectation(
                characters=[],
                response_type=ResponseType.NONE
            )
            assert exp.characters == []

    def test_context_manager_restores_previous_value(self):
        """Context manager restores previous registry value."""
        ResponseExpectation.registered_characters = {"Original"}

        with character_registry_context({"New"}):
            assert ResponseExpectation.registered_characters == {"New"}

        assert ResponseExpectation.registered_characters == {"Original"}
        ResponseExpectation.registered_characters = None  # Cleanup


# =============================================================================
# MILESTONE 2: MessageCoordinator
# =============================================================================

class TestMessageCoordinator:
    """Test MessageCoordinator validation logic."""

    def test_create_message_coordinator(self):
        """Factory function creates coordinator correctly."""
        coordinator = create_message_coordinator()
        assert coordinator is not None
        assert coordinator.combat_mode is False

    def test_exploration_mode_allows_any_message(self):
        """In exploration mode, any message is allowed."""
        coordinator = create_message_coordinator()
        coordinator.combat_mode = False

        result = coordinator.validate_responder("Alice")
        assert result.result == MessageValidationResult.VALID

    def test_combat_mode_validates_turn(self):
        """In combat mode, only expected character can act."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        # Set expectation for Alice's turn
        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        ))

        # Alice can act
        result = coordinator.validate_responder("Alice")
        assert result.result == MessageValidationResult.VALID

        # Bob cannot act
        result = coordinator.validate_responder("Bob")
        assert result.result == MessageValidationResult.INVALID_NOT_YOUR_TURN

    def test_none_expectation_blocks_messages(self):
        """NONE expectation blocks messages (DM narrating)."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=[],
            response_type=ResponseType.NONE
        ))

        result = coordinator.validate_responder("Alice")
        assert result.result == MessageValidationResult.INVALID_NO_RESPONSE_EXPECTED

    def test_free_form_allows_any_listed_character(self):
        """FREE_FORM allows any listed character."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice", "Bob", "Charlie"],
            response_type=ResponseType.FREE_FORM
        ))

        # Any listed character can respond
        for char in ["Alice", "Bob", "Charlie"]:
            result = coordinator.validate_responder(char)
            assert result.result == MessageValidationResult.VALID

    def test_is_valid_responder_helper(self):
        """is_valid_responder returns simple boolean."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        ))

        assert coordinator.is_valid_responder("Alice") is True
        assert coordinator.is_valid_responder("Bob") is False

    def test_add_response_and_collection(self):
        """Test adding responses and checking collection status."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        ))

        # Add first response
        result = coordinator.add_response("Alice", {"roll": 15})
        assert result == AddResult.ACCEPTED
        assert not coordinator.is_collection_complete()

        # Add second response
        result = coordinator.add_response("Bob", {"roll": 12})
        assert result == AddResult.ACCEPTED
        assert coordinator.is_collection_complete()

        # Get collected responses
        responses = coordinator.get_collected_responses()
        assert responses["Alice"] == {"roll": 15}
        assert responses["Bob"] == {"roll": 12}

    def test_duplicate_response_rejected(self):
        """Duplicate responses are rejected via coordinator."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        ))

        # First response accepted
        coordinator.add_response("Alice", "Roll 1")

        # Duplicate rejected
        result = coordinator.add_response("Alice", "Roll 2")
        assert result == AddResult.DUPLICATE

    def test_remove_response_allows_retry(self):
        """remove_response allows player to retry after API error."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        ))

        # Add response (simulating player sending message)
        result = coordinator.add_response("Alice", "I attack")
        assert result == AddResult.ACCEPTED

        # Verify Alice has responded
        validation = coordinator.validate_responder("Alice")
        assert validation.result == MessageValidationResult.INVALID_ALREADY_RESPONDED

        # Remove response (simulating API error cleanup)
        removed = coordinator.remove_response("Alice")
        assert removed is True

        # Alice can now respond again
        validation = coordinator.validate_responder("Alice")
        assert validation.result == MessageValidationResult.VALID

        # Retry succeeds
        result = coordinator.add_response("Alice", "I attack again")
        assert result == AddResult.ACCEPTED

    def test_remove_response_not_found(self):
        """remove_response returns False if character hasn't responded."""
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        coordinator.set_expectation(ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        ))

        # Try to remove before adding
        removed = coordinator.remove_response("Alice")
        assert removed is False

    def test_remove_response_no_collector(self):
        """remove_response returns False if no collector exists."""
        coordinator = create_message_coordinator()

        # No expectation set, so no collector
        removed = coordinator.remove_response("Alice")
        assert removed is False

# =============================================================================
# MILESTONE 3: ResponseCollector
# =============================================================================

class TestResponseCollector:
    """Test ResponseCollector collection modes."""

    def test_single_mode_completes_on_first_response(self):
        """SINGLE mode (ACTION type) completes after first expected response."""
        expectation = ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        )
        collector = create_response_collector(expectation)

        result = collector.add_response("Alice", "I attack")
        assert result == AddResult.ACCEPTED
        assert collector.is_complete()

    def test_all_mode_waits_for_everyone(self):
        """ALL mode (INITIATIVE type) waits for all expected characters."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        )
        collector = create_response_collector(expectation)

        result = collector.add_response("Alice", "I roll 15")
        assert result == AddResult.ACCEPTED
        assert not collector.is_complete()

        result = collector.add_response("Bob", "I roll 12")
        assert result == AddResult.ACCEPTED
        assert collector.is_complete()

    def test_all_mode_for_saving_throws(self):
        """ALL mode (SAVING_THROW type) waits for all expected characters."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.SAVING_THROW
        )
        collector = create_response_collector(expectation)

        collector.add_response("Alice", "I roll 18")
        assert not collector.is_complete()

        collector.add_response("Bob", "I roll 7")
        assert collector.is_complete()

    def test_any_mode_completes_on_first(self):
        """ANY mode (FREE_FORM type) completes on first response from any expected character."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob", "Charlie"],
            response_type=ResponseType.FREE_FORM
        )
        collector = create_response_collector(expectation)

        result = collector.add_response("Bob", "I respond first")
        assert result == AddResult.ACCEPTED
        assert collector.is_complete()

    def test_optional_mode_never_auto_completes(self):
        """OPTIONAL mode (REACTION type) accepts responses but never auto-completes."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.REACTION
        )
        collector = create_response_collector(expectation)

        # Add responses
        result = collector.add_response("Alice", "I use Shield")
        assert result == AddResult.ACCEPTED

        result = collector.add_response("Bob", "I pass")
        assert result == AddResult.ACCEPTED

        # Still not complete - optional mode never auto-completes
        assert not collector.is_complete()

    def test_none_mode_immediately_complete(self):
        """NONE mode is immediately complete (no responses expected)."""
        expectation = ResponseExpectation(
            characters=[],
            response_type=ResponseType.NONE
        )
        collector = create_response_collector(expectation)

        assert collector.is_complete()

    def test_unexpected_character_rejected(self):
        """Responses from unexpected characters are rejected."""
        expectation = ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        )
        collector = create_response_collector(expectation)

        result = collector.add_response("Bob", "I try to act")
        assert result == AddResult.UNEXPECTED

    def test_duplicate_response_rejected(self):
        """Duplicate responses from same character are rejected."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        )
        collector = create_response_collector(expectation)

        collector.add_response("Alice", "First response")
        result = collector.add_response("Alice", "Second response")
        assert result == AddResult.DUPLICATE

    def test_collected_responses(self):
        """Can retrieve all collected responses."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        )
        collector = create_response_collector(expectation)

        collector.add_response("Alice", "Roll: 15")
        collector.add_response("Bob", "Roll: 12")

        assert collector.collected["Alice"] == "Roll: 15"
        assert collector.collected["Bob"] == "Roll: 12"

    def test_get_missing_responders(self):
        """Can get list of characters who haven't responded."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob", "Charlie"],
            response_type=ResponseType.INITIATIVE
        )
        collector = create_response_collector(expectation)

        collector.add_response("Bob", "I rolled")

        missing = collector.get_missing_responders()
        assert "Alice" in missing
        assert "Charlie" in missing
        assert "Bob" not in missing

    def test_get_active_character_for_action(self):
        """Get active character for ACTION type."""
        expectation = ResponseExpectation(
            characters=["Alice"],
            response_type=ResponseType.ACTION
        )
        collector = create_response_collector(expectation)

        assert collector.get_active_character() == "Alice"

    def test_get_status_message(self):
        """Get human-readable status messages."""
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.INITIATIVE
        )
        collector = create_response_collector(expectation)

        status = collector.get_status_message()
        assert "Alice" in status
        assert "Bob" in status

        collector.add_response("Alice", "Rolled")
        collector.add_response("Bob", "Rolled")

        assert collector.get_status_message() == "Complete"


# =============================================================================
# MILESTONE 4: Discord Views (Unit Tests)
# NOTE: Discord.py View classes require a running event loop.
# These tests use pytest-asyncio to provide the event loop.
# =============================================================================

class TestReactionView:
    """Test ReactionView logic without Discord."""

    @pytest.mark.asyncio
    async def test_reaction_view_initialization(self):
        """ReactionView initializes correctly."""
        from src.discord.views.reaction_view import ReactionView

        view = ReactionView(
            expected_characters=["Alice", "Bob"],
            prompt="Opportunity attack?",
            timeout=30.0
        )

        assert view.expected == {"Alice", "Bob"}
        assert view.prompt == "Opportunity attack?"
        assert view.passed == set()
        assert view.reactions == {}

    @pytest.mark.asyncio
    async def test_reaction_view_check_complete(self):
        """ReactionView completes when all have responded."""
        from src.discord.views.reaction_view import ReactionView

        view = ReactionView(
            expected_characters=["Alice", "Bob"],
            timeout=30.0
        )

        # Not complete initially
        assert not view._check_complete()

        # Alice passes
        view.passed.add("Alice")
        assert not view._check_complete()

        # Bob uses reaction
        view.reactions["Bob"] = {"type": "declared"}
        assert view._check_complete()

    @pytest.mark.asyncio
    async def test_reaction_view_results(self):
        """ReactionView returns correct results."""
        from src.discord.views.reaction_view import ReactionView

        view = ReactionView(
            expected_characters=["Alice", "Bob"],
            timeout=30.0
        )

        view.passed.add("Alice")
        view.reactions["Bob"] = {"type": "declared", "description": ""}

        results = view.get_results()
        assert "Alice" in results["passed"]
        assert "Bob" in results["reactions"]
        assert results["complete"] is True


class TestInitiativeView:
    """Test InitiativeView logic without Discord."""

    @pytest.mark.asyncio
    async def test_initiative_view_initialization(self):
        """InitiativeView initializes correctly."""
        from src.discord.views.initiative_modal import InitiativeView

        view = InitiativeView(
            expected_characters=["Alice", "Bob", "Goblin1"],
            timeout=120.0
        )

        assert view.expected == ["Alice", "Bob", "Goblin1"]
        assert view.collected == {}

    @pytest.mark.asyncio
    async def test_initiative_view_check_complete(self):
        """InitiativeView completes when all have rolled."""
        from src.discord.views.initiative_modal import InitiativeView

        view = InitiativeView(
            expected_characters=["Alice", "Bob"],
            timeout=120.0
        )

        assert not view._check_complete()

        view.collected["Alice"] = {"roll": 15, "source": "manual"}
        assert not view._check_complete()

        view.collected["Bob"] = {"roll": 12, "source": "manual"}
        assert view._check_complete()

    @pytest.mark.asyncio
    async def test_initiative_view_get_results(self):
        """InitiativeView returns sorted results by roll."""
        from src.discord.views.initiative_modal import InitiativeView

        view = InitiativeView(
            expected_characters=["Alice", "Bob"],
            timeout=120.0
        )

        view.collected["Alice"] = {"roll": 12, "source": "manual", "dex_modifier": 2}
        view.collected["Bob"] = {"roll": 18, "source": "manual", "dex_modifier": 1}

        results = view.get_results()
        # Bob should be first (higher roll)
        assert results["order"] == ["Bob", "Alice"]
        assert results["complete"] is True


class TestSaveView:
    """Test SaveView logic without Discord."""

    @pytest.mark.asyncio
    async def test_save_view_initialization(self):
        """SaveView initializes correctly."""
        from src.discord.views.save_modal import SaveView

        view = SaveView(
            expected_characters=["Alice", "Bob"],
            prompt="Roll Dex save",
            save_type="DEX",
            dc=15,
            timeout=60.0
        )

        assert view.expected == ["Alice", "Bob"]
        assert view.save_type == "DEX"
        assert view.dc == 15

    @pytest.mark.asyncio
    async def test_save_view_results_with_dc(self):
        """SaveView correctly determines successes/failures."""
        from src.discord.views.save_modal import SaveView

        view = SaveView(
            expected_characters=["Alice", "Bob"],
            prompt="Roll Dex save DC 15",
            save_type="DEX",
            dc=15,
            timeout=60.0
        )

        view.collected["Alice"] = {"roll": 18, "success": True}
        view.collected["Bob"] = {"roll": 10, "success": False}

        results = view.get_results()
        assert "Alice" in results["successes"]
        assert "Bob" in results["failures"]

    @pytest.mark.asyncio
    async def test_save_view_check_complete(self):
        """SaveView completes when all have rolled."""
        from src.discord.views.save_modal import SaveView

        view = SaveView(
            expected_characters=["Alice", "Bob"],
            prompt="Roll Con save",
            save_type="CON",
            dc=14,
            timeout=60.0
        )

        assert not view._check_complete()

        view.collected["Alice"] = {"roll": 15, "success": True}
        assert not view._check_complete()

        view.collected["Bob"] = {"roll": 12, "success": False}
        assert view._check_complete()


class TestParseSaveFromPrompt:
    """Test save prompt parsing utility."""

    def test_parse_dex_save(self):
        """Parse DEX save from prompt."""
        from src.discord.views.save_modal import parse_save_from_prompt

        save_type, dc = parse_save_from_prompt("Roll Dex save DC 15")
        assert save_type == "DEX"
        assert dc == 15

    def test_parse_wisdom_save(self):
        """Parse WIS save from prompt."""
        from src.discord.views.save_modal import parse_save_from_prompt

        save_type, dc = parse_save_from_prompt("Make a Wisdom saving throw DC 14")
        assert save_type == "WIS"
        assert dc == 14

    def test_parse_no_dc(self):
        """Handle prompt without DC."""
        from src.discord.views.save_modal import parse_save_from_prompt

        save_type, dc = parse_save_from_prompt("Roll a Constitution save")
        assert save_type == "CON"
        assert dc is None


# =============================================================================
# MILESTONE 6: Configurable Timeouts
# =============================================================================

class TestSessionTimeouts:
    """Test SessionTimeouts configuration."""

    def test_default_timeouts(self):
        """Default timeout values are correct."""
        timeouts = SessionTimeouts()
        assert timeouts.initiative == 120.0
        assert timeouts.saving_throw == 60.0
        assert timeouts.reaction == 30.0
        assert timeouts.action == 300.0

    def test_custom_timeouts(self):
        """Can set custom timeout values."""
        timeouts = SessionTimeouts(
            initiative=60.0,
            saving_throw=30.0,
            reaction=15.0,
            action=180.0
        )
        assert timeouts.initiative == 60.0
        assert timeouts.saving_throw == 30.0
        assert timeouts.reaction == 15.0
        assert timeouts.action == 180.0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestDungeonMasterResponseIntegration:
    """Test DungeonMasterResponse with validation."""

    def test_dm_response_with_valid_expectation(self):
        """DM response with valid expectation parses correctly."""
        with character_registry_context({"Alice", "Bob"}):
            response = DungeonMasterResponse(
                narrative="The goblin attacks Alice!",
                game_step_completed=False,
                awaiting_response=ResponseExpectation(
                    characters=["Alice"],
                    response_type=ResponseType.REACTION,
                    prompt="Do you want to use Shield?"
                )
            )

        assert response.awaiting_response.characters == ["Alice"]
        assert response.awaiting_response.response_type == ResponseType.REACTION

    def test_dm_response_filters_unknown_characters(self):
        """DM response filters unknown characters in expectation."""
        with character_registry_context({"Alice", "Bob"}):
            response = DungeonMasterResponse(
                narrative="Everyone roll for initiative!",
                game_step_completed=False,
                awaiting_response=ResponseExpectation(
                    characters=["Alice", "Bob", "Goblin1"],
                    response_type=ResponseType.INITIATIVE  # Allows unknown
                )
            )

        # Initiative allows all (including enemies)
        assert "Goblin1" in response.awaiting_response.characters

    def test_dm_response_with_saving_throw(self):
        """DM response with saving throw expectation."""
        with character_registry_context({"Alice", "Bob"}):
            response = DungeonMasterResponse(
                narrative="A fireball explodes!",
                game_step_completed=False,
                awaiting_response=ResponseExpectation(
                    characters=["Alice", "Bob"],
                    response_type=ResponseType.SAVING_THROW,
                    prompt="Roll DEX save DC 15"
                )
            )

        assert response.awaiting_response.get_collection_mode() == "all"
        assert response.awaiting_response.prompt == "Roll DEX save DC 15"


class TestEndToEndFlow:
    """Test end-to-end flow scenarios."""

    def test_action_turn_flow(self):
        """Test typical action turn flow."""
        # 1. Create coordinator in combat mode
        coordinator = create_message_coordinator()
        coordinator.enter_combat_mode()

        # 2. DM sets expectation for Alice's turn
        with character_registry_context({"Alice", "Bob"}):
            expectation = ResponseExpectation(
                characters=["Alice"],
                response_type=ResponseType.ACTION
            )
        coordinator.set_expectation(expectation)

        # 3. Alice's message is valid
        result = coordinator.validate_responder("Alice")
        assert result.result == MessageValidationResult.VALID

        # 4. Bob's message is invalid
        result = coordinator.validate_responder("Bob")
        assert result.result == MessageValidationResult.INVALID_NOT_YOUR_TURN

    def test_saving_throw_flow(self):
        """Test saving throw collection flow."""
        # 1. Create collector for saves (SAVING_THROW uses ALL mode)
        expectation = ResponseExpectation(
            characters=["Alice", "Bob"],
            response_type=ResponseType.SAVING_THROW
        )
        collector = create_response_collector(expectation)

        # 2. Collect responses
        collector.add_response("Alice", "I rolled 18")
        assert not collector.is_complete()

        collector.add_response("Bob", "I rolled 7")
        assert collector.is_complete()

        # 3. Get results
        assert len(collector.collected) == 2

    @pytest.mark.asyncio
    async def test_reaction_window_flow(self):
        """Test reaction window flow."""
        from src.discord.views.reaction_view import ReactionView

        # 1. Create reaction view
        view = ReactionView(
            expected_characters=["Alice", "Bob"],
            prompt="Opportunity attack?",
            timeout=30.0
        )

        # 2. Alice passes
        view.passed.add("Alice")
        assert not view._check_complete()

        # 3. Bob uses reaction
        view.reactions["Bob"] = {"type": "declared"}
        assert view._check_complete()

        # 4. Get results
        results = view.get_results()
        assert results["passed"] == ["Alice"]
        assert "Bob" in results["reactions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

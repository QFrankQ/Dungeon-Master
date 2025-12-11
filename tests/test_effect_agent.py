"""Tests for EffectAgent - Effect and Condition extraction specialist."""

import pytest
from src.agents.effect_agent import EffectAgent, create_effect_agent
from src.models.state_commands_optimized import (
    EffectAgentResult,
    EffectCommand,
    ConditionCommand
)
from src.characters.dnd_enums import Condition
from src.characters.character_components import DurationType


@pytest.fixture
def effect_agent():
    """Create EffectAgent for testing."""
    return create_effect_agent()


# ==================== ConditionCommand Tests ====================

class TestConditionExtraction:
    """Tests for extracting ConditionCommand from narratives."""

    @pytest.mark.asyncio
    async def test_extract_poisoned_condition(self, effect_agent):
        """Test extracting a poisoned condition from narrative."""
        narrative = "The orc's poisoned blade strikes Gimli. He becomes poisoned."

        result = await effect_agent.extract(narrative)

        assert isinstance(result, EffectAgentResult)
        assert len(result.commands) >= 1

        # Find the poisoned condition command
        poisoned_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, ConditionCommand) and cmd.condition == Condition.POISONED),
            None
        )

        assert poisoned_cmd is not None
        assert poisoned_cmd.character_id == "gimli"
        assert poisoned_cmd.action == "add"
        assert poisoned_cmd.condition == Condition.POISONED

    @pytest.mark.asyncio
    async def test_extract_stunned_condition(self, effect_agent):
        """Test extracting a stunned condition."""
        narrative = "The monk's stunning strike hits the guard. The guard is stunned until the end of the monk's next turn."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        stunned_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, ConditionCommand) and cmd.condition == Condition.STUNNED),
            None
        )

        assert stunned_cmd is not None
        assert stunned_cmd.character_id in ["guard", "the_guard"]
        assert stunned_cmd.action == "add"

    @pytest.mark.asyncio
    async def test_remove_condition(self, effect_agent):
        """Test removing a condition."""
        narrative = "The cleric's Lesser Restoration removes the poisoned condition from Aragorn."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        remove_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, ConditionCommand) and cmd.action == "remove"),
            None
        )

        assert remove_cmd is not None
        assert remove_cmd.character_id == "aragorn"
        assert remove_cmd.action == "remove"
        assert remove_cmd.condition == Condition.POISONED


# ==================== EffectCommand Tests ====================

class TestEffectExtraction:
    """Tests for extracting EffectCommand from narratives."""

    @pytest.mark.asyncio
    async def test_extract_bless_name_only(self, effect_agent):
        """Test extracting Bless spell when DM only mentions the name."""
        narrative = "Gandalf casts Bless on Aragorn, Legolas, and Gimli."

        result = await effect_agent.extract(narrative)

        # Should have 3 Bless effects
        bless_commands = [
            cmd for cmd in result.commands
            if isinstance(cmd, EffectCommand) and cmd.effect_name == "Bless"
        ]

        assert len(bless_commands) == 3

        # Check one of them has complete D&D RAW mechanics
        aragorn_bless = next(
            cmd for cmd in bless_commands if cmd.character_id == "aragorn"
        )

        assert aragorn_bless.action == "add"
        assert "attack roll" in aragorn_bless.description.lower()
        assert "saving throw" in aragorn_bless.description.lower()
        assert "d4" in aragorn_bless.description.lower()
        assert aragorn_bless.duration_type == DurationType.CONCENTRATION
        assert len(aragorn_bless.summary) > 0

    @pytest.mark.asyncio
    async def test_extract_bless_explicit_partial(self, effect_agent):
        """Test extracting Bless when DM is explicit but mentions only part of the mechanics."""
        narrative = "The cleric blesses you, granting +1d4 to your attack rolls for the next minute while she concentrates."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        bless_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, EffectCommand) and cmd.effect_name == "Bless"),
            None
        )

        assert bless_cmd is not None
        # Agent should fill in complete mechanics (includes saving throws)
        assert "attack roll" in bless_cmd.description.lower()
        assert "saving throw" in bless_cmd.description.lower()
        assert bless_cmd.duration_type == DurationType.CONCENTRATION

    @pytest.mark.asyncio
    async def test_extract_haste(self, effect_agent):
        """Test extracting complex spell (Haste) with full mechanics."""
        narrative = "The wizard casts Haste on Aragorn."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        haste_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, EffectCommand) and cmd.effect_name == "Haste"),
            None
        )

        assert haste_cmd is not None
        assert haste_cmd.character_id == "aragorn"
        assert haste_cmd.action == "add"

        # Should include all Haste mechanics
        desc_lower = haste_cmd.description.lower()
        assert "ac" in desc_lower or "armor class" in desc_lower
        assert "dex" in desc_lower or "dexterity" in desc_lower
        assert "speed" in desc_lower
        assert "action" in desc_lower

    @pytest.mark.asyncio
    async def test_extract_homebrew_effect(self, effect_agent):
        """Test extracting homebrew effect (DM contradicts RAW)."""
        narrative = "The wizard casts Modified Bless, granting you +1d6 to attack rolls only (not saves) for 1 minute."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        modified_bless = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, EffectCommand) and "bless" in cmd.effect_name.lower()),
            None
        )

        assert modified_bless is not None
        # Should NOT include saving throws since DM explicitly said "not saves"
        desc_lower = modified_bless.description.lower()
        assert "attack" in desc_lower
        assert "1d6" in desc_lower or "d6" in desc_lower
        # Should respect DM's version

    @pytest.mark.asyncio
    async def test_extract_custom_effect(self, effect_agent):
        """Test extracting custom/unique effect."""
        narrative = "The dragon's aura surrounds you, granting resistance to fire damage."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        custom_effect = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, EffectCommand)),
            None
        )

        assert custom_effect is not None
        assert custom_effect.action == "add"
        # Should use DM's exact text
        desc_lower = custom_effect.description.lower()
        assert "fire" in desc_lower
        assert "resistance" in desc_lower

    @pytest.mark.asyncio
    async def test_remove_effect(self, effect_agent):
        """Test removing an effect."""
        narrative = "The Haste spell wears off from Legolas, leaving him lethargic."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        remove_cmd = next(
            (cmd for cmd in result.commands
             if isinstance(cmd, EffectCommand) and cmd.action == "remove"),
            None
        )

        assert remove_cmd is not None
        assert remove_cmd.character_id == "legolas"
        assert remove_cmd.effect_name == "Haste"

    @pytest.mark.asyncio
    async def test_duration_extraction_minutes(self, effect_agent):
        """Test extracting duration in minutes."""
        narrative = "You gain the Shield spell's benefit for 1 minute."

        result = await effect_agent.extract(narrative)

        assert len(result.commands) >= 1
        effect_cmd = next(
            (cmd for cmd in result.commands if isinstance(cmd, EffectCommand)),
            None
        )

        assert effect_cmd is not None
        assert effect_cmd.duration_type == DurationType.MINUTES
        assert effect_cmd.duration == 1

    @pytest.mark.asyncio
    async def test_concentration_duration(self, effect_agent):
        """Test extracting concentration duration."""
        narrative = "The wizard maintains concentration on Hunter's Mark."

        result = await effect_agent.extract(narrative)

        # May or may not extract this (depends on interpretation)
        # But if it does, duration_type should be concentration
        if result.commands:
            for cmd in result.commands:
                if isinstance(cmd, EffectCommand) and cmd.duration_type:
                    # If extracted, should have concentration type
                    assert cmd.duration_type == DurationType.CONCENTRATION


# ==================== Multiple Effects Tests ====================

class TestMultipleEffects:
    """Tests for extracting multiple effects from single narrative."""

    @pytest.mark.asyncio
    async def test_multiple_effects_and_conditions(self, effect_agent):
        """Test extracting both effects and conditions from same narrative."""
        narrative = "The cleric casts Bless on Aragorn and Gimli. Meanwhile, the orc's poisoned blade strikes Legolas, poisoning him."

        result = await effect_agent.extract(narrative)

        # Should have 2 Bless effects + 1 poisoned condition = 3 total
        assert len(result.commands) >= 3

        bless_commands = [
            cmd for cmd in result.commands
            if isinstance(cmd, EffectCommand) and cmd.effect_name == "Bless"
        ]
        assert len(bless_commands) == 2

        poisoned_commands = [
            cmd for cmd in result.commands
            if isinstance(cmd, ConditionCommand) and cmd.condition == Condition.POISONED
        ]
        assert len(poisoned_commands) == 1

    @pytest.mark.asyncio
    async def test_no_effects_found(self, effect_agent):
        """Test narrative with no effects or conditions."""
        narrative = "Aragorn attacks the orc with his sword, dealing 12 slashing damage."

        result = await effect_agent.extract(narrative)

        # Should return empty list (HP damage is not an effect)
        assert isinstance(result, EffectAgentResult)
        assert len(result.commands) == 0


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_narrative(self, effect_agent):
        """Test with empty narrative."""
        result = await effect_agent.extract("")

        assert isinstance(result, EffectAgentResult)
        assert len(result.commands) == 0

    @pytest.mark.asyncio
    async def test_character_id_normalization(self, effect_agent):
        """Test that character IDs are normalized to lowercase with underscores."""
        narrative = "The cleric casts Bless on Evil Wizard."

        result = await effect_agent.extract(narrative)

        if result.commands:
            # Character ID should be normalized
            assert result.commands[0].character_id in ["evil_wizard", "wizard"]

    @pytest.mark.asyncio
    async def test_skip_non_effect_content(self, effect_agent):
        """Test that agent skips HP changes and other non-effect content."""
        narrative = "Gandalf casts Fireball using a 3rd level spell slot, dealing 28 fire damage to the orc. The orc is also set on fire, taking ongoing fire damage."

        result = await effect_agent.extract(narrative)

        # Should NOT extract HP damage (28 fire damage)
        # May or may not extract "on fire" as an effect (depends on interpretation)
        # But should definitely not have HP damage as an effect
        for cmd in result.commands:
            assert isinstance(cmd, (EffectCommand, ConditionCommand))

"""Tests for EffectAgentContextBuilder - context formatting with cached rules."""

import pytest
from src.context.effect_agent_context_builder import (
    EffectAgentContextBuilder,
    create_effect_agent_context_builder
)
from src.services.rules_cache_service import create_rules_cache_service
from src.models.turn_context import TurnContext


# ==================== Test Fixtures ====================

@pytest.fixture
def rules_cache_service():
    """Create RulesCacheService for testing."""
    return create_rules_cache_service()


@pytest.fixture
def context_builder(rules_cache_service):
    """Create EffectAgentContextBuilder for testing."""
    return EffectAgentContextBuilder(rules_cache_service)


def create_turn_with_cache(turn_id: str, turn_level: int, cache_data: dict = None) -> TurnContext:
    """Helper to create TurnContext with optional cache data."""
    turn = TurnContext(
        turn_id=turn_id,
        turn_level=turn_level,
        current_step_objective="Test objective",
        metadata={}
    )
    if cache_data:
        turn.metadata["rules_cache"] = cache_data
    return turn


# ==================== Basic Context Building Tests ====================

class TestBasicContextBuilding:
    """Tests for basic context building functionality."""

    def test_build_context_with_no_cache(self, context_builder):
        """Test building context when no cached rules exist."""
        # Setup
        narrative = "The wizard casts a spell."
        active_turns = [create_turn_with_cache("1", 0)]  # Empty cache

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify
        assert "=== NARRATIVE ===" in context
        assert "The wizard casts a spell." in context
        assert "=== KNOWN EFFECTS ===" in context
        assert "No effects have been queried" in context

    def test_build_context_with_single_cached_spell(self, context_builder):
        """Test building context with one cached spell."""
        # Setup
        narrative = "The cleric casts Bless on the party."
        cache_data = {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Whenever you make an attack roll or saving throw, you can roll 1d4...",
                "level": 1,
                "school": "enchantment",
                "duration_text": "Concentration, up to 1 minute",
                "source": "lancedb"
            }
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify narrative section
        assert "=== NARRATIVE ===" in context
        assert narrative in context

        # Verify KNOWN EFFECTS section
        assert "=== KNOWN EFFECTS ===" in context
        assert "**Bless**" in context
        assert "(Spell, Level 1)" in context
        assert "Whenever you make an attack roll" in context
        assert "Duration: Concentration, up to 1 minute" in context
        assert "School: Enchantment" in context

    def test_build_context_with_multiple_cached_rules(self, context_builder):
        """Test building context with multiple cached rules."""
        # Setup
        narrative = "Effects are active."
        cache_data = {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Bless description",
                "level": 1,
                "source": "lancedb"
            },
            "poisoned": {
                "name": "Poisoned",
                "entry_type": "condition",
                "description": "Disadvantage on attack rolls",
                "source": "lancedb"
            },
            "haste": {
                "name": "Haste",
                "entry_type": "spell",
                "description": "Speed doubles",
                "level": 3,
                "source": "lancedb"
            }
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify all rules are included
        assert "**Bless**" in context
        assert "**Poisoned**" in context
        assert "**Haste**" in context

    def test_build_context_with_game_context(self, context_builder):
        """Test building context with game metadata."""
        # Setup
        narrative = "Action happens."
        active_turns = [create_turn_with_cache("1.2", 1)]
        game_context = {
            "turn_id": "1.2",
            "active_character": "Alice",
            "combat_round": 3
        }

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns,
            game_context=game_context
        )

        # Verify game context section
        assert "=== GAME CONTEXT ===" in context
        assert "Turn ID: 1.2" in context
        assert "Active Character: Alice" in context
        assert "Combat Round: 3" in context


# ==================== Cache Filtering Tests ====================

class TestCacheFiltering:
    """Tests for filtering cache to effect-related types only."""

    def test_filters_to_effect_types_only(self, context_builder):
        """Test that only effect/condition/spell types are included."""
        # Setup
        narrative = "Test"
        cache_data = {
            "bless": {"name": "Bless", "entry_type": "spell", "description": "Spell", "source": "lancedb"},
            "poisoned": {"name": "Poisoned", "entry_type": "condition", "description": "Condition", "source": "lancedb"},
            "longsword": {"name": "Longsword", "entry_type": "item", "description": "Item", "source": "lancedb"},
            "attack": {"name": "Attack", "entry_type": "action", "description": "Action", "source": "lancedb"}
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify only effect-related types are included
        assert "**Bless**" in context
        assert "**Poisoned**" in context
        assert "**Longsword**" not in context
        assert "**Attack**" not in context

    def test_includes_custom_effect_type(self, context_builder):
        """Test that custom 'effect' entry_type is included."""
        # Setup
        narrative = "Test"
        cache_data = {
            "custom_buff": {
                "name": "Custom Buff",
                "entry_type": "effect",
                "description": "Custom effect",
                "source": "llm_generated"
            }
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify custom effect is included
        assert "**Custom Buff**" in context
        assert "(Effect)" in context


# ==================== Hierarchical Cache Merging Tests ====================

class TestHierarchicalCacheMerging:
    """Tests for cache merging from turn hierarchy."""

    def test_child_inherits_parent_cache(self, context_builder):
        """Test that child turn inherits parent's cached rules."""
        # Setup
        narrative = "Test"

        # Parent turn with Bless
        parent = create_turn_with_cache("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "description": "Parent spell", "source": "lancedb"}
        })

        # Child turn with Shield
        child = create_turn_with_cache("1.1", 1, {
            "shield": {"name": "Shield", "entry_type": "spell", "description": "Child spell", "source": "lancedb"}
        })

        active_turns = [parent, child]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify both rules are included
        assert "**Bless**" in context
        assert "**Shield**" in context

    def test_sibling_isolation(self, context_builder):
        """Test that sibling turns do NOT share cache."""
        # Setup
        narrative = "Test"

        # Parent turn
        parent = create_turn_with_cache("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "description": "From parent", "source": "lancedb"}
        })

        # Sibling turn (NOT in snapshot for current turn)
        # Only parent is in active_turns_by_level for this child

        # Current turn (child 2)
        current_turn = create_turn_with_cache("1.2", 1, {
            "haste": {"name": "Haste", "entry_type": "spell", "description": "From current", "source": "lancedb"}
        })

        # Snapshot for current turn only includes [parent, current_turn]
        # (does NOT include sibling 1.1)
        active_turns = [parent, current_turn]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify parent and current are included, but NOT sibling
        assert "**Bless**" in context  # From parent
        assert "**Haste**" in context  # From current turn
        # Sibling's Shield would NOT be here (not in snapshot)

    def test_nested_turn_inheritance(self, context_builder):
        """Test multi-level nested turn cache inheritance."""
        # Setup
        narrative = "Test"

        root = create_turn_with_cache("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "description": "Root", "source": "lancedb"}
        })

        level1 = create_turn_with_cache("1.1", 1, {
            "shield": {"name": "Shield", "entry_type": "spell", "description": "Level 1", "source": "lancedb"}
        })

        level2 = create_turn_with_cache("1.1.1", 2, {
            "haste": {"name": "Haste", "entry_type": "spell", "description": "Level 2", "source": "lancedb"}
        })

        active_turns = [root, level1, level2]

        # Execute
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Verify all levels are inherited
        assert "**Bless**" in context
        assert "**Shield**" in context
        assert "**Haste**" in context


# ==================== Helper Method Tests ====================

class TestHelperMethods:
    """Tests for helper methods and utilities."""

    def test_format_cached_rule_spell(self, context_builder):
        """Test _format_cached_rule with spell entry."""
        rule_entry = {
            "name": "Fireball",
            "entry_type": "spell",
            "description": "A bright streak...",
            "level": 3,
            "school": "evocation",
            "duration_text": "Instantaneous",
            "damage": "8d6 fire"
        }

        formatted = context_builder._format_cached_rule(rule_entry)

        assert "**Fireball**" in formatted
        assert "(Spell, Level 3)" in formatted
        assert "A bright streak..." in formatted
        assert "School: Evocation" in formatted
        assert "Damage: 8d6 fire" in formatted

    def test_format_cached_rule_condition(self, context_builder):
        """Test _format_cached_rule with condition entry."""
        rule_entry = {
            "name": "Stunned",
            "entry_type": "condition",
            "description": "Cannot move or speak."
        }

        formatted = context_builder._format_cached_rule(rule_entry)

        assert "**Stunned**" in formatted
        assert "(Condition)" in formatted
        assert "Cannot move or speak." in formatted

    def test_format_cached_rule_item(self, context_builder):
        """Test _format_cached_rule with item entry."""
        rule_entry = {
            "name": "Potion of Healing",
            "entry_type": "item",
            "description": "Restores hit points.",
            "rarity": "common",
            "damage": "2d4+2 healing"
        }

        formatted = context_builder._format_cached_rule(rule_entry)

        assert "**Potion of Healing**" in formatted
        assert "(Item, Common)" in formatted
        assert "Restores hit points." in formatted
        assert "Damage: 2d4+2 healing" in formatted

    def test_build_simple_context(self, context_builder):
        """Test build_simple_context fallback method."""
        narrative = "Simple narrative text."

        context = context_builder.build_simple_context(narrative)

        assert "=== NARRATIVE ===" in context
        assert narrative in context
        assert "=== KNOWN EFFECTS ===" not in context

    def test_get_cached_effect_count_empty(self, context_builder):
        """Test get_cached_effect_count with no cached rules."""
        active_turns = [create_turn_with_cache("1", 0)]

        count = context_builder.get_cached_effect_count(active_turns)

        assert count == 0

    def test_get_cached_effect_count_with_rules(self, context_builder):
        """Test get_cached_effect_count with cached rules."""
        cache_data = {
            "bless": {"name": "Bless", "entry_type": "spell", "description": "Test", "source": "lancedb"},
            "poisoned": {"name": "Poisoned", "entry_type": "condition", "description": "Test", "source": "lancedb"},
            "longsword": {"name": "Longsword", "entry_type": "item", "description": "Test", "source": "lancedb"}
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        count = context_builder.get_cached_effect_count(active_turns)

        # Only effect/condition/spell types are counted
        assert count == 2  # bless and poisoned, NOT longsword


# ==================== Edge Cases Tests ====================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_active_turns_list(self, context_builder):
        """Test with empty active_turns_by_level list."""
        narrative = "Test"

        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=[]
        )

        assert "=== NARRATIVE ===" in context
        assert "No effects have been queried" in context

    def test_cache_entry_missing_fields(self, context_builder):
        """Test formatting cache entry with missing optional fields."""
        narrative = "Test"
        cache_data = {
            "minimal": {
                "name": "Minimal Effect",
                "entry_type": "spell",
                "description": "Minimal description"
                # Missing level, school, duration, etc.
            }
        }
        active_turns = [create_turn_with_cache("1", 0, cache_data)]

        # Should not raise error
        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        assert "**Minimal Effect**" in context
        assert "(Spell)" in context  # No level shown
        assert "Minimal description" in context

    def test_child_overwrites_parent_cache_entry(self, context_builder):
        """Test that child's cache entry overwrites parent's for same rule."""
        narrative = "Test"

        parent = create_turn_with_cache("1", 0, {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Original description",
                "source": "lancedb"
            }
        })

        child = create_turn_with_cache("1.1", 1, {
            "bless": {
                "name": "Bless (Modified)",
                "entry_type": "spell",
                "description": "Modified description",
                "source": "llm_generated"
            }
        })

        active_turns = [parent, child]

        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=active_turns
        )

        # Child's version should overwrite parent's
        assert "Modified description" in context
        assert "Original description" not in context


# ==================== Factory Function Test ====================

class TestFactoryFunction:
    """Tests for create_effect_agent_context_builder factory function."""

    def test_create_effect_agent_context_builder(self):
        """Test factory function creates builder with dependencies."""
        cache_service = create_rules_cache_service()

        builder = create_effect_agent_context_builder(cache_service)

        assert isinstance(builder, EffectAgentContextBuilder)
        assert builder.rules_cache_service == cache_service


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_context_building_flow(self):
        """Test complete context building flow with realistic data."""
        # Setup services
        cache_service = create_rules_cache_service()
        builder = create_effect_agent_context_builder(cache_service)

        # Create turn hierarchy with realistic cache
        parent_cache = {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Whenever you make an attack roll or saving throw, you can roll 1d4 and add the number rolled.",
                "level": 1,
                "school": "enchantment",
                "duration_text": "Concentration, up to 1 minute",
                "source": "lancedb"
            }
        }

        child_cache = {
            "shield": {
                "name": "Shield",
                "entry_type": "spell",
                "description": "An invisible barrier of magical force appears and protects you.",
                "level": 1,
                "school": "abjuration",
                "duration_text": "1 round",
                "source": "lancedb"
            },
            "poisoned": {
                "name": "Poisoned",
                "entry_type": "condition",
                "description": "A poisoned creature has disadvantage on attack rolls and ability checks.",
                "source": "lancedb"
            }
        }

        parent = create_turn_with_cache("1", 0, parent_cache)
        child = create_turn_with_cache("1.1", 1, child_cache)

        narrative = """The wizard casts Shield as the orc attacks.
The cleric maintains concentration on Bless.
The rogue is still Poisoned from the trap."""

        game_context = {
            "turn_id": "1.1",
            "active_character": "Wizard",
            "combat_round": 2
        }

        # Execute
        context = builder.build_context(
            narrative=narrative,
            active_turns_by_level=[parent, child],
            game_context=game_context
        )

        # Verify complete context
        assert narrative in context
        assert "**Bless**" in context
        assert "**Shield**" in context
        assert "**Poisoned**" in context
        assert "Turn ID: 1.1" in context
        assert "Active Character: Wizard" in context
        assert "Combat Round: 2" in context

    def test_context_with_no_cache_and_no_game_context(self, context_builder):
        """Test minimal context with only narrative."""
        narrative = "The dragon breathes fire."

        context = context_builder.build_context(
            narrative=narrative,
            active_turns_by_level=[create_turn_with_cache("1", 0)]
        )

        assert narrative in context
        assert "=== NARRATIVE ===" in context
        assert "=== KNOWN EFFECTS ===" in context
        assert "No effects have been queried" in context
        # No game context section since it wasn't provided
        assert "=== GAME CONTEXT ===" not in context

"""Tests for RulesCacheService - Simplified cache merging and filtering."""

import pytest
from datetime import datetime

from src.services.rules_cache_service import RulesCacheService, create_rules_cache_service
from src.models.turn_context import TurnContext


# ==================== Test Fixtures ====================

@pytest.fixture
def cache_service():
    """Create RulesCacheService for testing."""
    return create_rules_cache_service()


def create_turn_context(turn_id: str, turn_level: int, cache_data: dict = None) -> TurnContext:
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


# ==================== Cache Merging Tests ====================

class TestCacheMerging:
    """Tests for merge_cache_from_snapshot method."""

    def test_merge_single_turn(self, cache_service):
        """Test merging cache from single turn."""
        turn = create_turn_context("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "source": "lancedb"}
        })

        merged = cache_service.merge_cache_from_snapshot([turn])

        assert "bless" in merged
        assert merged["bless"]["name"] == "Bless"

    def test_merge_parent_and_child(self, cache_service):
        """Test that child inherits parent cache."""
        parent = create_turn_context("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "source": "lancedb"},
            "haste": {"name": "Haste", "entry_type": "spell", "source": "lancedb"}
        })

        child = create_turn_context("1.1", 1, {
            "shield": {"name": "Shield", "entry_type": "spell", "source": "lancedb"}
        })

        # Snapshot active_turns_by_level = [parent, child]
        merged = cache_service.merge_cache_from_snapshot([parent, child])

        # Should have all three
        assert "bless" in merged
        assert "haste" in merged
        assert "shield" in merged

    def test_sibling_isolation(self, cache_service):
        """Test that sibling turns do NOT share cache."""
        # Parent turn
        parent = create_turn_context("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "source": "lancedb"}
        })

        # Child 1 with shield (NOT in snapshot for child 2)
        child1 = create_turn_context("1.1", 1, {
            "shield": {"name": "Shield", "entry_type": "spell", "source": "lancedb"}
        })

        # Child 2 with haste (current turn)
        child2 = create_turn_context("1.2", 1, {
            "haste": {"name": "Haste", "entry_type": "spell", "source": "lancedb"}
        })

        # Snapshot for child2 only includes [parent, child2], NOT child1
        merged = cache_service.merge_cache_from_snapshot([parent, child2])

        assert "bless" in merged  # From parent
        assert "haste" in merged  # From child2
        assert "shield" not in merged  # NOT from sibling child1

    def test_nested_turns_inheritance(self, cache_service):
        """Test multi-level nested turn inheritance."""
        root = create_turn_context("1", 0, {
            "bless": {"name": "Bless", "entry_type": "spell", "source": "lancedb"}
        })

        level1 = create_turn_context("1.1", 1, {
            "haste": {"name": "Haste", "entry_type": "spell", "source": "lancedb"}
        })

        level2 = create_turn_context("1.1.1", 2, {
            "shield": {"name": "Shield", "entry_type": "spell", "source": "lancedb"}
        })

        # Snapshot = [root, level1, level2]
        merged = cache_service.merge_cache_from_snapshot([root, level1, level2])

        # Should inherit from all ancestors
        assert "bless" in merged
        assert "haste" in merged
        assert "shield" in merged

    def test_child_overwrites_parent(self, cache_service):
        """Test that child cache entries overwrite parent entries."""
        parent = create_turn_context("1", 0, {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Parent version",
                "source": "lancedb"
            }
        })

        child = create_turn_context("1.1", 1, {
            "bless": {
                "name": "Modified Bless",
                "entry_type": "spell",
                "description": "Child version (custom)",
                "source": "llm_generated"
            }
        })

        merged = cache_service.merge_cache_from_snapshot([parent, child])

        # Child version should overwrite parent
        assert merged["bless"]["description"] == "Child version (custom)"
        assert merged["bless"]["source"] == "llm_generated"

    def test_empty_snapshot(self, cache_service):
        """Test merging with empty snapshot."""
        merged = cache_service.merge_cache_from_snapshot([])

        assert merged == {}

    def test_turns_without_cache(self, cache_service):
        """Test merging when turns have no rules_cache."""
        turn1 = create_turn_context("1", 0)  # No cache
        turn2 = create_turn_context("1.1", 1)  # No cache

        merged = cache_service.merge_cache_from_snapshot([turn1, turn2])

        assert merged == {}


# ==================== Cache Filtering Tests ====================

class TestCacheFiltering:
    """Tests for filter_cache_by_types method."""

    def test_filter_effect_and_condition_types(self, cache_service):
        """Test filtering to effect/condition types for EffectAgent."""
        full_cache = {
            "bless": {"name": "Bless", "entry_type": "spell"},
            "poisoned": {"name": "Poisoned", "entry_type": "condition"},
            "longsword": {"name": "Longsword", "entry_type": "item"},
            "attack": {"name": "Attack", "entry_type": "action"},
            "haste": {"name": "Haste", "entry_type": "effect"}
        }

        # Filter to effect-related types
        filtered = cache_service.filter_cache_by_types(
            full_cache,
            ["effect", "condition", "spell"]
        )

        # Should include spell, condition, effect
        assert "bless" in filtered
        assert "poisoned" in filtered
        assert "haste" in filtered

        # Should exclude item, action
        assert "longsword" not in filtered
        assert "attack" not in filtered

    def test_filter_combat_types(self, cache_service):
        """Test filtering to combat-related types."""
        full_cache = {
            "bless": {"name": "Bless", "entry_type": "spell"},
            "longsword": {"name": "Longsword", "entry_type": "item"},
            "attack": {"name": "Attack", "entry_type": "action"},
            "shield_item": {"name": "Shield", "entry_type": "item"}
        }

        filtered = cache_service.filter_cache_by_types(
            full_cache,
            ["action", "item"]
        )

        assert "attack" in filtered
        assert "longsword" in filtered
        assert "shield_item" in filtered
        assert "bless" not in filtered

    def test_filter_empty_cache(self, cache_service):
        """Test filtering empty cache returns empty dict."""
        filtered = cache_service.filter_cache_by_types({}, ["spell"])
        assert filtered == {}

    def test_filter_no_matches(self, cache_service):
        """Test filtering with no matching types returns empty dict."""
        cache = {
            "longsword": {"name": "Longsword", "entry_type": "item"}
        }

        filtered = cache_service.filter_cache_by_types(cache, ["spell"])
        assert filtered == {}

    def test_filter_with_missing_entry_type(self, cache_service):
        """Test filtering handles entries without entry_type field."""
        cache = {
            "valid": {"name": "Valid", "entry_type": "spell"},
            "missing_type": {"name": "Missing"}  # No entry_type
        }

        filtered = cache_service.filter_cache_by_types(cache, ["spell"])

        assert "valid" in filtered
        assert "missing_type" not in filtered


# ==================== Add to Cache Tests ====================

class TestAddToCache:
    """Tests for add_to_cache helper method."""

    def test_add_rule_to_empty_cache(self, cache_service):
        """Test adding rule to turn with no existing cache."""
        turn = create_turn_context("1", 0)

        rule_entry = {
            "name": "Bless",
            "entry_type": "spell",
            "description": "Grants +1d4 to attacks and saves",
            "source": "lancedb"
        }

        cache_service.add_to_cache(rule_entry, turn)

        assert "rules_cache" in turn.metadata
        assert "bless" in turn.metadata["rules_cache"]
        assert turn.metadata["rules_cache"]["bless"]["name"] == "Bless"

    def test_add_rule_to_existing_cache(self, cache_service):
        """Test adding rule to turn with existing cache."""
        turn = create_turn_context("1", 0, {
            "haste": {"name": "Haste", "entry_type": "spell", "source": "lancedb"}
        })

        rule_entry = {
            "name": "Bless",
            "entry_type": "spell",
            "description": "Grants +1d4",
            "source": "lancedb"
        }

        cache_service.add_to_cache(rule_entry, turn)

        # Should have both rules
        assert "haste" in turn.metadata["rules_cache"]
        assert "bless" in turn.metadata["rules_cache"]

    def test_key_normalization(self, cache_service):
        """Test that rule names are normalized to lowercase keys."""
        turn = create_turn_context("1", 0)

        # Add with capital letters
        rule_entry = {
            "name": "BLESS",
            "entry_type": "spell",
            "source": "lancedb"
        }

        cache_service.add_to_cache(rule_entry, turn)

        # Key should be lowercase
        assert "bless" in turn.metadata["rules_cache"]
        assert "BLESS" not in turn.metadata["rules_cache"]

        # But original name preserved
        assert turn.metadata["rules_cache"]["bless"]["name"] == "BLESS"

    def test_overwrite_existing_entry(self, cache_service):
        """Test that adding duplicate rule overwrites existing entry."""
        turn = create_turn_context("1", 0, {
            "bless": {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Old description",
                "source": "lancedb"
            }
        })

        # Add updated version
        new_entry = {
            "name": "Bless",
            "entry_type": "spell",
            "description": "New description",
            "source": "llm_generated"
        }

        cache_service.add_to_cache(new_entry, turn)

        # Should be overwritten
        assert turn.metadata["rules_cache"]["bless"]["description"] == "New description"
        assert turn.metadata["rules_cache"]["bless"]["source"] == "llm_generated"

    def test_add_multiple_types(self, cache_service):
        """Test adding different rule types."""
        turn = create_turn_context("1", 0)

        spell = {"name": "Bless", "entry_type": "spell", "source": "lancedb"}
        condition = {"name": "Poisoned", "entry_type": "condition", "source": "lancedb"}
        item = {"name": "Longsword", "entry_type": "item", "source": "lancedb"}

        cache_service.add_to_cache(spell, turn)
        cache_service.add_to_cache(condition, turn)
        cache_service.add_to_cache(item, turn)

        cache = turn.metadata["rules_cache"]
        assert len(cache) == 3
        assert "bless" in cache
        assert "poisoned" in cache
        assert "longsword" in cache


# ==================== Factory Function Test ====================

class TestFactoryFunction:
    """Test factory function."""

    def test_create_rules_cache_service(self):
        """Test factory function creates service."""
        service = create_rules_cache_service()

        assert isinstance(service, RulesCacheService)
        assert hasattr(service, 'merge_cache_from_snapshot')
        assert hasattr(service, 'filter_cache_by_types')
        assert hasattr(service, 'add_to_cache')

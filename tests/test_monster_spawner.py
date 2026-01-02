"""
Tests for MonsterSpawner service.

This test suite verifies:
1. Template discovery and loading from catalog
2. Monster spawning with unique IDs
3. Available monsters context generation
4. Integration with StateManager
5. Error handling for invalid monster types
"""

import pytest
from pathlib import Path
from typing import Dict

from src.services.monster_spawner import MonsterSpawner, MonsterSummary, create_monster_spawner
from src.memory.state_manager import StateManager
from src.characters.monster import Monster


# ==================== Test Fixtures ====================


@pytest.fixture
def state_manager(tmp_path):
    """Create a StateManager instance for testing."""
    return StateManager(character_data_path=str(tmp_path), enable_logging=False)


@pytest.fixture
def monster_spawner(state_manager):
    """Create a MonsterSpawner with the real template catalog."""
    return create_monster_spawner(state_manager=state_manager)


@pytest.fixture
def mock_catalog_path(tmp_path):
    """Create a temporary catalog with mock monster templates."""
    catalog = tmp_path / "monsters"
    catalog.mkdir()

    # Create minimal goblin template
    goblin_template = """{
  "name": "Goblin",
  "meta": {
    "size": "Small",
    "type": "humanoid",
    "alignment": "Neutral Evil"
  },
  "attributes": {
    "strength": {"score": 8, "modifier": -1},
    "dexterity": {"score": 14, "modifier": 2},
    "constitution": {"score": 10, "modifier": 0},
    "intelligence": {"score": 10, "modifier": 0},
    "wisdom": {"score": 8, "modifier": -1},
    "charisma": {"score": 8, "modifier": -1}
  },
  "stats": {
    "armor_class": {"value": 15, "type": "Leather Armor, Shield"},
    "hit_points": {"average": 7, "formula": "2d6"},
    "speed": {"walk": {"value": 30, "unit": "ft"}},
    "senses": {"darkvision": 60, "passive_perception": 9},
    "languages": ["Common", "Goblin"],
    "challenge": {"rating": "1/4", "xp": 50},
    "proficiency_bonus": 2
  },
  "actions": [
    {
      "name": "Scimitar",
      "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.",
      "type": "Melee Weapon Attack",
      "attack_bonus": 4,
      "reach": {"value": 5, "unit": "ft"},
      "target": "one target",
      "damage": {"average": 5, "formula": "1d6 + 2", "type": "slashing"}
    }
  ]
}"""
    (catalog / "goblin.json").write_text(goblin_template)

    # Create minimal orc template
    orc_template = """{
  "name": "Orc",
  "meta": {
    "size": "Medium",
    "type": "humanoid",
    "alignment": "Chaotic Evil"
  },
  "attributes": {
    "strength": {"score": 16, "modifier": 3},
    "dexterity": {"score": 12, "modifier": 1},
    "constitution": {"score": 16, "modifier": 3},
    "intelligence": {"score": 7, "modifier": -2},
    "wisdom": {"score": 11, "modifier": 0},
    "charisma": {"score": 10, "modifier": 0}
  },
  "stats": {
    "armor_class": {"value": 13, "type": "Hide Armor"},
    "hit_points": {"average": 15, "formula": "2d8 + 6"},
    "speed": {"walk": {"value": 30, "unit": "ft"}},
    "senses": {"darkvision": 60, "passive_perception": 10},
    "languages": ["Common", "Orc"],
    "challenge": {"rating": "1/2", "xp": 100},
    "proficiency_bonus": 2
  },
  "special_traits": [
    {
      "name": "Aggressive",
      "description": "As a bonus action, the orc can move up to its speed toward a hostile creature that it can see."
    }
  ],
  "actions": [
    {
      "name": "Greataxe",
      "description": "Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 9 (1d12 + 3) slashing damage.",
      "type": "Melee Weapon Attack",
      "attack_bonus": 5,
      "reach": {"value": 5, "unit": "ft"},
      "target": "one target",
      "damage": {"average": 9, "formula": "1d12 + 3", "type": "slashing"}
    }
  ]
}"""
    (catalog / "orc.json").write_text(orc_template)

    return str(catalog)


@pytest.fixture
def mock_spawner(state_manager, mock_catalog_path):
    """Create a MonsterSpawner with mock catalog."""
    return MonsterSpawner(state_manager=state_manager, catalog_path=mock_catalog_path)


# ==================== Template Discovery Tests ====================


class TestTemplateDiscovery:
    """Test suite for template discovery and loading."""

    def test_get_available_monster_types_returns_list(self, monster_spawner):
        """Test that get_available_monster_types returns a list."""
        types = monster_spawner.get_available_monster_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_available_types_have_required_fields(self, monster_spawner):
        """Test that each available type has required summary fields."""
        types = monster_spawner.get_available_monster_types()

        for monster_summary in types:
            assert isinstance(monster_summary, MonsterSummary)
            assert monster_summary.type_name  # e.g., "goblin"
            assert monster_summary.display_name  # e.g., "Goblin"
            assert monster_summary.cr  # e.g., "1/4"
            assert monster_summary.size  # e.g., "Small"

    def test_template_types_match_json_files(self, mock_spawner):
        """Test that available types match JSON files in catalog."""
        types = mock_spawner.get_available_monster_types()
        type_names = [t.type_name for t in types]

        assert "goblin" in type_names
        assert "orc" in type_names
        assert len(type_names) == 2

    def test_template_caching(self, mock_spawner):
        """Test that templates are cached after first load."""
        # First access triggers load
        _ = mock_spawner.get_available_monster_types()

        # Should be cached now
        assert "goblin" in mock_spawner._template_cache
        assert "orc" in mock_spawner._template_cache


# ==================== Available Monsters Context Tests ====================


class TestAvailableMonstersContext:
    """Test suite for available monsters context generation."""

    def test_get_available_monsters_context_returns_string(self, monster_spawner):
        """Test that get_available_monsters_context returns a string."""
        context = monster_spawner.get_available_monsters_context()
        assert isinstance(context, str)

    def test_context_contains_monster_info(self, mock_spawner):
        """Test that context contains monster information."""
        context = mock_spawner.get_available_monsters_context()

        assert "goblin" in context.lower()
        assert "orc" in context.lower()
        assert "CR" in context or "cr" in context.lower()

    def test_context_includes_special_traits(self, mock_spawner):
        """Test that context includes notable special traits."""
        context = mock_spawner.get_available_monsters_context()

        # Orc has Aggressive trait
        assert "Aggressive" in context


# ==================== Monster Spawning Tests ====================


class TestMonsterSpawning:
    """Test suite for monster spawning functionality."""

    def test_spawn_single_monster(self, mock_spawner, state_manager):
        """Test spawning a single monster."""
        created_ids = mock_spawner.spawn_monsters([{"type": "goblin", "count": 1}])

        assert len(created_ids) == 1
        assert created_ids[0] == "goblin_1"
        assert "goblin_1" in state_manager.monsters

    def test_spawn_multiple_same_type(self, mock_spawner, state_manager):
        """Test spawning multiple monsters of the same type."""
        created_ids = mock_spawner.spawn_monsters([{"type": "goblin", "count": 3}])

        assert len(created_ids) == 3
        assert "goblin_1" in created_ids
        assert "goblin_2" in created_ids
        assert "goblin_3" in created_ids

        # All should be in state manager
        for monster_id in created_ids:
            assert monster_id in state_manager.monsters

    def test_spawn_mixed_types(self, mock_spawner, state_manager):
        """Test spawning monsters of different types."""
        created_ids = mock_spawner.spawn_monsters([
            {"type": "goblin", "count": 2},
            {"type": "orc", "count": 1}
        ])

        assert len(created_ids) == 3
        assert "goblin_1" in created_ids
        assert "goblin_2" in created_ids
        assert "orc_1" in created_ids

    def test_spawned_monsters_have_correct_stats(self, mock_spawner, state_manager):
        """Test that spawned monsters have correct stats from template."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 1}])

        goblin = state_manager.get_monster("goblin_1")
        assert goblin is not None
        assert goblin.name == "Goblin 1"
        assert goblin.armor_class.value == 15
        assert goblin.hit_points.average == 7
        assert goblin.hit_points.current == 7

    def test_spawned_monsters_have_unique_names(self, mock_spawner, state_manager):
        """Test that spawned monsters have unique display names."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 3}])

        names = [state_manager.get_monster(f"goblin_{i}").name for i in range(1, 4)]
        assert names == ["Goblin 1", "Goblin 2", "Goblin 3"]

    def test_spawn_increments_counter_within_call(self, mock_spawner, state_manager):
        """Test that monster counter increments within a single spawn call."""
        # Multiple monsters in same call get sequential IDs
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 3}])

        assert "goblin_1" in state_manager.monsters
        assert "goblin_2" in state_manager.monsters
        assert "goblin_3" in state_manager.monsters
        assert state_manager.get_monster("goblin_3").name == "Goblin 3"

    def test_spawn_invalid_type_raises_error(self, mock_spawner):
        """Test that spawning invalid monster type raises error."""
        with pytest.raises(ValueError) as exc_info:
            mock_spawner.spawn_monsters([{"type": "dragon", "count": 1}])

        assert "dragon" in str(exc_info.value).lower()

    def test_spawn_returns_empty_list_for_zero_count(self, mock_spawner):
        """Test that spawning with count 0 returns empty list."""
        created_ids = mock_spawner.spawn_monsters([{"type": "goblin", "count": 0}])
        assert created_ids == []


# ==================== Spawned Summary Tests ====================


class TestSpawnedSummary:
    """Test suite for spawned monster summary generation."""

    def test_get_spawned_summary_returns_string(self, mock_spawner):
        """Test that get_spawned_summary returns a string."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 1}])
        summary = mock_spawner.get_spawned_summary()

        assert isinstance(summary, str)

    def test_summary_contains_monster_info(self, mock_spawner):
        """Test that summary contains monster combat info."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 1}])
        summary = mock_spawner.get_spawned_summary()

        assert "goblin_1" in summary
        assert "HP" in summary
        assert "AC" in summary

    def test_summary_lists_all_spawned(self, mock_spawner):
        """Test that summary lists all spawned monsters."""
        mock_spawner.spawn_monsters([
            {"type": "goblin", "count": 2},
            {"type": "orc", "count": 1}
        ])
        summary = mock_spawner.get_spawned_summary()

        assert "goblin_1" in summary
        assert "goblin_2" in summary
        assert "orc_1" in summary

    def test_summary_empty_when_none_spawned(self, mock_spawner):
        """Test that summary handles no spawned monsters."""
        summary = mock_spawner.get_spawned_summary()
        assert summary == "" or "No monsters" in summary


# ==================== StateManager Integration Tests ====================


class TestStateManagerIntegration:
    """Test suite for StateManager integration."""

    def test_spawned_monsters_in_state_manager(self, mock_spawner, state_manager):
        """Test that spawned monsters are added to StateManager."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 2}])

        assert len(state_manager.monsters) == 2
        assert state_manager.get_monster("goblin_1") is not None
        assert state_manager.get_monster("goblin_2") is not None

    def test_get_character_by_id_finds_spawned_monster(self, mock_spawner, state_manager):
        """Test that get_character_by_id finds spawned monsters."""
        mock_spawner.spawn_monsters([{"type": "orc", "count": 1}])

        character = state_manager.get_character_by_id("orc_1")
        assert character is not None
        assert isinstance(character, Monster)
        assert character.name == "Orc 1"

    def test_spawned_monsters_have_effects_list(self, mock_spawner, state_manager):
        """Test that spawned monsters can have effects added."""
        mock_spawner.spawn_monsters([{"type": "goblin", "count": 1}])
        goblin = state_manager.get_monster("goblin_1")

        assert goblin.active_effects == []
        assert hasattr(goblin, 'add_effect')
        assert hasattr(goblin, 'remove_effect')


# ==================== Factory Function Tests ====================


class TestFactoryFunction:
    """Test suite for create_monster_spawner factory function."""

    def test_create_monster_spawner_returns_spawner(self, state_manager):
        """Test that factory function returns MonsterSpawner."""
        spawner = create_monster_spawner(state_manager=state_manager)
        assert isinstance(spawner, MonsterSpawner)

    def test_create_monster_spawner_with_custom_path(self, state_manager, mock_catalog_path):
        """Test factory function with custom catalog path."""
        spawner = create_monster_spawner(
            state_manager=state_manager,
            catalog_path=mock_catalog_path
        )

        types = spawner.get_available_monster_types()
        type_names = [t.type_name for t in types]

        assert "goblin" in type_names
        assert "orc" in type_names


# ==================== Real Template Tests ====================


class TestRealTemplates:
    """Test suite using real monster templates from src/characters/monsters/."""

    def test_real_templates_load_successfully(self, monster_spawner):
        """Test that real templates can be loaded."""
        types = monster_spawner.get_available_monster_types()
        assert len(types) >= 6  # At least goblin, orc, skeleton, zombie, wolf, hill_giant

    def test_spawn_real_goblin(self, monster_spawner, state_manager):
        """Test spawning from real goblin template."""
        created_ids = monster_spawner.spawn_monsters([{"type": "goblin", "count": 1}])

        assert "goblin_1" in created_ids
        goblin = state_manager.get_monster("goblin_1")
        assert goblin is not None
        assert goblin.armor_class.value == 15
        assert "Nimble Escape" in [t.name for t in goblin.special_traits]

    def test_spawn_real_skeleton(self, monster_spawner, state_manager):
        """Test spawning from real skeleton template."""
        created_ids = monster_spawner.spawn_monsters([{"type": "skeleton", "count": 1}])

        assert "skeleton_1" in created_ids
        skeleton = state_manager.get_monster("skeleton_1")
        assert skeleton is not None
        assert skeleton.meta.type == "undead"

    def test_spawn_real_wolf(self, monster_spawner, state_manager):
        """Test spawning from real wolf template."""
        created_ids = monster_spawner.spawn_monsters([{"type": "wolf", "count": 1}])

        assert "wolf_1" in created_ids
        wolf = state_manager.get_monster("wolf_1")
        assert wolf is not None
        assert "Pack Tactics" in [t.name for t in wolf.special_traits]

    def test_spawn_real_hill_giant(self, monster_spawner, state_manager):
        """Test spawning from real hill_giant template."""
        created_ids = monster_spawner.spawn_monsters([{"type": "hill_giant", "count": 1}])

        assert "hill_giant_1" in created_ids
        giant = state_manager.get_monster("hill_giant_1")
        assert giant is not None
        assert giant.meta.size == "Huge"
        assert giant.challenge.rating == "5"

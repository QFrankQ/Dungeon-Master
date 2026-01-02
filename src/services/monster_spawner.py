"""
Monster Spawner Service - Creates and manages monster instances for combat encounters.

This service provides:
1. Discovery of available monster templates
2. Spawning monsters from templates with unique IDs
3. Formatting available monsters for DM context
4. Loading pre-defined encounters
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..memory.state_manager import StateManager
from ..characters.monster import Monster


@dataclass
class MonsterSummary:
    """Summary info for a monster template."""
    type_name: str  # Template name (e.g., "goblin")
    display_name: str  # Display name (e.g., "Goblin")
    cr: str  # Challenge rating (e.g., "1/4", "5")
    size: str  # Size category
    creature_type: str  # Type (humanoid, undead, etc.)
    hp: int  # Average hit points
    ac: int  # Armor class
    special_trait: Optional[str] = None  # First special trait name if any


class MonsterSpawner:
    """
    Service for spawning monsters from templates.

    Handles:
    - Discovering available monster templates
    - Creating monster instances with unique IDs
    - Adding monsters to StateManager
    - Formatting monster info for DM context
    """

    def __init__(
        self,
        state_manager: StateManager,
        catalog_path: str = "src/characters/monsters/"
    ):
        """
        Initialize the monster spawner.

        Args:
            state_manager: StateManager for adding created monsters
            catalog_path: Path to directory containing monster templates
        """
        self.state_manager = state_manager
        self.catalog_path = catalog_path
        self._template_cache: Dict[str, Dict] = {}
        self._spawned_this_encounter: List[str] = []  # Track spawned IDs for summary

    def get_available_monster_types(self) -> List[MonsterSummary]:
        """
        Get list of all available monster templates with summary info.

        Returns:
            List of MonsterSummary objects for each template
        """
        summaries = []

        if not os.path.exists(self.catalog_path):
            return summaries

        for filename in sorted(os.listdir(self.catalog_path)):
            if not filename.endswith('.json'):
                continue

            type_name = filename[:-5]  # Remove .json extension
            template = self._load_template(type_name)

            if template:
                summary = self._create_summary(type_name, template)
                if summary:
                    summaries.append(summary)

        return summaries

    def _load_template(self, type_name: str) -> Optional[Dict]:
        """Load and cache a monster template."""
        if type_name in self._template_cache:
            return self._template_cache[type_name]

        template_path = os.path.join(self.catalog_path, f"{type_name}.json")
        if not os.path.exists(template_path):
            return None

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
                self._template_cache[type_name] = template
                return template
        except (json.JSONDecodeError, IOError):
            return None

    def _create_summary(self, type_name: str, template: Dict) -> Optional[MonsterSummary]:
        """Create a MonsterSummary from a template."""
        try:
            meta = template.get('meta', {})
            stats = template.get('stats', {})
            traits = template.get('special_traits', [])

            # Get CR - handle both string and int formats
            cr_data = stats.get('challenge', {})
            if isinstance(cr_data, dict):
                cr = str(cr_data.get('rating', '?'))
            else:
                cr = str(cr_data)

            # Get HP
            hp_data = stats.get('hit_points', {})
            if isinstance(hp_data, dict):
                hp = hp_data.get('average', 0)
            else:
                hp = hp_data

            # Get AC
            ac_data = stats.get('armor_class', {})
            if isinstance(ac_data, dict):
                ac = ac_data.get('value', 10)
            else:
                ac = ac_data

            # Get first special trait name
            special_trait = None
            if traits and len(traits) > 0:
                special_trait = traits[0].get('name')

            return MonsterSummary(
                type_name=type_name,
                display_name=template.get('name', type_name.title()),
                cr=cr,
                size=meta.get('size', 'Medium'),
                creature_type=meta.get('type', 'unknown'),
                hp=hp,
                ac=ac,
                special_trait=special_trait
            )
        except (KeyError, TypeError):
            return None

    def get_available_monsters_context(self) -> str:
        """
        Format available monsters for DM context.

        Returns:
            Formatted string listing all available monster templates
        """
        summaries = self.get_available_monster_types()

        if not summaries:
            return "No monster templates available."

        lines = ["Available Monster Templates:"]
        for s in summaries:
            trait_info = f", {s.special_trait}" if s.special_trait else ""
            lines.append(
                f"- {s.type_name} (CR {s.cr}, {s.size} {s.creature_type}): "
                f"HP {s.hp}, AC {s.ac}{trait_info}"
            )

        lines.append("")
        lines.append('Use select_encounter_monsters([{"type": "goblin", "count": 2}]) to spawn monsters.')

        return "\n".join(lines)

    def spawn_monsters(self, selections: List[Dict[str, Any]]) -> List[str]:
        """
        Create monsters from selections and add to StateManager.

        Args:
            selections: List of {"type": str, "count": int} dictionaries
                       e.g., [{"type": "goblin", "count": 2}, {"type": "orc", "count": 1}]

        Returns:
            List of created character_ids (e.g., ["goblin_1", "goblin_2", "orc_1"])

        Raises:
            ValueError: If a monster type is not found
        """
        created_ids = []
        self._spawned_this_encounter = []

        for selection in selections:
            monster_type = selection.get('type', '')
            count = selection.get('count', 1)

            if not monster_type:
                continue

            # Validate template exists
            template_path = os.path.join(self.catalog_path, f"{monster_type}.json")
            if not os.path.exists(template_path):
                available = [s.type_name for s in self.get_available_monster_types()]
                raise ValueError(
                    f"Monster type '{monster_type}' not found. "
                    f"Available types: {', '.join(available)}"
                )

            # Create monsters using StateManager
            monsters = self.state_manager.create_monster_group(
                template_path=template_path,
                count=count,
                prefix=monster_type
            )

            for monster in monsters:
                created_ids.append(monster.character_id)
                self._spawned_this_encounter.append(monster.character_id)

        return created_ids

    def get_spawned_summary(self) -> str:
        """
        Get summary of monsters spawned in the current encounter.

        Returns:
            Formatted string with spawned monster details
        """
        if not self._spawned_this_encounter:
            return "No monsters spawned yet."

        lines = ["Spawned Monsters:"]
        for char_id in self._spawned_this_encounter:
            monster = self.state_manager.get_monster(char_id)
            if monster:
                lines.append(
                    f"- {char_id}: {monster.name} "
                    f"(HP {monster.hit_points.current}/{monster.hit_points.maximum}, "
                    f"AC {monster.armor_class.value})"
                )

        return "\n".join(lines)

    def get_spawned_character_ids(self) -> List[str]:
        """Get list of character IDs spawned in the current encounter."""
        return list(self._spawned_this_encounter)

    def clear_spawned_tracking(self) -> None:
        """Clear the tracking of spawned monsters (call at combat end)."""
        self._spawned_this_encounter = []

    def spawn_from_encounter(self, encounter_path: str) -> List[str]:
        """
        Load and spawn monsters from a pre-defined encounter file.

        Args:
            encounter_path: Path to encounter JSON file

        Returns:
            List of created character_ids

        Raises:
            FileNotFoundError: If encounter file doesn't exist
            ValueError: If encounter format is invalid
        """
        if not os.path.exists(encounter_path):
            raise FileNotFoundError(f"Encounter file not found: {encounter_path}")

        try:
            with open(encounter_path, 'r', encoding='utf-8') as f:
                encounter = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid encounter JSON: {e}")

        monsters = encounter.get('monsters', [])
        if not monsters:
            raise ValueError("Encounter file has no 'monsters' defined")

        return self.spawn_monsters(monsters)


def create_monster_spawner(
    state_manager: StateManager,
    catalog_path: str = "src/characters/monsters/"
) -> MonsterSpawner:
    """
    Factory function to create a MonsterSpawner.

    Args:
        state_manager: StateManager for adding created monsters
        catalog_path: Path to monster templates directory

    Returns:
        Configured MonsterSpawner instance
    """
    return MonsterSpawner(state_manager=state_manager, catalog_path=catalog_path)

"""
State Manager - Character and Monster Persistence Layer

This class handles character and monster storage and persistence:
- load_character(): Load character from JSON file
- save_character(): Save character to JSON file
- get_character(): Get character with caching
- Monster management: add_monster, remove_monster, get_monster, clear_monsters
- get_character_by_id(): Unified lookup for both characters and monsters

All state updates are handled by StateCommandExecutor.
See state_command_executor.py for update logic.
"""

from typing import Dict, List, Any, Optional, Union
import json
import os
from datetime import datetime

from ..models.state_commands_optimized import StateCommandResult
from ..characters.charactersheet import Character
from ..characters.monster import Monster
from .state_command_executor import StateCommandExecutor, BatchExecutionResult


class StateUpdateError(Exception):
    """Exception raised when state updates fail."""
    pass


class StateManager:
    """
    Character and Monster Persistence and Storage Manager.

    This class provides storage, loading, and saving functionality for both
    player characters and monsters. It delegates state updates to StateCommandExecutor
    while maintaining data, caching, and audit trails.

    Key responsibilities:
    - Load/save character JSON files
    - Cache characters and monsters in memory
    - Coordinate with StateCommandExecutor for state updates
    - Provide unified character lookup for duck typing compatibility
    - Provide audit logging for state changes
    """

    def __init__(self, character_data_path: str = "src/characters/", enable_logging: bool = True):
        """
        Initialize the state manager.

        Args:
            character_data_path: Path to character data files
            enable_logging: Whether to log all state changes
        """
        self.character_data_path = character_data_path
        self.enable_logging = enable_logging
        self.characters: Dict[str, Character] = {}
        self.monsters: Dict[str, Monster] = {}  # Combat monsters (runtime only)
        self.update_log: List[Dict[str, Any]] = []

        # Initialize command executor with unified character lookup
        self.command_executor = StateCommandExecutor(
            character_lookup=self.get_character_by_id
        )

        # Ensure directories exist
        os.makedirs(character_data_path, exist_ok=True)
        if enable_logging:
            os.makedirs(os.path.join(character_data_path, "logs"), exist_ok=True)
    
    def load_character(self, character_id: str) -> Optional[Character]:
        """
        Load a character from storage.
        
        Args:
            character_id: ID of the character to load
        
        Returns:
            Character instance or None if not found
        """
        try:
            character_file = os.path.join(self.character_data_path, f"{character_id}.json")
            if os.path.exists(character_file):
                with open(character_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    character = Character.model_validate(data)
                    self.characters[character_id] = character
                    return character
        except Exception as e:
            self._log_error(f"Failed to load character {character_id}: {e}")
        
        return None
    
    def save_character(self, character_id: str) -> bool:
        """
        Save a character to storage.
        
        Args:
            character_id: ID of the character to save
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if character_id in self.characters:
                character_file = os.path.join(self.character_data_path, f"{character_id}.json")
                with open(character_file, 'w', encoding='utf-8') as f:
                    # Convert to dict for JSON serialization
                    character_data = self.characters[character_id].model_dump()
                    json.dump(character_data, f, indent=2, ensure_ascii=False)
                return True
        except Exception as e:
            self._log_error(f"Failed to save character {character_id}: {e}")
        
        return False
    
    def get_character_by_id(self, character_id: str) -> Optional[Union[Character, Monster]]:
        """
        Unified lookup for any character (player character or monster).

        Used by StateCommandExecutor for duck typing compatibility.
        Checks monsters first (runtime entities), then player characters.
        Loads player character from storage if not in memory.

        Args:
            character_id: ID of the character to look up

        Returns:
            Character or Monster instance, or None if not found
        """
        # Check monsters first (runtime entities)
        if character_id in self.monsters:
            return self.monsters[character_id]

        # Then check player characters (load from storage if needed)
        if character_id not in self.characters:
            self.load_character(character_id)
        return self.characters.get(character_id)

    def apply_commands(self, command_result: StateCommandResult) -> Dict[str, Any]:
        """
        Apply state commands using StateCommandExecutor (NEW method - command-based).

        Args:
            command_result: Result from StateExtractionOrchestrator with list of commands

        Returns:
            Dictionary with execution results and any errors
        """
        results = {
            "success": True,
            "commands_executed": 0,
            "errors": [],
            "warnings": []
        }

        try:
            # Execute all commands using the command executor
            batch_result: BatchExecutionResult = self.command_executor.execute_batch(
                command_result.commands
            )

            results["commands_executed"] = batch_result.successful
            results["success"] = batch_result.all_successful

            # Collect errors from failed commands
            for failure in batch_result.get_failures():
                results["errors"].append(failure.message)

            # Save all modified characters
            for command in command_result.commands:
                character_id = command.character_id
                if character_id in self.characters:
                    self.save_character(character_id)

            # Log the update
            if self.enable_logging:
                self._log_command_execution(command_result, batch_result)

        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Critical error executing commands: {str(e)}")
            self._log_error(f"Critical error executing commands: {e}")

        return results

    def _log_command_execution(self, command_result: StateCommandResult, batch_result: BatchExecutionResult) -> None:
        """Log command execution for audit trail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "extraction_notes": command_result.notes,
            "total_commands": batch_result.total_commands,
            "successful": batch_result.successful,
            "failed": batch_result.failed,
            "command_types": [cmd.type for cmd in command_result.commands],
            "failures": [
                {"character": r.character_id, "type": r.command_type, "message": r.message}
                for r in batch_result.get_failures()
            ]
        }

        self.update_log.append(log_entry)

        # Save to file if logging is enabled
        log_file = os.path.join(self.character_data_path, "logs", "state_updates.json")
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.update_log, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log_error(f"Failed to save update log: {e}")

    def _log_error(self, message: str) -> None:
        """Log error messages."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "ERROR",
            "message": message
        }
        
        print(f"StateManager ERROR: {message}")
        
        if self.enable_logging:
            error_file = os.path.join(self.character_data_path, "logs", "errors.json")
            try:
                errors = []
                if os.path.exists(error_file):
                    with open(error_file, 'r', encoding='utf-8') as f:
                        errors = json.load(f)
                
                errors.append(error_entry)
                
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(errors, f, indent=2, ensure_ascii=False)
            except Exception:
                pass  # Don't fail on logging errors
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """
        Get a player character by ID, loading if necessary.

        Delegates to get_character_by_id() but filters to only return
        Character instances (not Monster). Use get_character_by_id()
        for unified lookup of both types.

        Args:
            character_id: ID of the player character to get

        Returns:
            Character instance or None if not found or if ID refers to a monster
        """
        result = self.get_character_by_id(character_id)
        if isinstance(result, Character):
            return result
        return None
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get statistics about state updates."""
        return {
            "total_updates": len(self.update_log),
            "characters_in_memory": len(self.characters),
            "monsters_in_combat": len(self.monsters),
            "recent_errors": len([log for log in self.update_log if log.get("results", {}).get("errors")])
        }

    # ==================== Monster Management ====================

    def add_monster(self, monster: Monster) -> None:
        """
        Add a monster to combat.

        Args:
            monster: Monster instance to add
        """
        self.monsters[monster.character_id] = monster

    def remove_monster(self, character_id: str) -> bool:
        """
        Remove a monster from combat.

        Args:
            character_id: ID of the monster to remove

        Returns:
            True if monster was found and removed, False otherwise
        """
        if character_id in self.monsters:
            del self.monsters[character_id]
            return True
        return False

    def get_monster(self, character_id: str) -> Optional[Monster]:
        """
        Get a monster by ID.

        Args:
            character_id: ID of the monster

        Returns:
            Monster instance or None if not found
        """
        return self.monsters.get(character_id)

    def get_all_monsters(self) -> List[Monster]:
        """
        Get all active monsters.

        Returns:
            List of all Monster instances currently in combat
        """
        return list(self.monsters.values())

    def clear_monsters(self) -> None:
        """Clear all monsters (typically at end of combat)."""
        self.monsters.clear()

    def get_character_name_to_id_map(self) -> Dict[str, str]:
        """
        Get name → character_id mapping for all characters (players and monsters).

        Used by state extraction agents to resolve character names
        from narrative text to character IDs.

        Returns:
            Dictionary mapping display names to character IDs
        """
        mapping = {}

        # Add player characters
        for char_id, char in self.characters.items():
            if char.info and char.info.name:
                mapping[char.info.name] = char_id

        # Add monsters
        for monster_id, monster in self.monsters.items():
            mapping[monster.name] = monster_id

        return mapping

    def _transform_monster_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform JSON template format to Monster model format.

        Handles the structural differences between example_enemy.json format and
        Monster class expectations, including:
        - Moving stats.* fields to top level
        - Consolidating damage modifiers into damage_modifiers dict
        - Converting special_traits to MonsterSpecialTrait format

        Args:
            data: Raw JSON template data

        Returns:
            Transformed data ready for Monster.model_validate()
        """
        from ..characters.monster_components import MonsterSpecialTrait

        result = {}

        # Copy top-level fields directly
        for key in ['name', 'meta', 'attributes', 'special_traits', 'actions',
                    'reactions', 'legendary_actions', 'mythic_actions']:
            if key in data:
                result[key] = data[key]

        # Handle stats block - move fields to top level
        if 'stats' in data:
            stats = data['stats']

            # Direct mappings from stats to top level
            for key in ['armor_class', 'hit_points', 'speed', 'saving_throws',
                        'skills', 'senses', 'languages', 'challenge', 'proficiency_bonus']:
                if key in stats:
                    result[key] = stats[key]

            # Consolidate damage modifiers into damage_modifiers dict
            damage_mods = {}
            if 'damage_vulnerabilities' in stats:
                damage_mods['vulnerabilities'] = stats['damage_vulnerabilities']
            if 'damage_resistances' in stats:
                damage_mods['resistances'] = stats['damage_resistances']
            if 'damage_immunities' in stats:
                damage_mods['immunities'] = stats['damage_immunities']
            if 'condition_immunities' in stats:
                damage_mods['condition_immunities'] = stats['condition_immunities']

            if damage_mods:
                result['damage_modifiers'] = damage_mods

        # Convert special_traits to MonsterSpecialTrait format (preserves extra fields)
        if 'special_traits' in result:
            result['special_traits'] = [
                MonsterSpecialTrait.from_dict(trait).model_dump()
                for trait in result['special_traits']
            ]

        return result

    def create_monster_from_template(
        self,
        template_path: str,
        character_id: str,
        name: Optional[str] = None
    ) -> Optional[Monster]:
        """
        Create a monster from a JSON template file.

        Handles JSON templates in example_enemy.json format with nested stats block.

        Args:
            template_path: Path to monster template JSON file
            character_id: Unique ID for this monster instance
            name: Optional display name (defaults to template name)

        Returns:
            Monster instance or None if template loading failed
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Transform template format to Monster model format
            transformed = self._transform_monster_template(data)

            # Set the character_id
            transformed['character_id'] = character_id

            # Override name if provided
            if name:
                transformed['name'] = name

            monster = Monster.model_validate(transformed)
            self.add_monster(monster)
            return monster

        except Exception as e:
            self._log_error(f"Failed to create monster from template {template_path}: {e}")
            return None

    def create_monster_group(
        self,
        template_path: str,
        count: int,
        prefix: str
    ) -> List[Monster]:
        """
        Create multiple monsters from the same template.

        Args:
            template_path: Path to monster template JSON file
            count: Number of monsters to create
            prefix: Prefix for character_id and name (e.g., "goblin" -> "goblin_1", "Goblin 1")

        Returns:
            List of created Monster instances
        """
        monsters = []
        for i in range(1, count + 1):
            character_id = f"{prefix}_{i}"
            name = f"{prefix.replace('_', ' ').title()} {i}"
            monster = self.create_monster_from_template(template_path, character_id, name)
            if monster:
                monsters.append(monster)
        return monsters


def create_state_manager(character_data_path: str = "src/characters/") -> StateManager:
    """
    Factory function to create a configured state manager.
    
    Args:
        character_data_path: Path to character data files
    
    Returns:
        Configured StateManager instance
    """
    return StateManager(character_data_path=character_data_path)
"""
State update handler for managing character state changes.
Processes structured state updates and applies them to character models.
"""

from typing import Dict, List, Any, Optional, Union
import json
import os
from datetime import datetime
from copy import deepcopy

from ..models.state_updates import (
    StateExtractionResult,
    CharacterUpdate,
    CharacterCreation,
    HPUpdate,
    ConditionUpdate,
    AbilityUpdate,
    InventoryUpdate,
    SpellSlotUpdate,
    HitDiceUpdate,
    DeathSaveUpdate,
    CombatStatUpdate
)
from ..models.state_commands_optimized import StateCommandResult
from ..characters.charactersheet import Character
from .state_command_executor import StateCommandExecutor, BatchExecutionResult


class StateUpdateError(Exception):
    """Exception raised when state updates fail."""
    pass


class StateManager:
    """
    Manages character state updates based on extracted state changes.
    
    This class handles the system-level application of state changes
    identified by the StateExtractorAgent. It maintains character data,
    validates updates, and provides audit trails.
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
        self.update_log: List[Dict[str, Any]] = []

        # Initialize command executor with character lookup function
        self.command_executor = StateCommandExecutor(
            character_lookup=self._get_character_for_executor
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
    
    def _get_character_for_executor(self, character_id: str) -> Optional[Character]:
        """
        Character lookup function for StateCommandExecutor.

        Loads character from storage if not in memory.
        """
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

    def apply_state_updates(self, extraction_result: StateExtractionResult) -> Dict[str, Any]:
        """
        Apply all state updates from an extraction result.
        
        Args:
            extraction_result: Result from StateExtractorAgent
        
        Returns:
            Dictionary with update results and any errors
        """
        results = {
            "success": True,
            "character_updates_applied": 0,
            "new_characters_created": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Apply character updates
            for update in extraction_result.character_updates:
                try:
                    self._apply_character_update(update)
                    results["character_updates_applied"] += 1
                except Exception as e:
                    error_msg = f"Failed to update {update.character_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    self._log_error(error_msg)
            
            # Create new characters
            for creation in extraction_result.new_characters:
                try:
                    self._create_character(creation)
                    results["new_characters_created"] += 1
                except Exception as e:
                    error_msg = f"Failed to create character {creation.name}: {str(e)}"
                    results["errors"].append(error_msg)
                    self._log_error(error_msg)
            
            # Log the update
            if self.enable_logging:
                self._log_update(extraction_result, results)
            
            # If any errors occurred, mark as partial success
            if results["errors"]:
                results["success"] = False
        
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Critical error in state updates: {str(e)}")
            self._log_error(f"Critical error applying state updates: {e}")
        
        return results
    
    def _apply_character_update(self, update: CharacterUpdate) -> None:
        """Apply updates to a specific character."""
        character_id = update.character_id
        
        # Load character if not in memory
        if character_id not in self.characters:
            character = self.load_character(character_id)
            if not character:
                raise StateUpdateError(f"Character {character_id} not found")
        
        character = self.characters[character_id]
        
        # Apply different types of updates
        if update.hp_update:
            self._apply_hp_update(character, update.hp_update)
        
        if update.condition_update:
            self._apply_condition_update(character, update.condition_update)
        
        if update.ability_update:
            self._apply_ability_update(character, update.ability_update)
        
        if update.inventory_update:
            self._apply_inventory_update(character, update.inventory_update)
        
        if update.spell_slot_update:
            self._apply_spell_slot_update(character, update.spell_slot_update)
        
        if update.hit_dice_update:
            self._apply_hit_dice_update(character, update.hit_dice_update)
        
        if update.death_save_update:
            self._apply_death_save_update(character, update.death_save_update)
        
        if update.combat_stat_update:
            self._apply_combat_stat_update(character, update.combat_stat_update)
        
        # Save the updated character
        self.save_character(character_id)
    
    #TODO:HP Update needs to take temporary HP into account
    def _apply_hp_update(self, character: Character, hp_update: HPUpdate) -> None:
        """Apply HP changes to a character."""
        if hp_update.damage:
            current_hp = character.hit_points.current_hp
            new_hp = max(0, current_hp - hp_update.damage)
            character.hit_points.current_hp = new_hp
        
        if hp_update.healing:
            current_hp = character.hit_points.current_hp
            max_hp = character.hit_points.maximum_hp
            new_hp = min(max_hp, current_hp + hp_update.healing)
            character.hit_points.current_hp = new_hp
        
        if hp_update.temporary_hp:
            character.hit_points.temporary_hp = hp_update.temporary_hp
    
    def _apply_condition_update(self, character: Character, condition_update: ConditionUpdate) -> None:
        """Apply condition changes to a character."""
        # Initialize conditions list if it doesn't exist
        if not hasattr(character, 'conditions'):
            # Add conditions as a dynamic attribute for now
            # You may want to add this to the character model properly
            character.conditions = []
        
        # Add new conditions
        for condition in condition_update.add_conditions:
            if condition.value not in character.conditions:
                character.conditions.append(condition.value)
        
        # Remove conditions
        for condition in condition_update.remove_conditions:
            if condition.value in character.conditions:
                character.conditions.remove(condition.value)
    
    def _apply_ability_update(self, character: Character, ability_update: AbilityUpdate) -> None:
        """Apply ability score modifications to a character."""
        # This would modify temporary ability scores or modifiers
        # Implementation depends on how you handle temporary modifiers
        pass
    
    def _apply_inventory_update(self, character: Character, inventory_update: InventoryUpdate) -> None:
        """Apply inventory changes to a character."""
        # Implementation depends on your inventory structure
        pass
    
    def _apply_spell_slot_update(self, character: Character, spell_slot_update: SpellSlotUpdate) -> None:
        """Apply spell slot changes to a character."""
        if character.spellcasting and character.spellcasting.spell_slots:
            level = int(spell_slot_update.level.value)  # Convert enum to int
            if level in character.spellcasting.spell_slots:
                current = character.spellcasting.spell_slots[level]
                new_value = max(0, current + spell_slot_update.change)
                character.spellcasting.spell_slots[level] = new_value
    
    def _apply_hit_dice_update(self, character: Character, hit_dice_update: HitDiceUpdate) -> None:
        """Apply hit dice changes to a character."""
        # Implementation depends on hit dice structure in character model
        pass
    
    #TODO: implement the effects once either success or failures hits 3
    def _apply_death_save_update(self, character: Character, death_save_update: DeathSaveUpdate) -> None:
        """Apply death saving throw updates to a character."""
        if death_save_update.reset:
            character.death_saves.successes = 0
            character.death_saves.failures = 0
        else:
            # Increment successes if specified
            if death_save_update.success_increment is not None and death_save_update.success_increment > 0:
                new_successes = character.death_saves.successes + death_save_update.success_increment
                character.death_saves.successes = min(3, new_successes)
            
            # Increment failures if specified
            if death_save_update.failure_increment is not None and death_save_update.failure_increment > 0:
                new_failures = character.death_saves.failures + death_save_update.failure_increment
                character.death_saves.failures = min(3, new_failures)
    
    def _apply_combat_stat_update(self, character: Character, combat_stat_update: CombatStatUpdate) -> None:
        """Apply combat statistic updates to a character."""
        # Implementation for temporary combat stat changes
        pass
    
    def _create_character(self, creation: CharacterCreation) -> None:
        """Create a new character from creation data."""
        # This would create a basic character structure
        # Implementation depends on your character creation needs
        pass
    
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

    def _log_update(self, extraction_result: StateExtractionResult, results: Dict[str, Any]) -> None:
        """Log state update for audit trail (DEPRECATED - use _log_command_execution instead)."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "extraction_confidence": extraction_result.confidence,
            "extracted_from": extraction_result.extracted_from,
            "results": results,
            "character_updates": len(extraction_result.character_updates),
            "new_characters": len(extraction_result.new_characters)
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
        """Get a character by ID, loading if necessary."""
        if character_id not in self.characters:
            return self.load_character(character_id)
        return self.characters[character_id]
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get statistics about state updates."""
        return {
            "total_updates": len(self.update_log),
            "characters_in_memory": len(self.characters),
            "recent_errors": len([log for log in self.update_log if log.get("results", {}).get("errors")])
        }


def create_state_manager(character_data_path: str = "src/characters/") -> StateManager:
    """
    Factory function to create a configured state manager.
    
    Args:
        character_data_path: Path to character data files
    
    Returns:
        Configured StateManager instance
    """
    return StateManager(character_data_path=character_data_path)
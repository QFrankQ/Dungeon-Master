"""
State Manager - Character Persistence Layer

This class handles character storage and persistence:
- load_character(): Load character from JSON file
- save_character(): Save character to JSON file
- get_character(): Get character with caching

All state updates are handled by StateCommandExecutor.
See state_command_executor.py for update logic.
"""

from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime

from ..models.state_commands_optimized import StateCommandResult
from ..characters.charactersheet import Character
from .state_command_executor import StateCommandExecutor, BatchExecutionResult


class StateUpdateError(Exception):
    """Exception raised when state updates fail."""
    pass


class StateManager:
    """
    Character Persistence and Storage Manager.

    This class provides character storage, loading, and saving functionality.
    It delegates state updates to StateCommandExecutor while maintaining
    character data, caching, and audit trails.

    Key responsibilities:
    - Load/save character JSON files
    - Cache characters in memory
    - Coordinate with StateCommandExecutor for state updates
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
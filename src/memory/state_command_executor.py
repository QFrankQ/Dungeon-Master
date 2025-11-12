"""
State Command Executor - Applies state commands to character objects.

Design principles:
1. Single responsibility: Each handler method handles one command type
2. Clear error reporting: Track successes and failures with detailed messages
3. Extensibility: Easy to add new command handlers
4. Character lookup: Works with any character lookup mechanism (dict, registry, etc.)
"""

from typing import Dict, List, Optional, Callable, Union
from pydantic import BaseModel, Field

from ..characters.charactersheet import Character
from ..characters.character_components import Effect, DurationType
from ..models.state_commands_optimized import (
    HPChangeCommand,
    ConditionCommand,
    BuffCommand,
    SpellSlotCommand,
    HitDiceCommand,
    ItemCommand,
    DeathSaveCommand,
    RestCommand,
    StateCommand
)


# ==================== Execution Result Types ====================

class CommandExecutionResult(BaseModel):
    """Result of executing a single command."""
    success: bool
    command_type: str
    character_id: str
    message: str
    details: Dict = Field(default_factory=dict)  # Additional context like HP changes, etc.


class BatchExecutionResult(BaseModel):
    """Result of executing multiple commands."""
    total_commands: int
    successful: int
    failed: int
    results: List[CommandExecutionResult]

    @property
    def all_successful(self) -> bool:
        """Check if all commands executed successfully."""
        return self.failed == 0

    def get_failures(self) -> List[CommandExecutionResult]:
        """Get only the failed command results."""
        return [r for r in self.results if not r.success]

    def get_successes(self) -> List[CommandExecutionResult]:
        """Get only the successful command results."""
        return [r for r in self.results if r.success]


# ==================== State Command Executor ====================

class StateCommandExecutor:
    """
    Executes state commands and applies them to character objects.

    Usage:
        executor = StateCommandExecutor(character_lookup_fn)
        result = executor.execute_command(hp_change_command)
        batch_result = executor.execute_batch(command_list)
    """

    def __init__(self, character_lookup: Callable[[str], Optional[Character]]):
        """
        Initialize executor with a character lookup function.

        Args:
            character_lookup: Function that takes character_id and returns Character or None
                             Example: lambda id: character_registry.get_character(id)
        """
        self.character_lookup = character_lookup

        # Map command types to handler methods
        self._handlers: Dict[str, Callable] = {
            "hp_change": self._handle_hp_change,
            "condition": self._handle_condition,
            "buff": self._handle_buff,
            "spell_slot": self._handle_spell_slot,
            "hit_dice": self._handle_hit_dice,
            "item": self._handle_item,
            "death_save": self._handle_death_save,
            "rest": self._handle_rest,
        }

    # ==================== Public API ====================

    def execute_command(self, command: StateCommand) -> CommandExecutionResult:
        """
        Execute a single state command.

        Args:
            command: Any state command (HPChangeCommand, ConditionCommand, etc.)

        Returns:
            CommandExecutionResult with success status and details
        """
        command_type = command.type
        character_id = command.character_id

        # Get character
        character = self.character_lookup(character_id)
        if character is None:
            return CommandExecutionResult(
                success=False,
                command_type=command_type,
                character_id=character_id,
                message=f"Character '{character_id}' not found"
            )

        # Get handler
        handler = self._handlers.get(command_type)
        if handler is None:
            return CommandExecutionResult(
                success=False,
                command_type=command_type,
                character_id=character_id,
                message=f"No handler found for command type '{command_type}'"
            )

        # Execute handler
        try:
            return handler(command, character)
        except Exception as e:
            return CommandExecutionResult(
                success=False,
                command_type=command_type,
                character_id=character_id,
                message=f"Error executing command: {str(e)}"
            )

    def execute_batch(self, commands: List[StateCommand]) -> BatchExecutionResult:
        """
        Execute multiple commands in sequence.

        Args:
            commands: List of state commands to execute

        Returns:
            BatchExecutionResult with aggregate statistics and individual results
        """
        results = []
        successful = 0
        failed = 0

        for command in commands:
            result = self.execute_command(command)
            results.append(result)

            if result.success:
                successful += 1
            else:
                failed += 1

        return BatchExecutionResult(
            total_commands=len(commands),
            successful=successful,
            failed=failed,
            results=results
        )

    # ==================== Command Handlers ====================

    def _handle_hp_change(self, command: HPChangeCommand, character: Character) -> CommandExecutionResult:
        """Handle HP change commands (damage, healing, temporary HP)."""
        change = command.change
        is_temporary = command.is_temporary
        damage_type = command.damage_type

        # Store initial HP for reporting
        initial_hp = character.hit_points.current_hp
        initial_temp_hp = character.hit_points.temporary_hp

        if is_temporary:
            # Grant temporary HP
            if change <= 0:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message="Temporary HP must be positive"
                )

            old_temp_hp = character.hit_points.temporary_hp
            character.add_temporary_hp(change)
            new_temp_hp = character.hit_points.temporary_hp

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Granted {change} temporary HP (total: {new_temp_hp})",
                details={
                    "previous_temp_hp": old_temp_hp,
                    "granted": change,
                    "new_temp_hp": new_temp_hp,
                    "actual_change": new_temp_hp - old_temp_hp
                }
            )

        elif change < 0:
            # Apply damage
            damage_amount = abs(change)
            damage_result = character.take_damage(damage_amount)

            final_hp = character.hit_points.current_hp
            final_temp_hp = character.hit_points.temporary_hp

            temp_absorbed = damage_result["temp_absorbed"]
            actual_damage = damage_result["actual_damage"]

            damage_type_str = f" ({damage_type.value})" if damage_type else ""

            message_parts = [f"Took {damage_amount}{damage_type_str} damage"]
            if temp_absorbed > 0:
                message_parts.append(f"{temp_absorbed} absorbed by temp HP")
            if actual_damage > 0:
                message_parts.append(f"{actual_damage} to HP")

            # Check for unconscious
            if character.is_unconscious:
                message_parts.append("Character is now unconscious!")

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=", ".join(message_parts),
                details={
                    "damage_amount": damage_amount,
                    "damage_type": damage_type.value if damage_type else None,
                    "temp_hp_absorbed": temp_absorbed,
                    "actual_damage": actual_damage,
                    "previous_hp": initial_hp,
                    "previous_temp_hp": initial_temp_hp,
                    "new_hp": final_hp,
                    "new_temp_hp": final_temp_hp,
                    "is_unconscious": character.is_unconscious,
                    "is_bloodied": character.is_bloodied
                }
            )

        elif change > 0:
            # Apply healing
            heal_amount = change
            old_hp = character.hit_points.current_hp
            character.heal(heal_amount)
            new_hp = character.hit_points.current_hp
            actual_healing = new_hp - old_hp

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Healed {actual_healing} HP (max: {character.hit_points.maximum_hp})",
                details={
                    "heal_amount": heal_amount,
                    "previous_hp": old_hp,
                    "new_hp": new_hp,
                    "actual_healing": actual_healing,
                    "at_max_hp": new_hp == character.hit_points.maximum_hp
                }
            )

        else:
            # Change is 0, no-op
            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message="No HP change (change was 0)",
                details={"change": 0}
            )

    def _handle_condition(self, command: ConditionCommand, character: Character) -> CommandExecutionResult:
        """Handle condition add/remove commands."""
        # TODO: Implement condition handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Condition handler not yet implemented"
        )

    def _handle_buff(self, command: BuffCommand, character: Character) -> CommandExecutionResult:
        """Handle buff/debuff add/remove commands."""
        # TODO: Implement buff handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Buff handler not yet implemented"
        )

    def _handle_spell_slot(self, command: SpellSlotCommand, character: Character) -> CommandExecutionResult:
        """Handle spell slot use/restore commands."""
        # TODO: Implement spell slot handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Spell slot handler not yet implemented"
        )

    def _handle_hit_dice(self, command: HitDiceCommand, character: Character) -> CommandExecutionResult:
        """Handle hit dice use/restore commands."""
        # TODO: Implement hit dice handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Hit dice handler not yet implemented"
        )

    def _handle_item(self, command: ItemCommand, character: Character) -> CommandExecutionResult:
        """Handle item use/add/remove commands."""
        # TODO: Implement item handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Item handler not yet implemented"
        )

    def _handle_death_save(self, command: DeathSaveCommand, character: Character) -> CommandExecutionResult:
        """Handle death save recording commands."""
        # TODO: Implement death save handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Death save handler not yet implemented"
        )

    def _handle_rest(self, command: RestCommand, character: Character) -> CommandExecutionResult:
        """Handle short/long rest commands."""
        # TODO: Implement rest handling
        return CommandExecutionResult(
            success=False,
            command_type=command.type,
            character_id=command.character_id,
            message="Rest handler not yet implemented"
        )

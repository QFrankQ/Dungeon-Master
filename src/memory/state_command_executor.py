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
        condition_name = command.condition.value.capitalize()  # "poisoned" -> "Poisoned"
        action = command.action

        if action == "add":
            # Check if condition already exists
            existing = next((e for e in character.active_effects if e.name == condition_name), None)
            if existing:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Condition '{condition_name}' already active on character",
                    details={
                        "condition": condition_name,
                        "existing_source": existing.source,
                        "existing_duration": f"{existing.duration_remaining} {existing.duration_type.value}"
                    }
                )

            # Validate duration fields for add action
            if command.duration_type is None:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message="duration_type is required when adding a condition"
                )

            duration = command.duration if command.duration is not None else 0

            # Create and add the condition effect
            effect = Effect(
                name=condition_name,
                effect_type="condition",
                duration_type=command.duration_type,
                duration_remaining=duration,
                source=f"{condition_name} condition",  # Default source, can be enhanced later
                modifiers={}  # Conditions don't have stat modifiers (buffs do)
            )

            character.add_effect(effect)

            # Build duration description
            if command.duration_type == DurationType.PERMANENT:
                duration_str = "permanent"
            elif command.duration_type == DurationType.CONCENTRATION:
                duration_str = f"concentration, {duration} rounds"
            else:
                duration_str = f"{duration} {command.duration_type.value}"

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Added condition '{condition_name}' ({duration_str})",
                details={
                    "condition": condition_name,
                    "action": "add",
                    "duration_type": command.duration_type.value,
                    "duration": duration,
                    "active_conditions": character.conditions
                }
            )

        elif action == "remove":
            # Check if condition exists
            existing = next((e for e in character.active_effects if e.name == condition_name), None)
            if not existing:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Condition '{condition_name}' not found on character",
                    details={
                        "condition": condition_name,
                        "active_conditions": character.conditions
                    }
                )

            character.remove_effect(condition_name)

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Removed condition '{condition_name}'",
                details={
                    "condition": condition_name,
                    "action": "remove",
                    "active_conditions": character.conditions
                }
            )

        else:
            # This should never happen due to Literal type, but include for safety
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Invalid action '{action}' (must be 'add' or 'remove')"
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
        # Check if character has spellcasting
        if character.spellcasting is None:
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Character '{command.character_id}' does not have spellcasting"
            )

        level = command.level
        action = command.action
        spellcasting = character.spellcasting

        # Check if character has spell slots at this level
        total_slots = spellcasting.spell_slots.get(level, 0)
        if total_slots == 0:
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Character has no level {level} spell slots"
            )

        if action == "use":
            # Use a spell slot
            remaining_before = spellcasting.get_remaining_slots(level)
            success = spellcasting.use_spell_slot(level)

            if not success:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"No level {level} spell slots available",
                    details={
                        "level": level,
                        "remaining_slots": 0,
                        "total_slots": total_slots,
                        "spell_name": command.spell_name
                    }
                )

            remaining_after = spellcasting.get_remaining_slots(level)
            spell_info = f" ({command.spell_name})" if command.spell_name else ""

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Used level {level} spell slot{spell_info} ({remaining_after}/{total_slots} remaining)",
                details={
                    "level": level,
                    "spell_name": command.spell_name,
                    "remaining_slots": remaining_after,
                    "total_slots": total_slots,
                    "action": "use"
                }
            )

        elif action == "restore":
            # Restore spell slots (partial restoration)
            count = command.count
            expended_before = spellcasting.spell_slots_expended.get(level, 0)

            if expended_before == 0:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"No level {level} spell slots to restore (all slots available)",
                    details={
                        "level": level,
                        "remaining_slots": total_slots,
                        "total_slots": total_slots
                    }
                )

            # Restore count slots, but don't restore more than expended
            actual_restored = min(count, expended_before)
            new_expended = expended_before - actual_restored

            # Update the expended count
            if new_expended == 0:
                # Fully restored at this level, remove from dict
                if level in spellcasting.spell_slots_expended:
                    del spellcasting.spell_slots_expended[level]
            else:
                spellcasting.spell_slots_expended[level] = new_expended

            remaining_after = spellcasting.get_remaining_slots(level)

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Restored {actual_restored} level {level} spell slot{'s' if actual_restored != 1 else ''} ({remaining_after}/{total_slots} available)",
                details={
                    "level": level,
                    "requested_count": count,
                    "actual_restored": actual_restored,
                    "remaining_slots": remaining_after,
                    "total_slots": total_slots,
                    "action": "restore"
                }
            )

        else:
            # This should never happen due to Literal type, but include for safety
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Invalid action '{action}' (must be 'use' or 'restore')"
            )

    def _handle_hit_dice(self, command: HitDiceCommand, character: Character) -> CommandExecutionResult:
        """Handle hit dice use/restore commands."""
        action = command.action
        count = command.count
        hit_dice = character.hit_dice

        total_dice = hit_dice.total
        used_dice = hit_dice.used
        available_dice = total_dice - used_dice

        if action == "use":
            # Use (spend) hit dice
            if available_dice == 0:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message="No hit dice available to use",
                    details={
                        "total_dice": total_dice,
                        "used_dice": used_dice,
                        "available_dice": 0
                    }
                )

            # Can't use more than available
            actual_used = min(count, available_dice)
            hit_dice.used += actual_used
            new_available = total_dice - hit_dice.used

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Used {actual_used} hit dice ({new_available}/{total_dice} remaining)",
                details={
                    "requested_count": count,
                    "actual_used": actual_used,
                    "previous_used": used_dice,
                    "new_used": hit_dice.used,
                    "available_dice": new_available,
                    "total_dice": total_dice,
                    "action": "use"
                }
            )

        elif action == "restore":
            # Restore hit dice
            if used_dice == 0:
                return CommandExecutionResult(
                    success=False,
                    command_type=command.type,
                    character_id=command.character_id,
                    message="No hit dice to restore (all dice available)",
                    details={
                        "total_dice": total_dice,
                        "used_dice": 0,
                        "available_dice": total_dice
                    }
                )

            # Can't restore more than used
            actual_restored = min(count, used_dice)
            hit_dice.used = max(0, used_dice - actual_restored)
            new_available = total_dice - hit_dice.used

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Restored {actual_restored} hit dice ({new_available}/{total_dice} available)",
                details={
                    "requested_count": count,
                    "actual_restored": actual_restored,
                    "previous_used": used_dice,
                    "new_used": hit_dice.used,
                    "available_dice": new_available,
                    "total_dice": total_dice,
                    "action": "restore"
                }
            )

        else:
            # This should never happen due to Literal type, but include for safety
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Invalid action '{action}' (must be 'use' or 'restore')"
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
        result = command.result
        count = command.count
        death_saves = character.death_saves

        if result == "success":
            # Record successful death save(s)
            previous_successes = death_saves.successes
            previous_failures = death_saves.failures

            # Add successes (capped at 3 by validator)
            death_saves.successes = min(3, previous_successes + count)
            actual_added = death_saves.successes - previous_successes

            # Check if stable
            if death_saves.is_stable:
                return CommandExecutionResult(
                    success=True,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Death save succeeded! Character is now stable (3 successes)",
                    details={
                        "result": "success",
                        "count_added": actual_added,
                        "successes": death_saves.successes,
                        "failures": death_saves.failures,
                        "is_stable": True
                    }
                )
            else:
                return CommandExecutionResult(
                    success=True,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Death save succeeded ({death_saves.successes}/3 successes, {death_saves.failures}/3 failures)",
                    details={
                        "result": "success",
                        "count_added": actual_added,
                        "successes": death_saves.successes,
                        "failures": death_saves.failures,
                        "is_stable": False
                    }
                )

        elif result == "failure":
            # Record failed death save(s)
            previous_successes = death_saves.successes
            previous_failures = death_saves.failures

            # Add failures (capped at 3 by validator)
            death_saves.failures = min(3, previous_failures + count)
            actual_added = death_saves.failures - previous_failures

            # Check if dead
            if death_saves.is_dead:
                return CommandExecutionResult(
                    success=True,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Death save failed! Character has died (3 failures)",
                    details={
                        "result": "failure",
                        "count_added": actual_added,
                        "successes": death_saves.successes,
                        "failures": death_saves.failures,
                        "is_dead": True
                    }
                )
            else:
                return CommandExecutionResult(
                    success=True,
                    command_type=command.type,
                    character_id=command.character_id,
                    message=f"Death save failed ({death_saves.successes}/3 successes, {death_saves.failures}/3 failures)",
                    details={
                        "result": "failure",
                        "count_added": actual_added,
                        "successes": death_saves.successes,
                        "failures": death_saves.failures,
                        "is_dead": False
                    }
                )

        elif result == "reset":
            # Reset death saves (e.g., when healed or stabilized)
            previous_successes = death_saves.successes
            previous_failures = death_saves.failures

            death_saves.successes = 0
            death_saves.failures = 0

            return CommandExecutionResult(
                success=True,
                command_type=command.type,
                character_id=command.character_id,
                message="Death saves reset (character stabilized or healed)",
                details={
                    "result": "reset",
                    "previous_successes": previous_successes,
                    "previous_failures": previous_failures,
                    "successes": 0,
                    "failures": 0
                }
            )

        else:
            # This should never happen due to Literal type, but include for safety
            return CommandExecutionResult(
                success=False,
                command_type=command.type,
                character_id=command.character_id,
                message=f"Invalid result '{result}' (must be 'success', 'failure', or 'reset')"
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

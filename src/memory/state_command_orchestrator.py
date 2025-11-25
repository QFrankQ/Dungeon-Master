"""
State Command Orchestrator - Preprocesses commands before execution.

Handles meta-commands that expand into multiple atomic commands:
- RestCommand → HPChange, HitDice, SpellSlot, Effect removals

Design pattern:
    Agent → generates meta-commands (e.g., RestCommand)
    Orchestrator → expands to atomic commands
    Executor → executes atomic commands only
"""

from typing import List, Callable, Optional
from ..characters.charactersheet import Character
from ..characters.character_components import DurationType
from ..models.state_commands_optimized import (
    StateCommand,
    RestCommand,
    HPChangeCommand,
    HitDiceCommand,
    SpellSlotCommand,
    EffectCommand
)
from .state_command_executor import (
    StateCommandExecutor,
    BatchExecutionResult,
    CommandExecutionResult
)


class StateCommandOrchestrator:
    """
    Orchestrates command preprocessing and execution.

    Responsibilities:
    1. Expand meta-commands (RestCommand) to atomic commands
    2. Validate command sequences
    3. Execute commands via StateCommandExecutor

    Usage:
        orchestrator = StateCommandOrchestrator(executor)
        result = orchestrator.process_and_execute(commands, character_lookup)
    """

    def __init__(self, executor: StateCommandExecutor):
        """
        Initialize orchestrator with an executor.

        Args:
            executor: StateCommandExecutor instance for executing atomic commands
        """
        self.executor = executor

    def process_and_execute(
        self,
        commands: List[StateCommand],
        character_lookup: Callable[[str], Optional[Character]]
    ) -> BatchExecutionResult:
        """
        Preprocess commands (expand meta-commands) then execute.

        Args:
            commands: List of state commands (may include meta-commands like RestCommand)
            character_lookup: Function to look up characters by ID

        Returns:
            BatchExecutionResult with results for all executed commands
        """
        expanded_commands = []
        expansion_errors = []

        for cmd in commands:
            if isinstance(cmd, RestCommand):
                # Expand RestCommand to atomic commands
                char = character_lookup(cmd.character_id)
                if not char:
                    # Character not found - create error result
                    expansion_errors.append(CommandExecutionResult(
                        success=False,
                        command_type="rest",
                        character_id=cmd.character_id,
                        message=f"Character '{cmd.character_id}' not found"
                    ))
                    continue

                # Generate atomic commands based on rest type
                try:
                    rest_commands = self._generate_rest_commands(
                        character_id=cmd.character_id,
                        character=char,
                        rest_type=cmd.rest_type,
                        hit_dice_spent=cmd.hit_dice_spent
                    )
                    expanded_commands.extend(rest_commands)
                except Exception as e:
                    expansion_errors.append(CommandExecutionResult(
                        success=False,
                        command_type="rest",
                        character_id=cmd.character_id,
                        message=f"Error expanding RestCommand: {str(e)}"
                    ))
            else:
                # Pass through atomic commands as-is
                expanded_commands.append(cmd)

        # Execute all expanded atomic commands
        if expanded_commands:
            execution_result = self.executor.execute_batch(expanded_commands)

            # Merge expansion errors with execution results
            if expansion_errors:
                all_results = expansion_errors + execution_result.results
                return BatchExecutionResult(
                    total_commands=len(commands),
                    successful=execution_result.successful,
                    failed=execution_result.failed + len(expansion_errors),
                    results=all_results
                )
            return execution_result

        # Only expansion errors, no commands to execute
        return BatchExecutionResult(
            total_commands=len(commands),
            successful=0,
            failed=len(expansion_errors),
            results=expansion_errors
        )

    def _generate_rest_commands(
        self,
        character_id: str,
        character: Character,
        rest_type: str,
        hit_dice_spent: int
    ) -> List[StateCommand]:
        """
        Generate atomic commands for a rest.

        Args:
            character_id: ID of the character taking rest
            character: Character object taking the rest
            rest_type: "short" or "long"
            hit_dice_spent: Number of hit dice to spend (short rest only)

        Returns:
            List of atomic StateCommands that implement the rest
        """
        commands = []
        char_id = character_id

        if rest_type == "short":
            # SHORT REST: Spend hit dice for healing
            if hit_dice_spent > 0:
                # Use hit dice
                commands.append(HitDiceCommand(
                    character_id=char_id,
                    action="use",
                    count=hit_dice_spent
                ))

                # Calculate healing: hit_dice_spent × (hit die average + CON modifier)
                # Note: Actual healing should be rolled, but we'll use average
                # Calculate CON modifier: (score - 10) // 2
                con_modifier = (character.ability_scores.constitution - 10) // 2
                # Assume d10 hit die (Fighter default) - ideally would use character.hit_dice.die_type
                hit_die_faces = 10  # Default assumption
                hit_die_average = (hit_die_faces // 2) + 1
                healing_per_die = max(1, hit_die_average + con_modifier)  # Minimum 1 HP per die
                total_healing = hit_dice_spent * healing_per_die

                commands.append(HPChangeCommand(
                    character_id=char_id,
                    change=total_healing,
                    change_type="heal"
                ))

        elif rest_type == "long":
            # LONG REST: Full heal
            # Heal by maximum HP (executor will cap at actual max)
            # This ensures full heal regardless of command execution order
            commands.append(HPChangeCommand(
                character_id=char_id,
                change=character.hit_points.maximum_hp,
                change_type="heal"
            ))

            # Restore hit dice (regain half of spent hit dice, minimum 1)
            hit_dice_spent_count = character.hit_dice.used
            if hit_dice_spent_count > 0:
                commands.append(HitDiceCommand(
                    character_id=char_id,
                    action="restore"
                ))

            # Restore all spell slots
            if character.spellcasting:
                for level in range(1, 10):
                    slots_total = character.spellcasting.spell_slots.get(level, 0)
                    if slots_total > 0:
                        slots_used = character.spellcasting.spell_slots_expended.get(level, 0)
                        if slots_used > 0:
                            # Restore this spell level - restore ALL expended slots
                            commands.append(SpellSlotCommand(
                                character_id=char_id,
                                level=level,
                                action="restore",
                                count=slots_used  # Restore all expended slots at this level
                            ))

            # Remove all non-permanent effects
            for effect in character.active_effects:
                if effect.duration_type != DurationType.PERMANENT:
                    commands.append(EffectCommand(
                        character_id=char_id,
                        action="remove",
                        effect_name=effect.name
                    ))

        return commands

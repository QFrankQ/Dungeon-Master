"""
Context builder for Dungeon Master that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional, Dict, Any

from ..memory.turn_manager import TurnManagerSnapshot
from ..models.turn_context import TurnContext



class DMContextBuilder:
    """
    Builds comprehensive context for Dungeon Master including all available information.
    
    Provides full chronological context with:
    - Recent condensed turn history
    - Current turn stack with live messages and completed subturn results
    - Proper indentation to show turn hierarchy
    - Chronological order preservation
    """
    
    def __init__(self, state_manager=None, rules_cache_service=None, player_character_registry=None):
        """
        Initialize the DM context builder.

        Args:
            state_manager: Optional StateManager for loading character information
            rules_cache_service: Optional RulesCacheService for accessing cached rules
            player_character_registry: Optional PlayerCharacterRegistry for registered character names
        """
        self.state_manager = state_manager
        self.rules_cache_service = rules_cache_service
        self.player_character_registry = player_character_registry
    
    def build_context(
        self,
        turn_manager_snapshots: TurnManagerSnapshot,
        new_message_entries: Optional[List[Dict[str, Any]]] = None,
        # recent_history: Optional[List[str]] = None
    ) -> str:
        """
        Build comprehensive DM context from turn stack and recent history.

        Args:
            turn_manager_snapshots: Current turn manager state snapshot
            new_message_entries: Optional list of message entry dictionaries with keys:
                - 'player_message': ChatMessage object
                - 'player_id': Player's ID
                - 'character_id': Character name/ID
            recent_history: Recent condensed turn history (last few completed turns)

        Returns:
            Formatted context string with full chronological information
        """
        context_parts = []
        completed_turns = turn_manager_snapshots.completed_turns
        #TODO: Objectives for Current Step
        # Need Default Objectives at the start of game session
        context_parts.append(turn_manager_snapshots.current_step_objective)
        
        # Add recent history if available
        # TODO: history summary + recent history
        if completed_turns:
            context_parts.append("<history_turns")
            context_parts.extend(completed_turns[-3:])  # Last 3 completed turns for now
            context_parts.append("</history_turns>")
        
        #Context from current turn.
        context_parts.extend("<current_turn>")
        context_parts.append(self.build_xml_context(turn_manager_snapshots.active_turns_by_level))
        context_parts.extend("</current_turn>")

        # Add character sheet for active character (for capability validation)
        if self.state_manager and turn_manager_snapshots.active_turns_by_level:
            current_turn = turn_manager_snapshots.active_turns_by_level[-1]
            if current_turn.active_character:
                character = self.state_manager.get_character(current_turn.active_character)
                if character:
                    context_parts.append("<character_sheet>")
                    context_parts.append(self._format_character_sheet(character))
                    context_parts.append("</character_sheet>")
                    context_parts.append("")

        # Add cached rules from turn hierarchy (for quick reference)
        if self.rules_cache_service and turn_manager_snapshots.active_turns_by_level:
            merged_cache = self.rules_cache_service.merge_cache_from_snapshot(
                turn_manager_snapshots.active_turns_by_level
            )
            if merged_cache:
                context_parts.append("<cached_rules>")
                context_parts.append(self._format_cached_rules(merged_cache))
                context_parts.append("</cached_rules>")
                context_parts.append("")

        # Build New Messages (if provided as parameter)
        if new_message_entries:
            context_parts.append("<new_messages>")
            for message_entry in new_message_entries:
                xml_message = self._convert_message_entry_to_xml(message_entry)
                context_parts.append(xml_message)
            context_parts.append("</new_messages>")

        return "\n".join(context_parts)

    def _convert_message_entry_to_xml(self, message_entry: Dict[str, Any]) -> str:
        """
        Convert a message entry dictionary to XML format.

        Args:
            message_entry: Dictionary containing:
                - 'player_message': ChatMessage object
                - 'player_id': Player's ID
                - 'character_id': Character name/ID

        Returns:
            XML formatted string for the message
        """
        player_message = message_entry['player_message']
        character_name = message_entry['character_id']

        # Format as XML message with character context
        return f'<message speaker="{character_name}">{player_message.text}</message>'
    
    def build_xml_context(self, active_turns_by_level: List[TurnContext], exclude_new_messages: bool = False) -> str:
        """
        Build XML context for Dungeon Master with nested turn structure.

        Uses each TurnContext's to_xml_context method to build properly nested
        XML with appropriate indentation for each turn level.

        Args:
            active_turns_by_level: First TurnContext from each level (provided by snapshot)
            exclude_new_messages: Whether to exclude new messages
                (they will be shown separately in <new_messages>)

        Returns:
            XML string with nested turn/subturn structure and proper indentation
        """
        if not active_turns_by_level:
            return "<turn_log>\n</turn_log>"

        context_parts = []

        for turn_context in active_turns_by_level:
            # Get XML context from the turn
            turn_xml = turn_context.to_xml_context(exclude_new_messages=exclude_new_messages)

            # Apply indentation based on turn level for nested structure
            indent = "  " * turn_context.turn_level
            xml_lines = turn_xml.split('\n')

            for line in xml_lines:
                if line.strip():  # Only indent non-empty lines
                    context_parts.append(f"{indent}{line}")
                else:
                    context_parts.append("")

        return "\n".join(context_parts)

    def _format_character_sheet(self, character) -> str:
        """
        Format character sheet information for DM context.

        Provides essential character capabilities including class, level, HP,
        spellcasting abilities, and equipment. Helps DM validate actions.

        Args:
            character: Character object from state_manager

        Returns:
            Formatted character sheet string
        """
        lines = []

        # Basic info
        classes_str = "/".join([c.value.title() for c in character.info.classes])
        lines.append(f"Character: {character.info.name} ({classes_str} Level {character.info.level})")
        lines.append(f"Race: {character.info.race.value.title()} | Background: {character.info.background}")
        lines.append("")

        # Hit Points
        hp_current = character.hit_points.current_hp
        hp_max = character.hit_points.maximum_hp
        hp_temp = character.hit_points.temporary_hp
        hp_line = f"HP: {hp_current}/{hp_max}"
        if hp_temp > 0:
            hp_line += f" (+{hp_temp} temp)"
        lines.append(hp_line)
        lines.append("")

        # Ability Scores (for checking action feasibility)
        lines.append("Ability Scores:")
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(character.ability_scores, ability)
            modifier = (score - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
            lines.append(f"  {ability.upper()[:3]}: {score} ({mod_str})")
        lines.append("")

        # Spellcasting (critical for validating spell actions)
        if character.spellcasting:
            lines.append("Spellcasting:")
            lines.append(f"  Ability: {character.spellcasting.spellcasting_ability.upper()}")
            lines.append(f"  Spell Save DC: {character.spellcasting.spell_save_dc}")
            lines.append(f"  Spell Attack: +{character.spellcasting.spell_attack_bonus}")

            # Spell slots
            if character.spellcasting.spell_slots:
                lines.append("  Spell Slots:")
                for level in range(1, 10):
                    total_slots = character.spellcasting.spell_slots.get(level, 0)
                    expended = character.spellcasting.spell_slots_expended.get(level, 0)
                    if total_slots > 0:
                        available = total_slots - expended
                        lines.append(f"    Level {level}: {available}/{total_slots} available")
            lines.append("")

        # Active Conditions (affect action feasibility)
        if character.conditions:
            lines.append(f"Conditions: {', '.join(character.conditions)}")
            lines.append("")

        # Active Effects
        if character.active_effects:
            lines.append("Active Effects:")
            for effect in character.active_effects:
                duration_str = f" ({effect.duration} rounds)" if effect.duration else ""
                lines.append(f"  - {effect.name}: {effect.summary}{duration_str}")
            lines.append("")

        return "\n".join(lines)

    #TODO: this should be generated directly from Character
    def _format_cached_rules(self, rules_cache: Dict[str, Any]) -> str:
        """
        Format cached rules for DM context.

        Provides quick reference to rules already queried during this turn,
        helping DM make informed decisions without additional lookups.

        Args:
            rules_cache: Dictionary of cached rule entries

        Returns:
            Formatted rules cache string
        """
        if not rules_cache:
            return ""

        lines = []
        lines.append("Cached Rules Reference:")

        # Group by entry_type
        rules_by_type = {}
        for rule_name, rule_data in rules_cache.items():
            entry_type = rule_data.get("entry_type", "unknown")
            if entry_type not in rules_by_type:
                rules_by_type[entry_type] = []
            rules_by_type[entry_type].append(rule_data)

        # Format each type
        for entry_type, rules in sorted(rules_by_type.items()):
            lines.append(f"\n  {entry_type.upper()}S:")
            for rule in rules:
                name = rule.get("name", "Unknown")
                summary = rule.get("summary", rule.get("description", "")[:100])
                lines.append(f"    - {name}: {summary}")

        return "\n".join(lines)

    # ===== DEMO METHOD (Simplified for demo purposes) =====

    def build_demo_context(
        self,
        turn_manager_snapshots: TurnManagerSnapshot,
        # new_message_entries: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        DEMO VERSION: Build simplified DM context without game state, rules, etc.

        Differences from original:
        - No game state information
        - No rule lookups
        - Only includes: step objective, turn logs, and new messages
        - Automatically highlights unprocessed MessageGroups as "new"

        Args:
            turn_manager_snapshots: Current turn manager state snapshot
            new_message_entries: Optional list of message entry dictionaries (legacy support)
                If provided, uses this instead of extracting from MessageGroups

        Returns:
            Simplified context string with turn logs and new messages only
        """
        context_parts = []
        completed_turns = turn_manager_snapshots.completed_turns

        # Add registered player characters
        # Show both IDs (for awaiting_response) and names (for narrative)
        if self.player_character_registry:
            registered_ids = list(self.player_character_registry.get_all_character_ids())
            id_to_name_map = self.player_character_registry.get_character_id_to_name_map()
            if registered_ids:
                context_parts.append("<registered_player_characters>")
                # Show clear ID → Name mapping
                for char_id in registered_ids:
                    name = id_to_name_map.get(char_id, char_id)
                    context_parts.append(f"  {char_id} → {name}")
                context_parts.append("")
                # Instructions for usage
                id_list = ", ".join(registered_ids)
                name_list = ", ".join(id_to_name_map.get(cid, cid) for cid in registered_ids)
                context_parts.append(f"IMPORTANT: Use character IDs ({id_list}) in awaiting_response.characters")
                context_parts.append(f"Use character names ({name_list}) in narrative and dialogue")
                context_parts.append("</registered_player_characters>")
                context_parts.append("")

        # Add current step objective
        context_parts.append("<step_objective>")
        context_parts.append(turn_manager_snapshots.current_step_objective or "Begin the adventure")
        context_parts.append("</step_objective>")
        context_parts.append("")

        # Add recent completed turns history (if available)
        if completed_turns:
            context_parts.append("<history_turns>")
            for turn in completed_turns[-3:]:  # Last 3 completed turns
                # Use to_xml_context for consistent formatting
                context_parts.append(turn.to_xml_context())
            context_parts.append("</history_turns>")
            context_parts.append("")

        # Add current turn context (with processed messages and unprocessed groups hidden)
        context_parts.append("<current_turn>")
        context_parts.append(self.build_xml_context(turn_manager_snapshots.active_turns_by_level, exclude_new_messages=True))
        context_parts.append("</current_turn>")
        context_parts.append("")

        # Add character sheet for active character (enables DM to validate capabilities)
        if self.state_manager and turn_manager_snapshots.active_turns_by_level:
            current_turn = turn_manager_snapshots.active_turns_by_level[-1]
            if current_turn.active_character:
                character = self.state_manager.get_character(current_turn.active_character)
                if character:
                    context_parts.append("<character_sheet>")
                    context_parts.append(self._format_character_sheet(character))
                    context_parts.append("</character_sheet>")
                    context_parts.append("")

        # Add cached rules from turn hierarchy (provides quick rule reference)
        if self.rules_cache_service and turn_manager_snapshots.active_turns_by_level:
            merged_cache = self.rules_cache_service.merge_cache_from_snapshot(
                turn_manager_snapshots.active_turns_by_level
            )
            if merged_cache:
                context_parts.append("<cached_rules>")
                context_parts.append(self._format_cached_rules(merged_cache))
                context_parts.append("</cached_rules>")
                context_parts.append("")

        # Highlight new messages
        if turn_manager_snapshots.active_turns_by_level:
            current_turn = turn_manager_snapshots.active_turns_by_level[-1]  # Deepest level is current

            # Collect new messages - both TurnMessage and MessageGroup have is_new_message attribute
            new_message_items = [item for item in current_turn.messages if item.is_new_message]

            if new_message_items:
                context_parts.append("<new_messages>")
                for item in new_message_items:
                    context_parts.append(item.to_xml_element())
                context_parts.append("</new_messages>")
                context_parts.append("")

        return "\n".join(context_parts)

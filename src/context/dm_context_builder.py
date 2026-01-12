"""
Context builder for Dungeon Master that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional, Dict, Any, Union

from ..memory.player_character_registry import PlayerCharacterRegistry
from ..memory.state_manager import StateManager
from ..services.rules_cache_service import RulesCacheService
from ..memory.turn_manager import TurnManagerSnapshot
from ..models.turn_context import TurnContext
from ..models.combat_state import CombatState, CombatPhase
from ..characters.monster import Monster
from ..characters.charactersheet import Character



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
        self.state_manager: Optional[StateManager] = state_manager
        self.rules_cache_service: Optional[RulesCacheService] = rules_cache_service
        self.player_character_registry: Optional[PlayerCharacterRegistry] = player_character_registry
    
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

        # Add character/monster statblock for active character (for capability validation)
        if self.state_manager and turn_manager_snapshots.active_turns_by_level:
            current_turn = turn_manager_snapshots.active_turns_by_level[-1]
            if current_turn.active_character:
                character_data = self.state_manager.get_character_by_id(current_turn.active_character)
                if character_data:
                    # Use _format_character_sheet which handles both Character and Monster
                    context_parts.append("<active_character_statblock>")
                    context_parts.append(self._format_character_sheet(character_data))
                    context_parts.append("</active_character_statblock>")
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

    def _format_character_sheet(self, character: Union[Character, Monster]) -> str:
        """
        Format character or monster sheet information for DM context.

        For Characters: Uses compact get_full_sheet() method which provides essential
        stats and ability names without full descriptions. This is token-efficient
        for routine context. The DM can use query_character_ability tool to get
        detailed descriptions for specific features, spells, or equipment when needed.

        For Monsters: Uses get_full_statblock() for complete monster statblock format.

        Args:
            character: Character or Monster object from state_manager

        Returns:
            Formatted sheet string (compact version for characters, full statblock for monsters)
        """
        if isinstance(character, Monster):
            return character.get_full_statblock()
        return character.get_full_sheet()

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

    def _format_combat_state(self, combat_state: CombatState) -> str:
        """
        Format combat state for DM context including initiative order.

        Only returns content when in combat (not in NOT_IN_COMBAT phase).
        Includes initiative order with current turn indicator so DM always
        has access to the correct order without needing to call a tool.

        Args:
            combat_state: CombatState object from turn_manager

        Returns:
            Formatted XML string with combat state, or empty string if not in combat
        """
        # Don't include if not in combat
        if combat_state.phase == CombatPhase.NOT_IN_COMBAT:
            return ""

        lines = ["<combat_state>"]
        lines.append(f"  <phase>{combat_state.phase.value}</phase>")
        lines.append(f"  <round>{combat_state.round_number}</round>")

        # Include initiative order if established
        if combat_state.initiative_order:
            lines.append("  <initiative_order>")
            lines.append("    <!-- IMPORTANT: Use this EXACT order when narrating turns. Do NOT make up different values. -->")
            for i, entry in enumerate(combat_state.initiative_order):
                player_marker = "PC" if entry.is_player else "NPC"
                current_marker = ' current="true"' if i == combat_state.current_participant_index else ""
                lines.append(
                    f'    <entry position="{i+1}" id="{entry.character_id}" '
                    f'name="{entry.character_name}" roll="{entry.roll}" '
                    f'type="{player_marker}"{current_marker}/>'
                )
            lines.append("  </initiative_order>")

            # Add explicit current turn info for clarity
            current_entry = combat_state.get_current_entry()
            if current_entry:
                lines.append(f"  <current_turn character_id=\"{current_entry.character_id}\" "
                           f"name=\"{current_entry.character_name}\"/>")
        else:
            lines.append("  <initiative_order>Not yet established</initiative_order>")

        # Combat statistics
        players = combat_state.get_remaining_player_ids()
        monsters = combat_state.get_remaining_monster_ids()
        lines.append(f"  <remaining_combatants players=\"{len(players)}\" monsters=\"{len(monsters)}\"/>")

        lines.append("</combat_state>")
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

        # Add combat state (initiative order, phase, etc.) when in combat
        if turn_manager_snapshots.combat_state:
            combat_context = self._format_combat_state(turn_manager_snapshots.combat_state)
            if combat_context:
                context_parts.append(combat_context)
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

        # Add character/monster statblock for active character
        # Enables DM to validate capabilities (players) or make tactical decisions (monsters)
        if self.state_manager and turn_manager_snapshots.active_turns_by_level:
            current_turn = turn_manager_snapshots.active_turns_by_level[-1]
            if current_turn.active_character:
                character_data = self.state_manager.get_character_by_id(current_turn.active_character)
                if character_data:
                    # Use _format_character_sheet which handles both Character and Monster
                    context_parts.append("<active_character_statblock>")
                    context_parts.append(self._format_character_sheet(character_data))
                    context_parts.append("</active_character_statblock>")
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

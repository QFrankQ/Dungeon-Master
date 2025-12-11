"""
Context builder for EffectAgent with cached rules from turn hierarchy.

Builds context for effect extraction with merged rules cache from turn snapshots,
providing known effect/spell/condition descriptions to guide extraction.
"""

from typing import Optional, Dict, Any, List
from ..models.turn_context import TurnContext
from ..services.rules_cache_service import RulesCacheService


class EffectAgentContextBuilder:
    """
    Builds context for EffectAgent with cached rule descriptions.

    Follows the established context builder pattern (StateExtractorContextBuilder, DMContextBuilder)
    by using snapshot's active_turns_by_level for hierarchical cache merging.

    Provides context that includes:
    - Narrative text to extract effects from
    - KNOWN EFFECTS section with cached spell/condition descriptions from LanceDB
    - Game context metadata (turn ID, active character, etc.)
    """

    def __init__(self, rules_cache_service: RulesCacheService):
        """
        Initialize the EffectAgent context builder.

        Args:
            rules_cache_service: Service for merging and filtering rules cache
        """
        self.rules_cache_service = rules_cache_service

    def build_context(
        self,
        narrative: str,
        active_turns_by_level: List[TurnContext],
        game_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build formatted context for EffectAgent with cached effect descriptions.

        Args:
            narrative: Narrative text to extract effects from (e.g., DM response)
            active_turns_by_level: Active turns from snapshot (for hierarchical cache merging)
                                   Example: [Turn_1, Turn_1.2, Turn_1.2.1]
            game_context: Optional metadata (turn_id, active_character, etc.)

        Returns:
            Formatted context string with narrative, known effects, and metadata

        Example Output:
            === NARRATIVE ===
            The cleric casts Bless on the party...

            === KNOWN EFFECTS ===
            **Bless** (Spell, Level 1)
            Whenever you make an attack roll or saving throw, you can roll 1d4...
            Duration: Concentration, up to 1 minute

            **Poisoned** (Condition)
            A poisoned creature has disadvantage on attack rolls...

            === GAME CONTEXT ===
            Turn ID: 1.2.1
            Active Character: Alice
        """
        context_parts = []

        # Add narrative section
        context_parts.extend([
            "=== NARRATIVE ===",
            narrative,
            ""
        ])

        # Merge cache from snapshot and filter to effect-related types
        rules_cache = self.rules_cache_service.merge_cache_from_snapshot(
            active_turns_by_level
        )

        effect_cache = self.rules_cache_service.filter_cache_by_types(
            rules_cache,
            entry_types=["effect", "condition", "spell"]
        )

        # Add KNOWN EFFECTS section
        if effect_cache:
            context_parts.append("=== KNOWN EFFECTS ===")
            context_parts.append("The following effects/spells/conditions have been referenced in this turn:")
            context_parts.append("")

            for rule_key, rule_entry in effect_cache.items():
                formatted_rule = self._format_cached_rule(rule_entry)
                context_parts.append(formatted_rule)
                context_parts.append("")
        else:
            context_parts.extend([
                "=== KNOWN EFFECTS ===",
                "No effects have been queried from the rules database in this turn.",
                ""
            ])

        # Add game context metadata
        if game_context:
            context_parts.append("=== GAME CONTEXT ===")

            if "turn_id" in game_context:
                context_parts.append(f"Turn ID: {game_context['turn_id']}")

            if "active_character" in game_context:
                context_parts.append(f"Active Character: {game_context['active_character']}")

            if "combat_round" in game_context:
                context_parts.append(f"Combat Round: {game_context['combat_round']}")

            context_parts.append("")

        return "\n".join(context_parts)

    def _format_cached_rule(self, rule_entry: Dict[str, Any]) -> str:
        """
        Format a single cached rule entry for display in KNOWN EFFECTS section.

        Args:
            rule_entry: Cache entry with rule information

        Returns:
            Formatted multi-line string with rule details

        Example:
            **Bless** (Spell, Level 1)
            Whenever you make an attack roll or saving throw...
            Duration: Concentration, up to 1 minute
            School: Enchantment
        """
        name = rule_entry.get("name", "Unknown")
        entry_type = rule_entry.get("entry_type", "unknown").capitalize()
        description = rule_entry.get("description", "No description available.")

        # Build header with type and additional info
        header_parts = [entry_type]

        if "level" in rule_entry:
            header_parts.append(f"Level {rule_entry['level']}")

        if "rarity" in rule_entry:
            header_parts.append(rule_entry["rarity"].capitalize())

        header = f"**{name}** ({', '.join(header_parts)})"

        # Build full entry
        lines = [header, description]

        # Add additional details on separate lines
        if "duration_text" in rule_entry:
            lines.append(f"Duration: {rule_entry['duration_text']}")

        if "school" in rule_entry:
            lines.append(f"School: {rule_entry['school'].capitalize()}")

        if "damage" in rule_entry:
            lines.append(f"Damage: {rule_entry['damage']}")

        return "\n".join(lines)

    def build_simple_context(self, narrative: str) -> str:
        """
        Build simplified context without cache (for testing or fallback).

        Args:
            narrative: Narrative text to extract effects from

        Returns:
            Simple context with just narrative
        """
        return f"=== NARRATIVE ===\n{narrative}\n"

    def get_cached_effect_count(
        self,
        active_turns_by_level: List[TurnContext]
    ) -> int:
        """
        Get count of cached effect-related rules for this turn hierarchy.

        Useful for debugging and validation.

        Args:
            active_turns_by_level: Active turns from snapshot

        Returns:
            Number of cached effect/condition/spell entries
        """
        rules_cache = self.rules_cache_service.merge_cache_from_snapshot(
            active_turns_by_level
        )

        effect_cache = self.rules_cache_service.filter_cache_by_types(
            rules_cache,
            entry_types=["effect", "condition", "spell"]
        )

        return len(effect_cache)


def create_effect_agent_context_builder(
    rules_cache_service: RulesCacheService
) -> EffectAgentContextBuilder:
    """
    Factory function to create an EffectAgent context builder.

    Args:
        rules_cache_service: Service for merging and filtering rules cache

    Returns:
        Configured EffectAgentContextBuilder instance

    Usage:
        from src.services.rules_cache_service import create_rules_cache_service
        from src.context.effect_agent_context_builder import create_effect_agent_context_builder

        cache_service = create_rules_cache_service()
        context_builder = create_effect_agent_context_builder(cache_service)

        # Use in orchestrator
        context = context_builder.build_context(
            narrative=dm_response,
            active_turns_by_level=snapshot.active_turns_by_level,
            game_context={"turn_id": "1.2", "active_character": "Alice"}
        )
    """
    return EffectAgentContextBuilder(rules_cache_service)

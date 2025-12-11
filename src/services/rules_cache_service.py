"""RulesCacheService - Simplified cache merging and filtering for D&D rules.

Manages cache stored in TurnContext.metadata["rules_cache"] with hierarchical
inheritance from turn snapshots. DM populates cache via query_rules_database tool,
downstream agents (EffectAgent, etc.) consume merged cache.
"""

from typing import Dict, List, Any
from src.models.turn_context import TurnContext


class RulesCacheService:
    """
    Simplified cache service for merging and filtering D&D rules from turn hierarchy.

    Design Philosophy:
    - DM queries LanceDB proactively → caches in turn.metadata["rules_cache"]
    - RulesCacheService merges cache from snapshot's active_turns_by_level
    - Downstream agents filter cache to relevant types and consume

    Cache stores ALL rule types (spells, items, conditions, actions, etc.),
    not just effects. Individual agents filter to relevant types.
    """

    def merge_cache_from_snapshot(
        self,
        active_turns_by_level: List[TurnContext]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Merge cache from snapshot's active turns (hierarchical inheritance).

        Iterates through active_turns_by_level (from TurnManager snapshot) and merges
        each turn's metadata["rules_cache"]. Later turns overwrite earlier ones,
        allowing turn-specific overrides.

        Args:
            active_turns_by_level: Active turns from snapshot (one per level in lineage)
                                  Example: [Turn_1, Turn_1.2, Turn_1.2.1]

        Returns:
            Merged cache dictionary with normalized lowercase keys

        Example:
            Turn 1 (Level 0): cache = {bless: {...}, haste: {...}}
            Turn 1.2 (Level 1): cache = {shield: {...}}
            Merged = {bless, haste, shield}

            Turn 1.1 (sibling): NOT in active_turns_by_level for Turn 1.2
            Therefore Turn 1.1's cache NOT included
        """
        merged_cache = {}

        # Merge caches in order from root to current (child overwrites parent)
        for turn in active_turns_by_level:
            turn_cache = turn.metadata.get("rules_cache", {})
            merged_cache.update(turn_cache)

        return merged_cache

    def filter_cache_by_types(
        self,
        cache: Dict[str, Dict[str, Any]],
        entry_types: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Filter cache to specific entry types.

        Used by agents to get only relevant rules:
        - EffectAgent: ["effect", "condition", "spell"]
        - CombatAgent: ["action", "weapon", "item"]
        - HPAgent: ["spell", "item", "condition"]

        Args:
            cache: Full rules cache
            entry_types: List of types to include (e.g., ["spell", "condition"])

        Returns:
            Filtered cache dictionary

        Example:
            cache = {
                "bless": {"entry_type": "spell", ...},
                "longsword": {"entry_type": "item", ...},
                "poisoned": {"entry_type": "condition", ...}
            }
            filter_cache_by_types(cache, ["spell", "condition"])
            → {"bless": {...}, "poisoned": {...}}
        """
        return {
            key: value
            for key, value in cache.items()
            if value.get("entry_type") in entry_types
        }

    #TODO: Potential future improvement, avoid duplicate 
    def add_to_cache(
        self,
        rule_entry: Dict[str, Any],
        turn_context: TurnContext
    ) -> None:
        """
        Add a rule entry to turn's cache (helper for DM tool).

        Normalizes rule name to lowercase for consistent lookups.
        Creates rules_cache if it doesn't exist.

        Args:
            rule_entry: Rule dictionary with required fields:
                       - name: Rule name (will be normalized to lowercase key)
                       - entry_type: Type (spell, item, condition, action, etc.)
                       - description: Rule description
                       - source: "lancedb" or "llm_generated"
                       - ...additional fields (duration, summary, etc.)
            turn_context: Turn to add cache entry to

        Example:
            rule_entry = {
                "name": "Bless",
                "entry_type": "spell",
                "description": "Whenever you make an attack roll...",
                "source": "lancedb"
            }
            add_to_cache(rule_entry, current_turn)
            → current_turn.metadata["rules_cache"]["bless"] = rule_entry
        """
        # Get or create rules_cache
        if "rules_cache" not in turn_context.metadata:
            turn_context.metadata["rules_cache"] = {}

        # Normalize key to lowercase
        normalized_key = rule_entry["name"].lower()

        # Add to cache
        turn_context.metadata["rules_cache"][normalized_key] = rule_entry


def create_rules_cache_service() -> RulesCacheService:
    """
    Factory function to create RulesCacheService.

    Returns:
        RulesCacheService instance
    """
    return RulesCacheService()

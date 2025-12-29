"""DM Agent Tools - Tools for Dungeon Master agent to query rules and cache results.

Provides tools for DM to query LanceDB for D&D rules and cache results in current turn,
as well as query detailed character ability information.
"""

from typing import Optional, Literal
from pydantic_ai import RunContext

from ..db.lance_rules_service import LanceRulesService
from ..memory.turn_manager import TurnManager
from ..memory.state_manager import StateManager
from ..services.rules_cache_service import RulesCacheService


# Dependency types for tool context
class DMToolsDependencies:
    """Dependencies required by DM tools."""

    def __init__(
        self,
        lance_service: LanceRulesService,
        turn_manager: TurnManager,
        rules_cache_service: RulesCacheService,
        state_manager: Optional[StateManager] = None
    ):
        self.lance_service = lance_service
        self.turn_manager = turn_manager
        self.rules_cache_service = rules_cache_service
        self.state_manager = state_manager


async def query_rules_database(
    ctx: RunContext[DMToolsDependencies],
    query: str,
    limit: int = 3
) -> str:
    """
    Query D&D rules database for spell, item, condition, or action information.

    Automatically detects query type and returns relevant rules:
    - Short queries (≤10 words): Tries exact name match first, falls back to hybrid search
    - Long queries (>10 words): Uses hybrid search (vector + full-text)

    Caches all results in current turn's metadata["rules_cache"] for reuse by
    state extraction agents (EffectAgent, etc.).

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        query: Rule name or natural language query
               Examples:
                 - "Bless" (exact match)
                 - "bonus action fireball concentration" (multi-keyword)
                 - "how does spellcasting work?" (natural language)
        limit: Maximum number of results to return (default 3, max 10)

    Returns:
        Formatted rule information string with up to 'limit' results

    Side Effects:
        - Caches all results in current_turn.metadata["rules_cache"]
        - Uses normalized lowercase keys for consistent lookups

    Examples:
        Single rule by name:
        >>> await query_rules_database(ctx, "Bless")
        "Bless (Spell, Level 1):\\nWhenever you make an attack roll..."

        Multi-concept query:
        >>> await query_rules_database(ctx, "bonus action fireball concentration", limit=5)
        "Bonus Action (Action):\\n...\\n\\n---\\n\\nFireball (Spell, Level 3):\\n...\\n\\n---\\n\\n..."
    """
    lance_service = ctx.deps.lance_service
    turn_manager = ctx.deps.turn_manager
    rules_cache_service = ctx.deps.rules_cache_service

    # Get current turn for caching
    current_turn = turn_manager.get_current_turn_context()
    if not current_turn:
        return "Error: No active turn to cache results."

    # Clamp limit to max 10
    limit = min(limit, 10)

    # Auto-detect: short queries try exact match first
    if len(query.split()) <= 10:
        rule_entry = lance_service.get_by_name(query)
        if rule_entry:
            # Exact match found - cache and return single result
            cache_entry = _format_lance_entry_to_cache(rule_entry)
            rules_cache_service.add_to_cache(cache_entry, current_turn)
            return _format_rule_for_dm(cache_entry)

    # Fall through to hybrid search (or if query was long/no exact match)
    results = lance_service.search(query, limit=limit)

    if not results:
        return f"No rules found matching '{query}'"

    # Cache all results and format
    formatted_results = []
    for result in results:
        cache_entry = _format_lance_entry_to_cache(result)
        rules_cache_service.add_to_cache(cache_entry, current_turn)
        formatted_results.append(_format_rule_for_dm(cache_entry))

    # Return formatted multi-result string with separator
    return "\n\n---\n\n".join(formatted_results)


def _format_lance_entry_to_cache(lance_entry: dict) -> dict:
    """
    Format LanceDB entry into cache schema.

    Args:
        lance_entry: Raw entry from LanceDB with fields:
                    - name: Rule name
                    - type: Entry type (spell, item, condition, etc.)
                    - content: Rule description
                    - metadata: Additional fields (level, school, duration, etc.)

    Returns:
        Cache entry dictionary matching schema:
        {
            "name": str,
            "entry_type": str,
            "description": str,
            "source": "lancedb",
            ...additional metadata fields
        }
    """
    cache_entry = {
        "name": lance_entry.get("name", "Unknown"),
        "entry_type": lance_entry.get("type", "unknown"),
        "description": lance_entry.get("content", ""),
        "source": "lancedb"
    }

    # Extract additional metadata if available
    metadata = lance_entry.get("metadata", {})
    if metadata:
        # Common metadata fields
        if "level" in metadata:
            cache_entry["level"] = metadata["level"]
        if "school" in metadata:
            cache_entry["school"] = metadata["school"]
        if "duration" in metadata:
            cache_entry["duration_text"] = metadata["duration"]
        if "rarity" in metadata:
            cache_entry["rarity"] = metadata["rarity"]
        if "damage" in metadata:
            cache_entry["damage"] = metadata["damage"]

    return cache_entry


def _format_rule_for_dm(cache_entry: dict) -> str:
    """
    Format cache entry into readable string for DM narrative generation.

    Args:
        cache_entry: Cache entry with rule information

    Returns:
        Formatted string with rule details

    Example:
        Input: {"name": "Bless", "entry_type": "spell", "level": 1, ...}
        Output: "Bless (Spell, Level 1):\\n  Whenever you make an attack roll..."
    """
    name = cache_entry.get("name", "Unknown")
    entry_type = cache_entry.get("entry_type", "unknown").capitalize()
    description = cache_entry.get("description", "No description available.")

    # Build header with type and level/rarity info
    header_parts = [entry_type]

    if "level" in cache_entry:
        header_parts.append(f"Level {cache_entry['level']}")
    if "rarity" in cache_entry:
        header_parts.append(cache_entry["rarity"].capitalize())

    header = f"{name} ({', '.join(header_parts)})"

    # Format full output
    lines = [
        header,
        "=" * len(header),
        description
    ]

    # Add additional details if available
    if "duration_text" in cache_entry:
        lines.append(f"\\nDuration: {cache_entry['duration_text']}")
    if "school" in cache_entry:
        lines.append(f"School: {cache_entry['school'].capitalize()}")
    if "damage" in cache_entry:
        lines.append(f"Damage: {cache_entry['damage']}")

    return "\\n".join(lines)


async def query_character_ability(
    ctx: RunContext[DMToolsDependencies],
    character_id: str,
    section: Literal["summary", "attacks", "features", "spells", "equipment", "full"],
    ability_name: Optional[str] = None
) -> str:
    """
    Query character ability information with varying levels of detail.

    Use this tool when you need information about a character's abilities,
    spells, features, or equipment to validate player actions or adjudicate rules.

    The compact character sheet in context shows names only. This tool provides:
    - summary: Compact character sheet (same as context, useful for other characters)
    - Detailed sections with full descriptions:
      - Spell: casting time, range, components, duration, full description, at higher levels
      - Feature: source, full description text
      - Attack: attack bonus, damage, damage type, notes
      - Equipment: quantity, weight, full description

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        character_id: Character ID to query (e.g., "fighter", "wizard", "cleric")
        section: Which section to query:
            - "summary": Compact character sheet (stats and ability names only)
            - "attacks": Detailed attack information
            - "features": Detailed feature/trait descriptions
            - "spells": Detailed spell information (casting time, range, etc.)
            - "equipment": Detailed equipment with descriptions
            - "full": Complete detailed character sheet
        ability_name: Optional specific ability name to look up within the section
                     (e.g., "Fireball" for spells, "Second Wind" for features)
                     If not found, returns the full section as fallback.

    Returns:
        Formatted information string

    Examples:
        Get compact character sheet:
        >>> await query_character_ability(ctx, "wizard", "summary")

        Get all spell details:
        >>> await query_character_ability(ctx, "wizard", "spells")

        Get specific spell details:
        >>> await query_character_ability(ctx, "wizard", "spells", "Fireball")

        Get all feature details:
        >>> await query_character_ability(ctx, "fighter", "features")

        Get specific feature:
        >>> await query_character_ability(ctx, "fighter", "features", "Second Wind")
    """
    state_manager = ctx.deps.state_manager

    if not state_manager:
        return "Error: State manager not available for character queries."

    # Load character
    character = state_manager.get_character(character_id)
    if not character:
        return f"Error: Character '{character_id}' not found."

    # Route to appropriate method
    if section == "summary":
        return character.get_full_sheet()

    elif section == "full":
        return character.get_full_sheet_detailed()

    elif section == "attacks":
        if ability_name:
            # Find specific attack
            for attack in character.attacks_and_spellcasting:
                if attack.name.lower() == ability_name.lower():
                    lines = [f"▸ {attack.name}"]
                    lines.append(f"  Attack Bonus: +{attack.attack_bonus}")
                    lines.append(f"  Damage: {attack.damage} {attack.damage_type}")
                    if attack.notes:
                        lines.append(f"  Notes: {attack.notes}")
                    return "\n".join(lines)
            # Not found - return section as fallback
            return f"Attack '{ability_name}' not found. Here are all attacks:\n\n{character.get_attacks_detailed()}"
        return character.get_attacks_detailed()

    elif section == "features":
        if ability_name:
            # Find specific feature
            for feature in character.features_and_traits:
                if feature.name.lower() == ability_name.lower():
                    lines = [f"▸ {feature.name}"]
                    if feature.source:
                        lines.append(f"  Source: {feature.source}")
                    if feature.description:
                        lines.append(f"  {feature.description}")
                    return "\n".join(lines)
            # Not found - return section as fallback
            return f"Feature '{ability_name}' not found. Here are all features:\n\n{character.get_features_detailed()}"
        return character.get_features_detailed()

    elif section == "spells":
        if not character.spells:
            return f"{character.info.name} has no spells."

        if ability_name:
            # Find specific spell across all levels
            for level in range(0, 10):
                for spell in character.spells.get_spells_at_level(level):
                    if spell.name.lower() == ability_name.lower():
                        level_label = "Cantrip" if level == 0 else f"Level {level}"
                        lines = [f"▸ {spell.name} ({level_label})"]
                        if spell.casting_time:
                            lines.append(f"  Casting Time: {spell.casting_time}")
                        if spell.range:
                            lines.append(f"  Range: {spell.range}")
                        if spell.target:
                            lines.append(f"  Target: {spell.target}")
                        if spell.components:
                            lines.append(f"  Components: {spell.components}")
                        if spell.duration:
                            lines.append(f"  Duration: {spell.duration}")
                        if spell.description:
                            lines.append(f"  Description: {spell.description}")
                        if spell.at_higher_levels:
                            lines.append(f"  At Higher Levels: {spell.at_higher_levels}")
                        return "\n".join(lines)
            # Not found - return section as fallback
            return f"Spell '{ability_name}' not found. Here are all spells:\n\n{character.get_spells_detailed()}"
        return character.get_spells_detailed()

    elif section == "equipment":
        if ability_name:
            # Find specific equipment item
            for item in character.equipment:
                if item.name.lower() == ability_name.lower():
                    qty = f" (×{item.quantity})" if item.quantity > 1 else ""
                    weight = f" [{item.weight_lbs} lb]" if item.weight_lbs > 0 else ""
                    lines = [f"▸ {item.name}{qty}{weight}"]
                    if item.description:
                        lines.append(f"  {item.description}")
                    return "\n".join(lines)
            # Not found - return section as fallback
            return f"Equipment '{ability_name}' not found. Here is all equipment:\n\n{character.get_equipment_detailed()}"
        return character.get_equipment_detailed()

    else:
        return f"Unknown section: '{section}'. Use 'summary', 'attacks', 'features', 'spells', 'equipment', or 'full'."


def create_dm_tools(
    lance_service: LanceRulesService,
    turn_manager: TurnManager,
    rules_cache_service: RulesCacheService,
    state_manager: Optional[StateManager] = None
) -> tuple[list, DMToolsDependencies]:
    """
    Factory function to create DM tools and their dependencies.

    Args:
        lance_service: LanceDB service for rule queries
        turn_manager: Turn manager for getting current turn
        rules_cache_service: Cache service for storing results
        state_manager: Optional StateManager for character ability queries

    Returns:
        Tuple of (tool_list, dependencies) where:
        - tool_list: List of tool functions to pass to DM agent
        - dependencies: DMToolsDependencies instance to pass to agent.run()

    Usage:
        tools, deps = create_dm_tools(lance_service, turn_manager, cache_service, state_manager)
        dm_agent = create_dungeon_master_agent(tools=tools)
        result = await dm_agent.process_message(context, deps=deps)
    """
    tools = [query_rules_database, query_character_ability]
    dependencies = DMToolsDependencies(
        lance_service=lance_service,
        turn_manager=turn_manager,
        rules_cache_service=rules_cache_service,
        state_manager=state_manager
    )

    return tools, dependencies

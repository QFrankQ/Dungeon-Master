"""DM Agent Tools - Tools for Dungeon Master agent to query rules and cache results.

Provides tools for DM to query LanceDB for D&D rules and cache results in current turn,
as well as query detailed character ability information and spawn monsters for combat.
"""

from typing import Optional, Literal, Union, List, Dict, Any
from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from ..db.lance_rules_service import LanceRulesService
from ..memory.turn_manager import TurnManager
from ..memory.state_manager import StateManager
from ..models.combat_state import CombatPhase
from ..services.rules_cache_service import RulesCacheService
from ..services.monster_spawner import MonsterSpawner
from ..services.game_logger import GameLogger, LogLevel
from ..characters.monster import Monster
from ..characters.charactersheet import Character


# ==================== Null Object Pattern for Logging ====================

class _NullToolLogger:
    """
    Null object logger for DM tools when no logger is configured.

    Accepts any method call with any arguments and does nothing.
    This eliminates the need for 'if logger:' checks throughout tool code.
    """
    def dm_tool(self, *args, **kwargs) -> None:
        pass

    def combat(self, *args, **kwargs) -> None:
        pass

    def turn(self, *args, **kwargs) -> None:
        pass

    def extraction(self, *args, **kwargs) -> None:
        pass

    def step(self, *args, **kwargs) -> None:
        pass

    def __repr__(self) -> str:
        return "<NullToolLogger>"


# Singleton null logger instance
_null_logger = _NullToolLogger()


def _get_log(ctx: "RunContext[DMToolsDependencies]") -> Union[GameLogger, _NullToolLogger]:
    """
    Get a logger that's always safe to call (never None).

    Returns the real logger if available, otherwise returns a null logger
    that silently discards all log calls.
    """
    return ctx.deps.logger or _null_logger


# ==================== Standardized Failure Codes ====================

class FailureReason:
    """
    Standardized failure reason codes for DM tools.

    Using a class with string constants instead of Enum for flexibility
    with dynamic reasons (like character_not_found with ID interpolation).
    """
    # Dependency missing
    TURN_MANAGER_MISSING = "turn_manager_not_available"
    STATE_MANAGER_MISSING = "state_manager_not_available"
    MONSTER_SPAWNER_MISSING = "monster_spawner_not_available"
    LANCE_SERVICE_MISSING = "lance_service_not_available"

    # Combat state
    NOT_IN_COMBAT = "not_in_combat"
    WRONG_PHASE = "wrong_combat_phase"

    # Turn state
    NO_ACTIVE_TURN = "no_active_turn"

    # Input validation
    NO_MONSTERS_SPECIFIED = "no_monsters_specified"
    NO_ROLLS_PROVIDED = "no_rolls_provided"

    # Entity not found
    CHARACTER_NOT_FOUND = "character_not_found"
    PARTICIPANT_NOT_FOUND = "participant_not_found"

    # Operation failures
    SPAWN_ERROR = "spawn_error"
    NO_MONSTERS_CREATED = "no_monsters_created"
    TRANSITION_ERROR = "transition_error"


# ==================== Raise-for-Error Pattern ====================

class ToolValidationError(Exception):
    """
    Exception raised when tool validation fails.

    Contains the pre-formatted error message to return to the AI.
    This enables the "raise for error" pattern where validation helpers
    raise instead of returning tuples, eliminating if-error boilerplate.

    Usage:
        def some_tool(ctx):
            turn_manager = _require_turn_manager(ctx, "some_tool")  # Raises if missing
            # ... rest of logic (no if-error check needed)
    """
    def __init__(self, error_message: str):
        self.error_message = error_message
        super().__init__(error_message)


def _fail(
    log: Union[GameLogger, _NullToolLogger],
    tool_name: str,
    reason: str,
    level: LogLevel = LogLevel.WARNING,
    **extra_data
) -> str:
    """
    Log a failure and return a formatted error string in one call.

    Args:
        log: Logger instance (real or null)
        tool_name: Name of the tool that failed
        reason: Machine-readable reason code (use FailureReason constants)
        level: Log level (default: WARNING)
        **extra_data: Additional fields to include in log

    Returns:
        Formatted error string for user display
    """
    log.dm_tool(f"{tool_name} failed: {reason}", level=level, **extra_data)
    # Convert reason code to human-readable message
    human_reason = reason.replace("_", " ").capitalize()
    return f"Error: {human_reason}."


def _raise_fail(
    log: Union[GameLogger, _NullToolLogger],
    tool_name: str,
    reason: str,
    level: LogLevel = LogLevel.WARNING,
    **extra_data
) -> None:
    """
    Log a failure and raise ToolValidationError.

    Same as _fail() but raises instead of returning.
    Use this in _require_* validation helpers.
    """
    error_msg = _fail(log, tool_name, reason, level, **extra_data)
    raise ToolValidationError(error_msg)


# ==================== Tool Parameter Models ====================


class MonsterSelection(BaseModel):
    """A monster type and count for encounter spawning."""
    type: str = Field(description="Monster template name (e.g., 'goblin', 'orc', 'skeleton')")
    count: int = Field(ge=1, description="Number of this monster type to spawn")


class MonsterInitiativeRoll(BaseModel):
    """A monster's initiative roll for combat."""
    monster_id: str = Field(description="Monster ID (e.g., 'goblin_1', 'orc_2')")
    roll: int = Field(description="Total initiative roll result (d20 + DEX modifier)")


# ==================== Dependency Types ====================
class DMToolsDependencies:
    """Dependencies required by DM tools."""

    def __init__(
        self,
        lance_service: LanceRulesService,
        turn_manager: TurnManager,
        rules_cache_service: RulesCacheService,
        state_manager: Optional[StateManager] = None,
        monster_spawner: Optional[MonsterSpawner] = None,
        logger: Optional[GameLogger] = None
    ):
        self.lance_service = lance_service
        self.turn_manager = turn_manager
        self.rules_cache_service = rules_cache_service
        self.state_manager = state_manager
        self.monster_spawner = monster_spawner
        self.logger = logger


# ==================== Validation Helpers (Raise-for-Error Pattern) ====================

def _require_turn_manager(ctx: RunContext[DMToolsDependencies], tool_name: str) -> TurnManager:
    """
    Validate that turn_manager is available.

    Returns:
        TurnManager instance

    Raises:
        ToolValidationError: If turn_manager is not available
    """
    turn_manager = ctx.deps.turn_manager
    if not turn_manager:
        _raise_fail(_get_log(ctx), tool_name, FailureReason.TURN_MANAGER_MISSING)

    return turn_manager


def _require_state_manager(ctx: RunContext[DMToolsDependencies], tool_name: str) -> StateManager:
    """
    Validate that state_manager is available.

    Returns:
        StateManager instance

    Raises:
        ToolValidationError: If state_manager is not available
    """
    state_manager = ctx.deps.state_manager
    if not state_manager:
        _raise_fail(_get_log(ctx), tool_name, FailureReason.STATE_MANAGER_MISSING)

    return state_manager


def _require_monster_spawner(ctx: RunContext[DMToolsDependencies], tool_name: str) -> MonsterSpawner:
    """
    Validate that monster_spawner is available.

    Returns:
        MonsterSpawner instance

    Raises:
        ToolValidationError: If monster_spawner is not available
    """
    monster_spawner = ctx.deps.monster_spawner
    if not monster_spawner:
        _raise_fail(_get_log(ctx), tool_name, FailureReason.MONSTER_SPAWNER_MISSING)

    return monster_spawner


def _require_combat_state(ctx: RunContext[DMToolsDependencies], tool_name: str) -> TurnManager:
    """
    Validate that turn_manager and combat_state are available.

    Returns:
        TurnManager instance (with combat_state guaranteed non-None)

    Raises:
        ToolValidationError: If not in combat
    """
    turn_manager = _require_turn_manager(ctx, tool_name)

    if not turn_manager.combat_state:
        _raise_fail(_get_log(ctx), tool_name, FailureReason.NOT_IN_COMBAT)

    return turn_manager


def _require_combat_phase(
    ctx: RunContext[DMToolsDependencies],
    tool_name: str,
    required_phase: CombatPhase
) -> TurnManager:
    """
    Validate that we're in a specific combat phase.

    Returns:
        TurnManager instance (with correct combat phase guaranteed)

    Raises:
        ToolValidationError: If not in the required phase
    """
    turn_manager = _require_combat_state(ctx, tool_name)

    if turn_manager.combat_state.phase != required_phase:
        _raise_fail(
            _get_log(ctx), tool_name,
            f"{FailureReason.WRONG_PHASE}_{turn_manager.combat_state.phase.value}_need_{required_phase.value}",
            current_phase=turn_manager.combat_state.phase.value
        )

    return turn_manager


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
    log = _get_log(ctx)
    lance_service = ctx.deps.lance_service
    turn_manager = ctx.deps.turn_manager
    rules_cache_service = ctx.deps.rules_cache_service

    log.dm_tool("query_rules_database called", query=query, limit=limit)

    # Get current turn for caching
    current_turn = turn_manager.get_current_turn_context()
    if not current_turn:
        return _fail(log, "query_rules_database", FailureReason.NO_ACTIVE_TURN)

    # Clamp limit to max 10
    limit = min(limit, 10)

    # Auto-detect: short queries try exact match first
    if len(query.split()) <= 10:
        rule_entry = lance_service.get_by_name(query)
        if rule_entry:
            # Exact match found - cache and return single result
            cache_entry = _format_lance_entry_to_cache(rule_entry)
            rules_cache_service.add_to_cache(cache_entry, current_turn)
            log.dm_tool("query_rules_database complete",
                       query=query, results_count=1, match_type="exact", cached=True)
            return _format_rule_for_dm(cache_entry)

    # Fall through to hybrid search (or if query was long/no exact match)
    results = lance_service.search(query, limit=limit)

    if not results:
        log.dm_tool("query_rules_database complete",
                   query=query, results_count=0, match_type="hybrid")
        return f"No rules found matching '{query}'"

    # Cache all results and format
    formatted_results = []
    for result in results:
        cache_entry = _format_lance_entry_to_cache(result)
        rules_cache_service.add_to_cache(cache_entry, current_turn)
        formatted_results.append(_format_rule_for_dm(cache_entry))

    log.dm_tool("query_rules_database complete",
               query=query, results_count=len(results), match_type="hybrid", cached=True)

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
    section: Literal["summary", "attacks", "actions", "features", "traits", "spells", "equipment", "full"],
    ability_name: Optional[str] = None
) -> str:
    """
    Query character or monster ability information with varying levels of detail.

    Use this tool when you need information about a character's or monster's abilities,
    spells, features, or equipment to validate player actions or adjudicate rules.

    The compact sheet in context shows names only. This tool provides:
    - summary: Compact sheet (stats and ability names only)
    - Detailed sections with full descriptions:
      - Spell: casting time, range, components, duration, full description, at higher levels
      - Feature/Trait: source, full description text
      - Attack/Action: attack bonus, damage, damage type, notes
      - Equipment: quantity, weight, full description

    For Characters:
    - summary, attacks, features, spells, equipment, full

    For Monsters:
    - summary: Combat summary (AC, HP, CR)
    - full: Full statblock
    - actions/attacks: Detailed action descriptions
    - traits/features: Special trait descriptions

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        character_id: Character or Monster ID to query (e.g., "fighter", "goblin_1")
        section: Which section to query:
            - "summary": Compact sheet (stats and ability names only)
            - "attacks"/"actions": Detailed attack/action information
            - "features"/"traits": Detailed feature/trait descriptions
            - "spells": Detailed spell information (characters only)
            - "equipment": Detailed equipment with descriptions (characters only)
            - "full": Complete detailed sheet/statblock
        ability_name: Optional specific ability name to look up within the section
                     (e.g., "Fireball" for spells, "Second Wind" for features)
                     If not found, returns the full section as fallback.

    Returns:
        Formatted information string

    Examples:
        Get character sheet:
        >>> await query_character_ability(ctx, "wizard", "summary")

        Get monster statblock:
        >>> await query_character_ability(ctx, "goblin_1", "full")

        Get monster actions:
        >>> await query_character_ability(ctx, "orc_chief", "actions")

        Get specific spell details:
        >>> await query_character_ability(ctx, "wizard", "spells", "Fireball")
    """
    log = _get_log(ctx)
    log.dm_tool("query_character_ability called",
               character_id=character_id, section=section, ability_name=ability_name)

    try:
        state_manager = _require_state_manager(ctx, "query_character_ability")
    except ToolValidationError as e:
        return e.error_message

    # Load character (player character or monster)
    character = state_manager.get_character_by_id(character_id)
    if not character:
        return _fail(log, "query_character_ability",
                    f"{FailureReason.CHARACTER_NOT_FOUND}_{character_id}",
                    character_id=character_id)

    # Log successful lookup
    char_type = "monster" if isinstance(character, Monster) else "player"
    log.dm_tool("query_character_ability found character",
               character_id=character_id, character_type=char_type, section=section)

    # Handle Monster
    if isinstance(character, Monster):
        return _query_monster_ability(character, section, ability_name)

    # Handle Player Character (Character class)
    # `character` variable now refers to the Character object

    # Route to appropriate method
    if section == "summary":
        return character.get_full_sheet()

    elif section == "full":
        return character.get_full_sheet_detailed()

    elif section in ("attacks", "actions"):
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

    elif section in ("features", "traits"):
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
        return f"Unknown section: '{section}'. Use 'summary', 'attacks', 'actions', 'features', 'traits', 'spells', 'equipment', or 'full'."


async def get_available_monsters(
    ctx: RunContext[DMToolsDependencies]
) -> str:
    """
    Get list of available monster templates for encounter selection.

    Call this to see what monsters can be spawned for combat encounters.
    Returns a list of monster types with their basic stats (CR, HP, AC, size, type).

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies

    Returns:
        Formatted list of available monster templates with summary stats

    Example:
        >>> await get_available_monsters(ctx)
        "Available Monster Templates:
         - goblin (CR 1/4, Small humanoid): HP 7, AC 15, Nimble Escape
         - orc (CR 1/2, Medium humanoid): HP 15, AC 13, Aggressive
         - skeleton (CR 1/4, Medium undead): HP 13, AC 13
         ..."
    """
    log = _get_log(ctx)
    log.dm_tool("get_available_monsters called")

    try:
        monster_spawner = _require_monster_spawner(ctx, "get_available_monsters")
    except ToolValidationError as e:
        return e.error_message

    result = monster_spawner.get_available_monsters_context()
    log.dm_tool("get_available_monsters complete")

    return result


async def select_encounter_monsters(
    ctx: RunContext[DMToolsDependencies],
    monsters: List[MonsterSelection]
) -> str:
    """
    Select monsters for an encounter before narrating combat start.

    Call this AFTER reviewing available monsters with get_available_monsters().
    Creates monster instances with stat sheets for initiative, HP tracking, and ability queries.

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        monsters: List of MonsterSelection objects specifying type and count

    Returns:
        Confirmation with created monster IDs and basic combat stats

    Examples:
        Spawn a small goblin ambush:
        >>> await select_encounter_monsters(ctx, [MonsterSelection(type="goblin", count=3)])

        Spawn mixed encounter:
        >>> await select_encounter_monsters(ctx, [
        ...     MonsterSelection(type="orc", count=2),
        ...     MonsterSelection(type="wolf", count=1)
        ... ])

    Side Effects:
        - Creates Monster objects in StateManager
        - Monsters are available for query_character_ability tool
        - Monsters can be targeted in combat and have HP tracked
    """
    log = _get_log(ctx)
    selections_summary = [{"type": m.type, "count": m.count} for m in monsters] if monsters else []
    log.dm_tool("select_encounter_monsters called", selections=selections_summary)

    try:
        monster_spawner = _require_monster_spawner(ctx, "select_encounter_monsters")
    except ToolValidationError as e:
        return e.error_message

    if not monsters:
        return _fail(log, "select_encounter_monsters", FailureReason.NO_MONSTERS_SPECIFIED)

    # Convert MonsterSelection objects to dicts for the spawner
    selections = [{"type": m.type, "count": m.count} for m in monsters]

    # Spawn the monsters
    try:
        created_ids = monster_spawner.spawn_monsters(selections)
    except ValueError as e:
        return _fail(log, "select_encounter_monsters", FailureReason.SPAWN_ERROR,
                    level=LogLevel.ERROR, error=str(e))

    if not created_ids:
        return _fail(log, "select_encounter_monsters", FailureReason.NO_MONSTERS_CREATED)

    log.dm_tool("Monsters spawned", created_ids=created_ids, count=len(created_ids))

    # Register spawned monsters as combat participants if in COMBAT_START phase
    turn_manager = ctx.deps.turn_manager
    if turn_manager and turn_manager.combat_state:
        try:
            participants_added = turn_manager.combat_state.add_participants(created_ids)
            if participants_added:
                log.dm_tool("Monsters added to combat participants",
                           added_ids=participants_added,
                           total_participants=len(turn_manager.combat_state.participants))
        except ValueError as e:
            # Not in COMBAT_START phase - that's OK, monsters can be spawned outside combat
            log.dm_tool("Monsters not added to participants (not in COMBAT_START)",
                       reason=str(e), level=LogLevel.DEBUG)

    # Return summary for DM to use in narrative with prominent reminder
    summary = monster_spawner.get_spawned_summary()
    id_list = ", ".join(created_ids)
    return (
        f"Created {len(created_ids)} monsters:\n{summary}\n\n"
        f"⚠️ IMPORTANT: When describing combat and adding initiative, "
        f"you MUST use ONLY these monster IDs: {id_list}\n"
        f"Do NOT invent different monster types or IDs."
    )


async def add_monster_initiative(
    ctx: RunContext[DMToolsDependencies],
    rolls: List[MonsterInitiativeRoll]
) -> str:
    """
    Add initiative rolls for monsters during COMBAT_START phase.

    Call this after spawning monsters with select_encounter_monsters() and rolling
    their initiative (d20 + DEX modifier for each monster).

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        rolls: List of MonsterInitiativeRoll objects with monster_id and roll

    Returns:
        Confirmation of added rolls and current initiative collection status

    Examples:
        Add initiative for spawned goblins:
        >>> await add_monster_initiative(ctx, [
        ...     MonsterInitiativeRoll(monster_id="goblin_1", roll=15),
        ...     MonsterInitiativeRoll(monster_id="goblin_2", roll=12),
        ...     MonsterInitiativeRoll(monster_id="orc_1", roll=8)
        ... ])
    """
    log = _get_log(ctx)
    rolls_summary = [{"id": r.monster_id, "roll": r.roll} for r in rolls] if rolls else []
    log.dm_tool("add_monster_initiative called", rolls=rolls_summary)

    try:
        turn_manager = _require_turn_manager(ctx, "add_monster_initiative")
        state_manager = _require_state_manager(ctx, "add_monster_initiative")
    except ToolValidationError as e:
        return e.error_message

    if not rolls:
        return _fail(log, "add_monster_initiative", FailureReason.NO_ROLLS_PROVIDED)

    # Get list of valid monster IDs from combat participants for error messages
    valid_monster_ids = []
    if turn_manager.combat_state:
        # Get monster IDs from initiative order (already registered) and participants (in combat)
        registered_ids = {e.character_id for e in turn_manager.combat_state.initiative_order if not e.is_player}
        for participant_id in turn_manager.combat_state.participants:
            # Only include monsters (not players) that haven't registered initiative yet
            monster = state_manager.get_monster(participant_id)
            if monster and participant_id not in registered_ids:
                valid_monster_ids.append(participant_id)

    results = []
    successful_count = 0
    failed_ids = []
    for roll_entry in rolls:
        monster = state_manager.get_monster(roll_entry.monster_id)
        if not monster:
            failed_ids.append(roll_entry.monster_id)
            continue

        # Also verify the monster is a combat participant
        if turn_manager.combat_state and roll_entry.monster_id not in turn_manager.combat_state.participants:
            failed_ids.append(roll_entry.monster_id)
            results.append(f"❌ {roll_entry.monster_id}: Monster exists but is NOT in this combat encounter")
            continue

        # Get display name and DEX modifier for the entry
        display_name = monster.name
        dex_mod = monster.attributes.dexterity.modifier

        try:
            turn_manager.add_initiative_roll(
                character_id=roll_entry.monster_id,
                character_name=display_name,
                roll=roll_entry.roll,
                dex_modifier=dex_mod,
                is_player=False  # Monsters are not player characters
            )
            results.append(f"✅ {display_name} ({roll_entry.monster_id}): Initiative {roll_entry.roll}")
            successful_count += 1
        except ValueError as e:
            results.append(f"❌ {roll_entry.monster_id}: {e}")

    # Add prominent error message for failed IDs with list of valid alternatives
    if failed_ids:
        # Build list of what monsters need initiative
        if valid_monster_ids:
            valid_list = ", ".join(valid_monster_ids)
            error_msg = (
                f"\n\n⚠️ INVALID MONSTER IDs: {', '.join(failed_ids)}\n"
                f"These monsters do not exist in this combat!\n"
                f"You MUST use only the monster IDs returned by select_encounter_monsters().\n"
                f"Monsters still needing initiative: {valid_list}"
            )
        else:
            error_msg = (
                f"\n\n⚠️ INVALID MONSTER IDs: {', '.join(failed_ids)}\n"
                f"These monsters do not exist in this combat!\n"
                f"You MUST use only the monster IDs returned by select_encounter_monsters()."
            )
        results.append(error_msg)

    # Get collection status and check for missing monsters
    if turn_manager.combat_state:
        collected = len(turn_manager.combat_state.initiative_order)
        total = len(turn_manager.combat_state.participants)
        status = f"\n\nInitiative collected: {collected}/{total}"

        # Calculate which monsters are STILL missing initiative after this call
        registered_ids = {e.character_id for e in turn_manager.combat_state.initiative_order}
        missing_monsters = []
        for participant_id in turn_manager.combat_state.participants:
            if participant_id not in registered_ids:
                monster = state_manager.get_monster(participant_id)
                if monster:  # Only count monsters, not players (players roll their own)
                    missing_monsters.append(participant_id)

        # Add PROMINENT warning if monsters are still missing
        if missing_monsters:
            missing_list = ", ".join(missing_monsters)
            status += (
                f"\n\n🚨 ACTION REQUIRED: {len(missing_monsters)} monster(s) still need initiative! 🚨\n"
                f"Missing: {missing_list}\n"
                f"You MUST call add_monster_initiative() for ALL spawned monsters.\n"
                f"Combat CANNOT proceed until all monsters have initiative."
            )

        log.dm_tool("add_monster_initiative complete",
                   added_count=successful_count, collected=collected, total=total,
                   missing_monsters=missing_monsters)
    else:
        status = ""
        log.dm_tool("add_monster_initiative complete", added_count=successful_count)

    return "\n".join(results) + status


async def remove_defeated_participant(
    ctx: RunContext[DMToolsDependencies],
    character_id: str,
    reason: str = "defeated"
) -> str:
    """
    Remove a defeated participant from combat (died, fled, incapacitated, etc.).

    Call this when a combatant is no longer able to participate in combat:
    - Monster/NPC drops to 0 HP (they die)
    - Monster/NPC flees or is banished
    - Player character is permanently incapacitated (not just unconscious)

    The participant will be removed from the initiative order and combat
    will automatically end if one side is eliminated.

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        character_id: The character ID to remove (e.g., "goblin_1", "orc_2")
        reason: Why they're being removed (default: "defeated")

    Returns:
        Status message including whether combat has ended

    Examples:
        Remove a dead goblin:
        >>> await remove_defeated_participant(ctx, "goblin_1", "killed")

        Remove a fleeing enemy:
        >>> await remove_defeated_participant(ctx, "orc_2", "fled the battle")
    """
    log = _get_log(ctx)
    log.dm_tool("remove_defeated_participant called",
               character_id=character_id, reason=reason)

    try:
        turn_manager = _require_combat_state(ctx, "remove_defeated_participant")
    except ToolValidationError as e:
        return e.error_message
    # TODO: handle non hp reasons more robustly.
    # Validate HP before allowing removal (unless reason indicates non-HP removal)
    non_hp_reasons = {"fled", "fled the battle", "banished", "surrendered", "captured", "escaped"}
    if reason.lower() not in non_hp_reasons:
        state_manager = ctx.deps.state_manager
        if state_manager:
            character = state_manager.get_character_by_id(character_id)
            if character:
                # Get current HP - handle both Character (.hp property) and Monster (.hit_points.current)
                if hasattr(character, 'hp'):
                    current_hp = character.hp  # Character has .hp property
                elif hasattr(character, 'hit_points'):
                    current_hp = character.hit_points.current  # Monster has .hit_points.current
                else:
                    current_hp = None

                if current_hp is not None and current_hp > 0:
                    log.dm_tool("remove_defeated_participant blocked - character still has HP",
                               character_id=character_id,
                               current_hp=current_hp,
                               reason=reason)
                    return (f"❌ Cannot remove {character_id}: they still have {current_hp} HP remaining. "
                            f"Only remove participants when they reach 0 HP (defeated/killed) or for "
                            f"non-HP reasons (fled, banished, surrendered, captured, escaped).")

    # Remove the participant from initiative order
    removed = turn_manager.combat_state.remove_participant(character_id)

    if not removed:
        return _fail(log, "remove_defeated_participant",
                    f"{FailureReason.PARTICIPANT_NOT_FOUND}_{character_id}",
                    character_id=character_id)

    # Also remove any queued turns for this character from the turn stack
    turns_removed = turn_manager.remove_queued_turns_for_character(character_id)

    # Log successful removal
    log.combat("Participant removed from combat",
              character_id=character_id, reason=reason,
              turns_removed=turns_removed,
              remaining_players=len(turn_manager.combat_state.get_remaining_player_ids()),
              remaining_monsters=len(turn_manager.combat_state.get_remaining_monster_ids()))

    # Check if combat should end
    result = f"✅ {character_id} has been removed from combat ({reason})."

    players = turn_manager.combat_state.get_remaining_player_ids()
    monsters = turn_manager.combat_state.get_remaining_monster_ids()

    if turn_manager.combat_state.is_combat_over():
        if len(monsters) == 0:
            result += "\n\n⚔️ COMBAT OVER: All enemies have been defeated!"
            result += f"\nPlayers remaining: {len(players)}"
            result += "\n\nCall end_combat() to transition to combat conclusion phase."
        elif len(players) == 0:
            result += "\n\n💀 COMBAT OVER: All player characters have fallen!"
            result += f"\nEnemies remaining: {len(monsters)}"
            result += "\n\nCall end_combat() to transition to combat conclusion phase."

        log.combat("Combat over - one side eliminated",
                  players_remaining=len(players), monsters_remaining=len(monsters))
    else:
        result += f"\nCombat continues: {len(players)} players, {len(monsters)} enemies remaining."

    return result


async def end_combat(
    ctx: RunContext[DMToolsDependencies],
    reason: str = "Combat conditions met"
) -> str:
    """
    Signal that combat should end after current actions resolve.

    This uses DEFERRED ending - combat will actually transition to COMBAT_END
    phase after state extraction runs for the current turn. This ensures the
    final action's damage/effects are properly recorded before combat ends.

    Call this when:
    - All enemies have been defeated (use remove_defeated_participant first)
    - All players have fallen
    - Combat is ended for narrative reasons (enemies surrender, negotiation, etc.)

    Args:
        ctx: PydanticAI RunContext with DMToolsDependencies
        reason: Reason for ending combat (default: "Combat conditions met")

    Returns:
        Confirmation that combat end is pending

    Examples:
        End combat after victory:
        >>> await end_combat(ctx, "All enemies defeated")

        End combat due to surrender:
        >>> await end_combat(ctx, "Enemies surrendered")
    """
    log = _get_log(ctx)
    log.dm_tool("end_combat called (deferred)", reason=reason)

    try:
        turn_manager = _require_combat_phase(ctx, "end_combat", CombatPhase.COMBAT_ROUNDS)
    except ToolValidationError as e:
        return e.error_message

    # Set pending end flag (actual transition happens after state extraction)
    try:
        turn_manager.combat_state.set_pending_end(reason=reason)

        # Get current stats for the response
        players = turn_manager.combat_state.get_remaining_player_ids()
        monsters = turn_manager.combat_state.get_remaining_monster_ids()
        rounds = turn_manager.combat_state.round_number

        log.combat("Combat end pending",
                  reason=reason,
                  rounds_fought=rounds,
                  players_remaining=len(players),
                  monsters_remaining=len(monsters))

        result = f"⚔️ COMBAT ENDING: {reason}\n"
        result += f"Rounds fought: {rounds}\n"
        result += f"Players remaining: {len(players)}\n"
        result += f"Enemies remaining: {len(monsters)}\n"
        result += f"\nCombat will transition to conclusion phase after current step resolves."
        result += f"\nNarrate the conclusion of the final action, then set game_step_completed=True."

        return result

    except ValueError as e:
        return _fail(log, "end_combat", FailureReason.TRANSITION_ERROR, level=LogLevel.ERROR, error=str(e))


def _query_monster_ability(
    monster: Monster,
    section: str,
    ability_name: Optional[str] = None
) -> str:
    """
    Query monster ability information with varying levels of detail.

    Args:
        monster: Monster instance to query
        section: Which section to query (summary, full, actions, traits, etc.)
        ability_name: Optional specific ability name to look up

    Returns:
        Formatted information string
    """
    if section == "summary":
        return monster.get_combat_summary()

    elif section == "full":
        return monster.get_full_statblock()

    elif section in ("actions", "attacks"):
        if ability_name:
            # Find specific action
            for action in monster.actions:
                if action.name.lower() == ability_name.lower():
                    lines = [f"▸ {action.name}"]
                    if action.attack_bonus is not None:
                        lines.append(f"  Attack Bonus: +{action.attack_bonus}")
                    if action.damage:
                        lines.append(f"  Damage: {action.damage.formula} {action.damage.type}")
                    if action.range:
                        range_str = f"{action.range.normal} {action.range.unit}"
                        if action.range.long > 0:
                            range_str += f"/{action.range.long} {action.range.unit}"
                        lines.append(f"  Range: {range_str}")
                    lines.append(f"  Description: {action.description}")
                    return "\n".join(lines)
            # Not found - return full section
            return f"Action '{ability_name}' not found. Here are all actions:\n\n{monster.get_actions_detailed()}"
        return monster.get_actions_detailed()

    elif section in ("traits", "features"):
        if ability_name:
            # Find specific trait
            for trait in monster.special_traits:
                if trait.name.lower() == ability_name.lower():
                    lines = [f"▸ {trait.name}"]
                    lines.append(f"  {trait.description}")
                    return "\n".join(lines)
            # Not found - return full section
            return f"Trait '{ability_name}' not found. Here are all traits:\n\n{monster.get_traits_detailed()}"
        return monster.get_traits_detailed()

    elif section == "spells":
        return f"{monster.name} is a monster. Use 'actions' to see its abilities."

    elif section == "equipment":
        return f"{monster.name} is a monster. Monsters don't have equipment in the same way as characters."

    else:
        return f"Unknown section: '{section}'. For monsters, use 'summary', 'full', 'actions', or 'traits'."


def create_dm_tools(
    lance_service: LanceRulesService,
    turn_manager: TurnManager,
    rules_cache_service: RulesCacheService,
    state_manager: Optional[StateManager] = None,
    monster_spawner: Optional[MonsterSpawner] = None,
    logger: Optional[GameLogger] = None
) -> tuple[list, DMToolsDependencies]:
    """
    Factory function to create DM tools and their dependencies.

    Args:
        lance_service: LanceDB service for rule queries
        turn_manager: Turn manager for getting current turn
        rules_cache_service: Cache service for storing results
        state_manager: Optional StateManager for character ability queries
        monster_spawner: Optional MonsterSpawner for creating monsters in encounters
        logger: Optional GameLogger for tracing tool invocations

    Returns:
        Tuple of (tool_list, dependencies) where:
        - tool_list: List of tool functions to pass to DM agent
        - dependencies: DMToolsDependencies instance to pass to agent.run()

    Usage:
        tools, deps = create_dm_tools(lance_service, turn_manager, cache_service, state_manager, monster_spawner, logger)
        dm_agent = create_dungeon_master_agent(tools=tools)
        result = await dm_agent.process_message(context, deps=deps)
    """
    tools = [query_rules_database, query_character_ability, get_available_monsters, select_encounter_monsters, add_monster_initiative, remove_defeated_participant, end_combat]
    dependencies = DMToolsDependencies(
        lance_service=lance_service,
        turn_manager=turn_manager,
        rules_cache_service=rules_cache_service,
        state_manager=state_manager,
        monster_spawner=monster_spawner,
        logger=logger
    )

    return tools, dependencies

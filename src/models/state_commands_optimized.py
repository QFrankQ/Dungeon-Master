"""
Optimized command-based state updates with orchestrator support.

Improvements over state_change_commands.py:
1. Merged add/remove commands (15 → 11 commands)
2. Unified HP commands (3 → 1)
3. Organized for specialist agents
4. Removed source fields (added in executor instead)
5. Examples in schema instead of full enum bloat

Total: 11 commands divided across 4 specialist agents
"""

from typing import List, Optional, Dict, Literal, Union
from pydantic import BaseModel, Field

from ..characters.dnd_enums import DamageType, Condition
from ..characters.character_components import DurationType


# ==================== HP Commands (1 unified command) ====================
# Used by: HP_AGENT

class HPChangeCommand(BaseModel):
    """Modify character hit points (damage, healing, or temporary HP)."""
    type: Literal["hp_change"] = "hp_change"
    character_id: str
    change: int = Field(..., description="HP change: negative=damage, positive=heal")
    is_temporary: bool = Field(False, description="True if granting temporary HP")
    damage_type: Optional[DamageType] = Field(None, description="Type of damage (only for damage)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "hp_change", "character_id": "aragorn", "change": -8, "damage_type": "slashing"},
                {"type": "hp_change", "character_id": "gandalf", "change": 12},
                {"type": "hp_change", "character_id": "legolas", "change": 5, "is_temporary": True}
            ]
        }


# ==================== Effect Commands (2 unified commands) ====================
# Used by: EFFECT_AGENT

class ConditionCommand(BaseModel):
    """Add or remove a D&D condition."""
    type: Literal["condition"] = "condition"
    character_id: str
    action: Literal["add", "remove"]
    condition: Condition = Field(...,
        description="D&D 5e condition - validated at command creation")

    # Only for action="add"
    duration_type: Optional[DurationType] = Field(None, description="Duration tracking (for add only)")
    duration: Optional[int] = Field(None, description="Duration amount (for add only)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "condition", "character_id": "aragorn", "action": "add",
                 "condition": "poisoned", "duration_type": "rounds", "duration": 3},
                {"type": "condition", "character_id": "aragorn", "action": "remove",
                 "condition": "poisoned"}
            ]
        }


class BuffCommand(BaseModel):
    """Add or remove a buff/debuff with stat modifiers."""
    type: Literal["buff"] = "buff"
    character_id: str
    action: Literal["add", "remove"]
    buff_name: str = Field(...,
        examples=["Bless", "Haste", "Slow", "Enlarge", "Bardic Inspiration"],
        description="Buff/debuff name")

    # Only for action="add"
    duration_type: Optional[DurationType] = Field(None, description="Duration tracking (for add only)")
    duration: Optional[int] = Field(None, description="Duration amount (for add only)")
    modifiers: Dict[str, int] = Field(default_factory=dict,
        description="Stat modifiers like {'attack_rolls': 4} (for add only)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "buff", "character_id": "gimli", "action": "add",
                 "buff_name": "Bless", "duration_type": "concentration", "duration": 10,
                 "modifiers": {"attack_rolls": 4, "saving_throws": 4}},
                {"type": "buff", "character_id": "gimli", "action": "remove",
                 "buff_name": "Bless"}
            ]
        }


# ==================== Resource Commands (4 commands) ====================
# Used by: RESOURCE_AGENT

class SpellSlotCommand(BaseModel):
    """Use or restore spell slots."""
    type: Literal["spell_slot"] = "spell_slot"
    character_id: str
    action: Literal["use", "restore"]
    level: int = Field(..., ge=1, le=9, description="Spell level 1-9")
    spell_name: Optional[str] = Field(None, description="Spell name (for use action)")
    count: int = Field(1, description="Number of slots (for restore action)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "spell_slot", "character_id": "gandalf", "action": "use",
                 "level": 3, "spell_name": "Fireball"},
                {"type": "spell_slot", "character_id": "gandalf", "action": "restore",
                 "level": 2, "count": 1}
            ]
        }


class HitDiceCommand(BaseModel):
    """Use or restore hit dice."""
    type: Literal["hit_dice"] = "hit_dice"
    character_id: str
    action: Literal["use", "restore"]
    count: int = Field(1, ge=1, description="Number of hit dice")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "hit_dice", "character_id": "aragorn", "action": "use", "count": 2},
                {"type": "hit_dice", "character_id": "aragorn", "action": "restore", "count": 3}
            ]
        }


class ItemCommand(BaseModel):
    """Use, add, or remove an item."""
    type: Literal["item"] = "item"
    character_id: str
    action: Literal["use", "add", "remove"]
    item_name: str = Field(..., examples=["Potion of Healing", "Antitoxin", "Rope"])
    quantity: int = Field(1, ge=1, description="Quantity (for add/remove)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "item", "character_id": "gimli", "action": "use",
                 "item_name": "Potion of Healing"},
                {"type": "item", "character_id": "gimli", "action": "add",
                 "item_name": "Gold Coins", "quantity": 50}
            ]
        }


# ==================== State Commands (3 commands) ====================
# Used by: STATE_AGENT

class DeathSaveCommand(BaseModel):
    """Record death save or reset."""
    type: Literal["death_save"] = "death_save"
    character_id: str
    result: Literal["success", "failure", "reset"]
    count: int = Field(1, ge=1, le=3, description="Number of saves (usually 1, 2 for crits)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "death_save", "character_id": "aragorn", "result": "success", "count": 1},
                {"type": "death_save", "character_id": "aragorn", "result": "failure", "count": 2},
                {"type": "death_save", "character_id": "aragorn", "result": "reset", "count": 1}
            ]
        }


class RestCommand(BaseModel):
    """Take a short or long rest."""
    type: Literal["rest"] = "rest"
    character_id: str
    rest_type: Literal["short", "long"]
    hit_dice_spent: int = Field(0, ge=0, description="Hit dice to spend (short rest only)")

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "rest", "character_id": "aragorn", "rest_type": "short", "hit_dice_spent": 2},
                {"type": "rest", "character_id": "gandalf", "rest_type": "long"}
            ]
        }


# ==================== Command Union (11 commands total) ====================

StateCommand = Union[
    # HP (1)
    HPChangeCommand,

    # Effects (2)
    ConditionCommand,
    BuffCommand,

    # Resources (3)
    SpellSlotCommand,
    HitDiceCommand,
    ItemCommand,

    # State (2)
    DeathSaveCommand,
    RestCommand,
]


# ==================== Specialist Agent Result Types ====================

class HPAgentResult(BaseModel):
    """Result from HP specialist agent."""
    commands: List[HPChangeCommand] = Field(default_factory=list)


class EffectAgentResult(BaseModel):
    """Result from Effect specialist agent."""
    commands: List[Union[ConditionCommand, BuffCommand]] = Field(default_factory=list)


class ResourceAgentResult(BaseModel):
    """Result from Resource specialist agent."""
    commands: List[Union[SpellSlotCommand, HitDiceCommand, ItemCommand]] = Field(default_factory=list)


class StateAgentResult(BaseModel):
    """Result from State specialist agent."""
    commands: List[Union[DeathSaveCommand, RestCommand]] = Field(default_factory=list)


# ==================== Main Result Container ====================

class StateCommandResult(BaseModel):
    """
    State extraction result: flat list of 11 command types.
    Can be from single agent or merged from specialist agents.
    """
    commands: List[StateCommand] = Field(default_factory=list)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "commands": [
                        {"type": "hp_change", "character_id": "aragorn", "change": -8, "damage_type": "slashing"},
                        {"type": "condition", "character_id": "aragorn", "action": "add",
                         "condition": "Poisoned", "duration_type": "rounds", "duration": 3},
                        {"type": "spell_slot", "character_id": "gandalf", "action": "use",
                         "level": 3, "spell_name": "Fireball"}
                    ],
                    "notes": "Combat encounter with orcs"
                }
            ]
        }


# ==================== Orchestrator Routing Configuration ====================

AGENT_ROUTING = {
    "hp_agent": {
        "commands": ["hp_change"],
        "result_type": HPAgentResult,
        "keywords": ["damage", "hit", "hurt", "heal", "cure", "regenerate", "temporary hp", "temp hp"],
        "schema_tokens": 50  # Estimated
    },
    "effect_agent": {
        "commands": ["condition", "buff"],
        "result_type": EffectAgentResult,
        "keywords": ["poisoned", "stunned", "blessed", "hasted", "condition", "buff", "effect",
                     "prone", "blinded", "paralyzed", "restrained"],
        "schema_tokens": 80
    },
    "resource_agent": {
        "commands": ["spell_slot", "hit_dice", "item"],
        "result_type": ResourceAgentResult,
        "keywords": ["cast", "spell", "slot", "hit dice", "potion", "item", "use", "consume"],
        "schema_tokens": 50
    },
    "state_agent": {
        "commands": ["death_save", "rest"],
        "result_type": StateAgentResult,
        "keywords": ["death save", "unconscious", "dying", "stable", "rest", "sleep", "short rest", "long rest"],
        "schema_tokens": 40
    }
}


# ==================== Comparison ====================

"""
OPTIMIZATION RESULTS:

Command Count:
- Original (state_change_commands.py): 15 commands
- Optimized: 11 commands (-27%)

Schema Size (estimated):
- Monolithic (all 15 commands): ~300 tokens
- HP_AGENT (1 command): ~50 tokens (-83%)
- EFFECT_AGENT (2 commands): ~80 tokens (-73%)
- RESOURCE_AGENT (3 commands): ~50 tokens (-83%)
- STATE_AGENT (2 commands): ~40 tokens (-87%)

Key Improvements:
1. ✅ Merged add/remove into action field
2. ✅ Unified HP commands (damage/heal/temp)
3. ✅ Removed source fields (added in executor)
4. ✅ Examples instead of full enum bloat
5. ✅ Organized for specialist agent routing
6. ✅ Each specialist sees 1-3 commands vs 15

Trade-offs:
- Some optional fields return (but scoped to action type)
- Need orchestrator to route to specialists
- More complex executor dispatch (handles unified commands)
"""

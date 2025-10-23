"""
Simple, flat command-based state update system.

Design principles:
1. Each command does ONE thing clearly
2. Maximum 2 levels deep (flat structure)
3. Only required fields (no complex optionals)
4. Action-oriented names (Damage, Heal, AddCondition, UseSpellSlot)
5. Small, focused schemas that LLMs can easily generate

Replaces deeply nested state_updates.py with ~10-12 simple command types.
"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field

from ..characters.dnd_enums import DamageType, Condition
from ..characters.charactersheet import DurationType


# ==================== HP Commands (3 commands) ====================

class DamageCommand(BaseModel):
    """Deal damage to a character."""
    type: Literal["damage"] = "damage"
    character_id: str
    amount: int = Field(..., gt=0)
    damage_type: Optional[DamageType] = None
    source: Optional[str] = None


class HealCommand(BaseModel):
    """Heal a character."""
    type: Literal["heal"] = "heal"
    character_id: str
    amount: int = Field(..., gt=0)
    source: Optional[str] = None


class TempHPCommand(BaseModel):
    """Grant temporary hit points."""
    type: Literal["temp_hp"] = "temp_hp"
    character_id: str
    amount: int = Field(..., gt=0)
    source: Optional[str] = None


# ==================== Condition Commands (2 commands) ====================

class AddConditionCommand(BaseModel):
    """Add a D&D condition (poisoned, stunned, etc.)."""
    type: Literal["add_condition"] = "add_condition"
    character_id: str
    condition: str  # Use string for flexibility, can validate against Condition enum
    duration_type: DurationType = DurationType.PERMANENT
    duration: int = 0  # 0 for permanent
    source: str = ""


class RemoveConditionCommand(BaseModel):
    """Remove a D&D condition."""
    type: Literal["remove_condition"] = "remove_condition"
    character_id: str
    condition: str


# ==================== Buff/Debuff Commands (2 commands) ====================

class AddBuffCommand(BaseModel):
    """Add a buff (Bless, Haste, etc.) with stat modifiers."""
    type: Literal["add_buff"] = "add_buff"
    character_id: str
    buff_name: str
    duration_type: DurationType
    duration: int
    source: str
    modifiers: Dict[str, int] = Field(default_factory=dict)  # e.g., {"attack_rolls": 4}


class RemoveBuffCommand(BaseModel):
    """Remove a buff."""
    type: Literal["remove_buff"] = "remove_buff"
    character_id: str
    buff_name: str


# ==================== Spell Slot Commands (2 commands) ====================

class UseSpellSlotCommand(BaseModel):
    """Use a spell slot."""
    type: Literal["use_spell_slot"] = "use_spell_slot"
    character_id: str
    level: int = Field(..., ge=1, le=9)
    spell_name: Optional[str] = None


class RestoreSpellSlotCommand(BaseModel):
    """Restore spell slot(s)."""
    type: Literal["restore_spell_slot"] = "restore_spell_slot"
    character_id: str
    level: int = Field(..., ge=1, le=9)
    count: int = 1


# ==================== Death Save Commands (2 commands) ====================

class DeathSaveCommand(BaseModel):
    """Record a death save (success or failure)."""
    type: Literal["death_save"] = "death_save"
    character_id: str
    success: bool  # True for success, False for failure
    count: int = 1  # Usually 1, but can be 2 for crits


class ResetDeathSavesCommand(BaseModel):
    """Reset death saves (healed/stabilized)."""
    type: Literal["reset_death_saves"] = "reset_death_saves"
    character_id: str


# ==================== Resource Commands (2 commands) ====================

class UseHitDiceCommand(BaseModel):
    """Spend hit dice (usually during short rest)."""
    type: Literal["use_hit_dice"] = "use_hit_dice"
    character_id: str
    count: int = 1


class UseItemCommand(BaseModel):
    """Use/consume an item."""
    type: Literal["use_item"] = "use_item"
    character_id: str
    item_name: str


# ==================== Rest Commands (2 commands) ====================

class ShortRestCommand(BaseModel):
    """Take a short rest."""
    type: Literal["short_rest"] = "short_rest"
    character_id: str
    hit_dice_spent: int = 0


class LongRestCommand(BaseModel):
    """Take a long rest."""
    type: Literal["long_rest"] = "long_rest"
    character_id: str


# ==================== Command Union (15 simple commands total) ====================

StateCommand = Union[
    # HP (3)
    DamageCommand,
    HealCommand,
    TempHPCommand,

    # Conditions (2)
    AddConditionCommand,
    RemoveConditionCommand,

    # Buffs/Debuffs (2)
    AddBuffCommand,
    RemoveBuffCommand,

    # Spell Slots (2)
    UseSpellSlotCommand,
    RestoreSpellSlotCommand,

    # Death Saves (2)
    DeathSaveCommand,
    ResetDeathSavesCommand,

    # Resources (2)
    UseHitDiceCommand,
    UseItemCommand,

    # Rest (2)
    ShortRestCommand,
    LongRestCommand,
]


# ==================== Result Container ====================

class StateCommandResult(BaseModel):
    """
    State extraction result: a flat list of simple commands.

    Structure:
    - Max 2 levels deep
    - 15 command types (each super simple)
    - No complex optional fields
    - Action-oriented and clear
    """
    commands: List[StateCommand] = Field(
        default_factory=list,
        description="List of state update commands"
    )

    notes: Optional[str] = Field(
        None,
        description="Additional extraction notes"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "commands": [
                        {
                            "type": "damage",
                            "character_id": "aragorn",
                            "amount": 8,
                            "damage_type": "slashing",
                            "source": "Orc greataxe"
                        },
                        {
                            "type": "add_condition",
                            "character_id": "aragorn",
                            "condition": "Poisoned",
                            "duration_type": "rounds",
                            "duration": 3,
                            "source": "Orc poisoned blade"
                        },
                        {
                            "type": "use_spell_slot",
                            "character_id": "gandalf",
                            "level": 3,
                            "spell_name": "Fireball"
                        },
                        {
                            "type": "damage",
                            "character_id": "orc_1",
                            "amount": 28,
                            "damage_type": "fire",
                            "source": "Fireball"
                        }
                    ],
                    "notes": "Combat encounter: Aragorn damaged and poisoned, Gandalf casts Fireball"
                }
            ]
        }


# ==================== LLM Prompt Schema (Compact Summary) ====================

COMMAND_SUMMARY = """
Available State Commands (15 types):

HP Commands:
- damage: {character_id, amount, damage_type?, source?}
- heal: {character_id, amount, source?}
- temp_hp: {character_id, amount, source?}

Condition Commands:
- add_condition: {character_id, condition, duration_type, duration, source}
- remove_condition: {character_id, condition}

Buff Commands:
- add_buff: {character_id, buff_name, duration_type, duration, source, modifiers}
- remove_buff: {character_id, buff_name}

Spell Slot Commands:
- use_spell_slot: {character_id, level, spell_name?}
- restore_spell_slot: {character_id, level, count}

Death Save Commands:
- death_save: {character_id, success (true/false), count}
- reset_death_saves: {character_id}

Resource Commands:
- use_hit_dice: {character_id, count}
- use_item: {character_id, item_name}

Rest Commands:
- short_rest: {character_id, hit_dice_spent}
- long_rest: {character_id}

Output Format:
{
  "commands": [
    {"type": "damage", "character_id": "aragorn", "amount": 8, "damage_type": "slashing"},
    {"type": "add_condition", "character_id": "aragorn", "condition": "Poisoned",
     "duration_type": "rounds", "duration": 3, "source": "Orc blade"}
  ],
  "notes": "Brief summary"
}
"""


# ==================== Comparison ====================

"""
BEFORE (state_updates.py) - 5 LEVELS DEEP:
{
    "character_updates": [
        {
            "character_id": "aragorn",
            "hp_update": {
                "damage": 8,
                "damage_type": "slashing"
            },
            "condition_update": {
                "add_conditions": ["poisoned"],
                "condition_details": {
                    "poisoned": {"duration": 3}
                }
            }
        }
    ]
}

AFTER (state_commands.py) - 2 LEVELS DEEP:
{
    "commands": [
        {
            "type": "damage",
            "character_id": "aragorn",
            "amount": 8,
            "damage_type": "slashing"
        },
        {
            "type": "add_condition",
            "character_id": "aragorn",
            "condition": "Poisoned",
            "duration_type": "rounds",
            "duration": 3,
            "source": "Orc blade"
        }
    ]
}

Benefits:
✓ Flat (2 levels max)
✓ Simple (each command has 3-6 fields)
✓ Clear (one command = one action)
✓ Compact (15 simple types vs complex nesting)
✓ Easy to generate for LLMs
✓ Easy to execute (simple dispatch)
"""

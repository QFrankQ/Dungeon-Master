"""
Pydantic models for structured state update data.
These models define what the state extraction agent should return.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

from ..characters.dnd_enums import (
    AbilityScore, Condition, DamageType, HitDieType, 
    CombatStat, CreatureType, ItemRarity, WeaponType,
    ArmorType, SpellLevel, Duration
)


class UpdateType(str, Enum):
    """Types of state updates that can be extracted."""
    HP_CHANGE = "hp_change"
    CONDITION_CHANGE = "condition_change"
    ABILITY_MODIFIER = "ability_modifier"
    INVENTORY_CHANGE = "inventory_change"
    SPELL_SLOT_CHANGE = "spell_slot_change"
    HIT_DICE_CHANGE = "hit_dice_change"
    DEATH_SAVE_CHANGE = "death_save_change"
    COMBAT_STAT_CHANGE = "combat_stat_change"
    CREATE_CHARACTER = "create_character"


class EventType(str, Enum):
    """Types of state change events that can occur - aligned with 4-agent architecture."""
    HP_CHANGE = "hp_change"              # HP damage, healing, temp HP → HPAgent
    EFFECT_APPLIED = "effect_applied"    # Conditions, buffs, debuffs → EffectAgent
    RESOURCE_USAGE = "resource_usage"    # Spell slots, items, hit dice → ResourceAgent
    STATE_CHANGE = "state_change"        # Death saves, rest → StateAgent


class EventDetectionResult(BaseModel):
    """Result from event detection - indicates what types of changes occurred."""
    detected_events: List[EventType] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(None, description="Why these events were detected")


class CombatStateResult(BaseModel):
    """Result from Combat State Extractor - only combat-critical updates."""
    character_updates: List["CombatCharacterUpdate"] = Field(
        default_factory=list,
        description="Combat updates: hp, condition, death_save, combat_stat only"
    )
    combat_info: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class ResourceResult(BaseModel):
    """Result from Resource Extractor - resource consumption and character changes."""
    character_updates: List["ResourceCharacterUpdate"] = Field(
        default_factory=list,
        description="Resource updates: spell_slot, inventory, ability, hit_dice only"
    )
    new_characters: List["CharacterCreation"] = Field(default_factory=list)
    notes: Optional[str] = None


class HPUpdate(BaseModel):
    """Hit point update information."""
    damage: Optional[int] = Field(None, description="Damage to apply (positive number)")
    healing: Optional[int] = Field(None, description="Healing to apply (positive number)")
    temporary_hp: Optional[int] = Field(None, description="Temporary HP to set")
    damage_type: Optional[DamageType] = Field(None, description="Type of damage")



class ConditionUpdate(BaseModel):
    """Condition change information."""
    add_conditions: List[Condition] = Field(default_factory=list, description="Conditions to add")
    remove_conditions: List[Condition] = Field(default_factory=list, description="Conditions to remove")
    condition_details: Dict[str, Any] = Field(default_factory=dict, description="Additional condition info")


class AbilityUpdate(BaseModel):
    """Ability score modifier information."""
    ability: AbilityScore = Field(..., description="Ability to modify")
    modifier: int = Field(..., description="Modifier to apply")
    duration: Optional[Union[int, Duration]] = Field(None, description="Duration in rounds or predefined duration")
    source: Optional[str] = Field(None, description="Source of the modifier")

class ItemUpdate(BaseModel):
    """Individual item update information."""
    name: str = Field(..., description="Item name")
    quantity: int = Field(1, description="Quantity of items")
    item_type: Optional[Union[WeaponType, ArmorType, str]] = Field(None, description="Type of item if applicable")
    rarity: Optional[ItemRarity] = Field(None, description="Item rarity for magic items")
    
class InventoryUpdate(BaseModel):
    """Inventory change information."""
    add_items: List[ItemUpdate] = Field(default_factory=list, description="Items to add")
    remove_items: List[ItemUpdate] = Field(default_factory=list, description="Items to remove")
    use_items: List[str] = Field(default_factory=list, description="Items to mark as used")


class SpellSlotUpdate(BaseModel):
    """Spell slot change information."""
    level: SpellLevel = Field(..., description="Spell slot level")
    change: int = Field(..., description="Change in available slots (negative to use)")
    reason: Optional[str] = Field(None, description="Reason for the change")


class HitDiceUpdate(BaseModel):
    """Hit dice change information."""
    dice_type: HitDieType = Field(..., description="Type of hit die")
    change: int = Field(..., description="Change in available hit dice")
    reason: Optional[str] = Field(None, description="Reason for the change")


class DeathSaveUpdate(BaseModel):
    """Death saving throw update information."""
    success_increment: Optional[int] = Field(None, description="Number of successful saves to add (positive integer)")
    failure_increment: Optional[int] = Field(None, description="Number of failed saves to add (positive integer)")
    reset: Optional[bool] = Field(None, description="Whether to reset all saves to 0")


class CombatStatUpdate(BaseModel):
    """Combat statistic update information."""
    stat: CombatStat = Field(..., description="Combat stat to update")
    value: Union[int, str] = Field(..., description="New value or modifier")
    temporary: bool = Field(True, description="Whether this is a temporary change")
    duration: Optional[Union[int, Duration]] = Field(None, description="Duration in rounds or predefined duration")


class CharacterCreation(BaseModel):
    """New character creation information."""
    name: str = Field(..., description="Character name")
    character_type: CreatureType = Field(..., description="Type of creature")
    basic_stats: Dict[str, Any] = Field(default_factory=dict, description="Basic character stats")
    temporary: bool = Field(True, description="Whether this is a temporary character")


class CharacterUpdate(BaseModel):
    """Complete update information for a single character."""
    character_id: str = Field(..., description="ID of the character to update")
    # character_name: Optional[str] = Field(None, description="Character name (for reference)")

    # Different types of updates
    hp_update: Optional[HPUpdate] = None
    condition_update: Optional[ConditionUpdate] = None
    ability_update: Optional[AbilityUpdate] = None
    inventory_update: Optional[InventoryUpdate] = None
    spell_slot_update: Optional[SpellSlotUpdate] = None
    hit_dice_update: Optional[HitDiceUpdate] = None
    death_save_update: Optional[DeathSaveUpdate] = None
    combat_stat_update: Optional[CombatStatUpdate] = None

    # Metadata
    # reason: Optional[str] = Field(None, description="Reason for the updates")
    # source: Optional[str] = Field(None, description="Source of the changes")


class CombatCharacterUpdate(BaseModel):
    """Character update containing only combat-critical changes."""
    character_id: str = Field(..., description="ID of the character to update")

    # Combat-specific updates only
    hp_update: Optional[HPUpdate] = None
    condition_update: Optional[ConditionUpdate] = None
    death_save_update: Optional[DeathSaveUpdate] = None
    combat_stat_update: Optional[CombatStatUpdate] = None

    # Metadata
    # reason: Optional[str] = Field(None, description="Reason for the updates")
    # source: Optional[str] = Field(None, description="Source of the changes")

    def to_character_update(self) -> CharacterUpdate:
        """Convert to full CharacterUpdate for final result."""
        return CharacterUpdate(
            character_id=self.character_id,
            # character_name=self.character_name,
            hp_update=self.hp_update,
            condition_update=self.condition_update,
            death_save_update=self.death_save_update,
            combat_stat_update=self.combat_stat_update,
            # reason=self.reason,
            # source=self.source
        )


class ResourceCharacterUpdate(BaseModel):
    """Character update containing only resource consumption changes."""
    character_id: str = Field(..., description="ID of the character to update")
    # character_name: Optional[str] = Field(None, description="Character name (for reference)")

    # Resource-specific updates only
    spell_slot_update: Optional[SpellSlotUpdate] = None
    inventory_update: Optional[InventoryUpdate] = None
    ability_update: Optional[AbilityUpdate] = None
    hit_dice_update: Optional[HitDiceUpdate] = None

    # Metadata
    # reason: Optional[str] = Field(None, description="Reason for the updates")
    # source: Optional[str] = Field(None, description="Source of the changes")

    def to_character_update(self) -> CharacterUpdate:
        """Convert to full CharacterUpdate for final result."""
        return CharacterUpdate(
            character_id=self.character_id,
            # character_name=self.character_name,
            spell_slot_update=self.spell_slot_update,
            inventory_update=self.inventory_update,
            ability_update=self.ability_update,
            hit_dice_update=self.hit_dice_update,
            # reason=self.reason,
            # source=self.source
        )


class StateExtractionResult(BaseModel):
    """
    Complete result from the state extraction agent.
    Contains all extracted state changes from a DM narrative.
    """
    character_updates: List[CharacterUpdate] = Field(
        default_factory=list, 
        description="List of character updates to apply"
    )
    
    new_characters: List[CharacterCreation] = Field(
        default_factory=list,
        description="New characters to create"
    )
    
    combat_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Combat-related information (round, initiative, etc.)"
    )
    
    # extracted_from: str = Field(..., description="The original narrative text")
    
    # confidence: float = Field(1.0, description="Confidence in the extraction (0.0-1.0)")
    
    notes: Optional[str] = Field(None, description="Additional notes about the extraction")
    
    modifications: List[str] = Field(
        default_factory=list,
        description="Cross-turn effects or modifications that carry over to parent turns"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "character_updates": [
                        {
                            "character_id": "pc_fighter_1",
                            "character_name": "Gareth",
                            "hp_update": {
                                "damage": 8,
                                "damage_type": "fire"
                            },
                            "condition_update": {
                                "add_conditions": ["burning"]
                            },
                            "reason": "Hit by fireball spell"
                        }
                    ],
                    "new_characters": [],
                    "combat_info": {
                        "round": 3,
                        "current_turn": "wizard_npc"
                    },
                    "extracted_from": "The fireball explodes around Gareth! He takes 8 fire damage and catches fire.",
                    "confidence": 0.95,
                    "notes": "Clear damage and condition application",
                    "modifications": [
                        "Shield spell blocks 3 damage from Alice's attack",
                        "Burning condition will deal 1d4 fire damage at start of next turn"
                    ]
                }
            ]
        }
    )
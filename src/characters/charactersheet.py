from pydantic import BaseModel

class AbilityScores(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    @property
    def modifiers(self) -> dict[str, int]:
        # Using 5e formula: (score - 10) // 2
        return {ab: (score - 10) // 2 for ab, score in self.model_dump().items()}
    
class HitPoints(BaseModel):
    max_hp: int
    current_hp: int
    temp_hp: int = 0

class HitDice(BaseModel):
    total: int  # total number available (e.g., levels)
    used: int = 0

class DeathSaves(BaseModel):
    successes: int = 0
    failures: int = 0

class CombatStats(BaseModel):
    armor_class: int
    initiative: int  # usually Dex modifier + d20 roll
    speed: int  # in feet

class SavingThrows(BaseModel):
    strength: bool = False
    dexterity: bool = False
    constitution: bool = False
    intelligence: bool = False
    wisdom: bool = False
    charisma: bool = False

class Skills(BaseModel):
    acrobatics: bool = False
    animal_handling: bool = False
    arcana: bool = False
    athletics: bool = False
    deception: bool = False
    history: bool = False
    insight: bool = False
    intimidation: bool = False
    investigation: bool = False
    medicine: bool = False
    nature: bool = False
    perception: bool = False
    performance: bool = False
    persuasion: bool = False
    religion: bool = False
    sleight_of_hand: bool = False
    stealth: bool = False
    survival: bool = False

from typing import List, Optional

class CharacterInfo(BaseModel):
    name: str
    player_name: Optional[str]
    background: Optional[str]
    alignment: Optional[str]
    race: Optional[str]
    classes: List[str]  # e.g., ["Fighter", "Rogue"]
    level: int
    experience_points: int
    proficiency_bonus: int
    inspiration: bool = False
    passive_perception: Optional[int] = None

class ProficienciesAndLanguages(BaseModel):
    armor: List[str] = []
    weapons: List[str] = []
    tools: List[str] = []
    languages: List[str] = []

class Feature(BaseModel):
    name: str
    description: str

class FeaturesAndTraits(BaseModel):
    features: List[Feature] = []

class Spellcasting(BaseModel):
    spellcasting_ability: Optional[str]
    spell_save_dc: Optional[int]
    spell_attack_bonus: Optional[int]
    cantrips_known: int = 0
    spells_known: int = 0
    spell_slots_total: dict[str, int] = {}      # e.g. {"1":4, "2":3}
    spell_slots_expended: dict[str, int] = {}

class Character(BaseModel):
    info: CharacterInfo
    ability_scores: AbilityScores
    saving_throws: SavingThrows
    skills: Skills
    hit_points: HitPoints
    hit_dice: HitDice
    death_saves: DeathSaves
    combat_stats: CombatStats
    proficiencies: ProficienciesAndLanguages
    features: FeaturesAndTraits
    spellcasting: Optional[Spellcasting] = None

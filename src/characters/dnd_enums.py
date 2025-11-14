"""
Comprehensive D&D 5e enums for all predefined game values.
Ensures type safety and consistency across the state management system.
"""

from enum import Enum


class AbilityScore(str, Enum):
    """The six core ability scores in D&D 5e."""
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class Condition(str, Enum):
    """All official D&D 5e conditions."""
    BLINDED = "blinded"
    CHARMED = "charmed"
    DEAFENED = "deafened"
    EXHAUSTION = "exhaustion"
    FRIGHTENED = "frightened"
    GRAPPLED = "grappled"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    POISONED = "poisoned"
    PRONE = "prone"
    RESTRAINED = "restrained"
    STUNNED = "stunned"
    UNCONSCIOUS = "unconscious"
    
    # TODO: Additional common conditions
    # CONCENTRATING = "concentrating"
    # DYING = "dying"
    # STABLE = "stable"
    # DEAD = "dead"


class DamageType(str, Enum):
    """All damage types in D&D 5e."""
    # Physical damage types
    BLUDGEONING = "bludgeoning"
    PIERCING = "piercing"
    SLASHING = "slashing"
    
    # Elemental damage types
    ACID = "acid"
    COLD = "cold"
    FIRE = "fire"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    
    # Energy damage types
    FORCE = "force"
    NECROTIC = "necrotic"
    RADIANT = "radiant"
    
    # Mental damage types
    PSYCHIC = "psychic"
    
    # Other damage types
    POISON = "poison"


class School(str, Enum):
    """Schools of magic in D&D 5e."""
    ABJURATION = "abjuration"
    CONJURATION = "conjuration"
    DIVINATION = "divination"
    ENCHANTMENT = "enchantment"
    EVOCATION = "evocation"
    ILLUSION = "illusion"
    NECROMANCY = "necromancy"
    TRANSMUTATION = "transmutation"


class SpellLevel(int, Enum):
    """Spell levels in D&D 5e."""
    CANTRIP = 0
    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5
    SIXTH = 6
    SEVENTH = 7
    EIGHTH = 8
    NINTH = 9


class DiceType(str, Enum):
    """Standard dice types used in D&D."""
    D4 = "d4"
    D6 = "d6"
    D8 = "d8"
    D10 = "d10"
    D12 = "d12"
    D20 = "d20"
    D100 = "d100"


class HitDieType(str, Enum):
    """Hit die types by class."""
    D6 = "d6"   # Sorcerer, Wizard
    D8 = "d8"   # Bard, Cleric, Druid, Monk, Rogue, Warlock
    D10 = "d10" # Fighter, Paladin, Ranger
    D12 = "d12" # Barbarian


class Skill(str, Enum):
    """All skills in D&D 5e with their associated abilities."""
    # Strength
    ATHLETICS = "athletics"
    
    # Dexterity
    ACROBATICS = "acrobatics"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    
    # Intelligence
    ARCANA = "arcana"
    HISTORY = "history"
    INVESTIGATION = "investigation"
    NATURE = "nature"
    RELIGION = "religion"
    
    # Wisdom
    ANIMAL_HANDLING = "animal_handling"
    INSIGHT = "insight"
    MEDICINE = "medicine"
    PERCEPTION = "perception"
    SURVIVAL = "survival"
    
    # Charisma
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"


class Language(str, Enum):
    """Languages in D&D 5e."""
    # Standard languages
    COMMON = "common"
    DWARVISH = "dwarvish"
    ELVISH = "elvish"
    GIANT = "giant"
    GNOMISH = "gnomish"
    GOBLIN = "goblin"
    HALFLING = "halfling"
    ORC = "orc"
    
    # Exotic languages
    ABYSSAL = "abyssal"
    CELESTIAL = "celestial"
    DRACONIC = "draconic"
    DEEP_SPEECH = "deep_speech"
    INFERNAL = "infernal"
    PRIMORDIAL = "primordial"
    SYLVAN = "sylvan"
    UNDERCOMMON = "undercommon"
    
    # Primordial dialects
    AQUAN = "aquan"
    AURAN = "auran"
    IGNAN = "ignan"
    TERRAN = "terran"


class CreatureType(str, Enum):
    """Creature types in D&D 5e."""
    ABERRATION = "aberration"
    BEAST = "beast"
    CELESTIAL = "celestial"
    CONSTRUCT = "construct"
    DRAGON = "dragon"
    ELEMENTAL = "elemental"
    FEY = "fey"
    FIEND = "fiend"
    GIANT = "giant"
    HUMANOID = "humanoid"
    MONSTROSITY = "monstrosity"
    OOZE = "ooze"
    PLANT = "plant"
    UNDEAD = "undead"


class CreatureSize(str, Enum):
    """Creature sizes in D&D 5e."""
    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"
    GARGANTUAN = "gargantuan"


class Alignment(str, Enum):
    """Alignments in D&D 5e."""
    LAWFUL_GOOD = "lawful_good"
    NEUTRAL_GOOD = "neutral_good"
    CHAOTIC_GOOD = "chaotic_good"
    LAWFUL_NEUTRAL = "lawful_neutral"
    TRUE_NEUTRAL = "true_neutral"
    CHAOTIC_NEUTRAL = "chaotic_neutral"
    LAWFUL_EVIL = "lawful_evil"
    NEUTRAL_EVIL = "neutral_evil"
    CHAOTIC_EVIL = "chaotic_evil"
    UNALIGNED = "unaligned"


class CharacterClass(str, Enum):
    """Character classes in D&D 5e."""
    ARTIFICER = "artificer"
    BARBARIAN = "barbarian"
    BARD = "bard"
    CLERIC = "cleric"
    DRUID = "druid"
    FIGHTER = "fighter"
    MONK = "monk"
    PALADIN = "paladin"
    RANGER = "ranger"
    ROGUE = "rogue"
    SORCERER = "sorcerer"
    WARLOCK = "warlock"
    WIZARD = "wizard"


class Race(str, Enum):
    """Character races in D&D 5e (core races)."""
    DRAGONBORN = "dragonborn"
    DWARF = "dwarf"
    ELF = "elf"
    GNOME = "gnome"
    HALF_ELF = "half_elf"
    HALFLING = "halfling"
    HALF_ORC = "half_orc"
    HUMAN = "human"
    TIEFLING = "tiefling"
    
    # Additional common races
    AARAKOCRA = "aarakocra"
    AASIMAR = "aasimar"
    BUGBEAR = "bugbear"
    CENTAUR = "centaur"
    CHANGELING = "changeling"
    FIRBOLG = "firbolg"
    GENASI = "genasi"
    GITHYANKI = "githyanki"
    GITHZERAI = "githzerai"
    GOBLIN = "goblin"
    GOLIATH = "goliath"
    HOBGOBLIN = "hobgoblin"
    KENKU = "kenku"
    KOBOLD = "kobold"
    LIZARDFOLK = "lizardfolk"
    MINOTAUR = "minotaur"
    ORC = "orc"
    TABAXI = "tabaxi"
    TORTLE = "tortle"
    TRITON = "triton"
    YUAN_TI_PUREBLOOD = "yuan_ti_pureblood"


class ArmorType(str, Enum):
    """Armor types in D&D 5e."""
    # Light armor
    PADDED = "padded"
    LEATHER = "leather"
    STUDDED_LEATHER = "studded_leather"
    
    # Medium armor
    HIDE = "hide"
    CHAIN_SHIRT = "chain_shirt"
    SCALE_MAIL = "scale_mail"
    BREASTPLATE = "breastplate"
    HALF_PLATE = "half_plate"
    
    # Heavy armor
    RING_MAIL = "ring_mail"
    CHAIN_MAIL = "chain_mail"
    SPLINT = "splint"
    PLATE = "plate"
    
    # Shields
    SHIELD = "shield"


class WeaponType(str, Enum):
    """Weapon types in D&D 5e."""
    # Simple melee weapons
    CLUB = "club"
    DAGGER = "dagger"
    DART = "dart"
    JAVELIN = "javelin"
    LIGHT_HAMMER = "light_hammer"
    MACE = "mace"
    QUARTERSTAFF = "quarterstaff"
    SICKLE = "sickle"
    SPEAR = "spear"
    
    # Simple ranged weapons
    CROSSBOW_LIGHT = "crossbow_light"
    SHORTBOW = "shortbow"
    SLING = "sling"
    
    # Martial melee weapons
    BATTLEAXE = "battleaxe"
    FLAIL = "flail"
    GLAIVE = "glaive"
    GREATAXE = "greataxe"
    GREATSWORD = "greatsword"
    HALBERD = "halberd"
    LANCE = "lance"
    LONGSWORD = "longsword"
    MAUL = "maul"
    MORNINGSTAR = "morningstar"
    PIKE = "pike"
    RAPIER = "rapier"
    SCIMITAR = "scimitar"
    SHORTSWORD = "shortsword"
    TRIDENT = "trident"
    WAR_PICK = "war_pick"
    WARHAMMER = "warhammer"
    WHIP = "whip"
    
    # Martial ranged weapons
    BLOWGUN = "blowgun"
    CROSSBOW_HAND = "crossbow_hand"
    CROSSBOW_HEAVY = "crossbow_heavy"
    LONGBOW = "longbow"
    NET = "net"


class WeaponProperty(str, Enum):
    """Weapon properties in D&D 5e."""
    AMMUNITION = "ammunition"
    FINESSE = "finesse"
    HEAVY = "heavy"
    LIGHT = "light"
    LOADING = "loading"
    RANGE = "range"
    REACH = "reach"
    SPECIAL = "special"
    THROWN = "thrown"
    TWO_HANDED = "two_handed"
    VERSATILE = "versatile"


class CombatStat(str, Enum):
    """Combat statistics that can be modified."""
    ARMOR_CLASS = "armor_class"
    INITIATIVE = "initiative"
    SPEED = "speed"
    # FLYING_SPEED = "flying_speed"
    # SWIMMING_SPEED = "swimming_speed"
    # CLIMBING_SPEED = "climbing_speed"
    # BURROWING_SPEED = "burrowing_speed"
    # PROFICIENCY_BONUS = "proficiency_bonus"


class RestType(str, Enum):
    """Types of rest in D&D 5e."""
    SHORT = "short"
    LONG = "long"


class CurrencyType(str, Enum):
    """Currency types in D&D 5e."""
    COPPER = "cp"
    SILVER = "sp"
    ELECTRUM = "ep"
    GOLD = "gp"
    PLATINUM = "pp"


class ItemRarity(str, Enum):
    """Magic item rarity in D&D 5e."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


class AdvantageType(str, Enum):
    """Advantage/disadvantage states."""
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class Duration(str, Enum):
    """Common spell and effect durations."""
    INSTANTANEOUS = "instantaneous"
    UNTIL_END_OF_TURN = "until_end_of_turn"
    UNTIL_START_OF_NEXT_TURN = "until_start_of_next_turn"
    ONE_ROUND = "1_round"
    ONE_MINUTE = "1_minute"
    TEN_MINUTES = "10_minutes"
    ONE_HOUR = "1_hour"
    EIGHT_HOURS = "8_hours"
    TWENTY_FOUR_HOURS = "24_hours"
    UNTIL_DISPELLED = "until_dispelled"
    PERMANENT = "permanent"


class Environment(str, Enum):
    """Environmental conditions and terrains."""
    NORMAL = "normal"
    DIFFICULT_TERRAIN = "difficult_terrain"
    UNDERWATER = "underwater"
    DARKNESS = "darkness"
    DIM_LIGHT = "dim_light"
    BRIGHT_LIGHT = "bright_light"
    HEAVILY_OBSCURED = "heavily_obscured"
    LIGHTLY_OBSCURED = "lightly_obscured"


class Cover(str, Enum):
    """Cover types in combat."""
    NONE = "none"
    HALF = "half"
    THREE_QUARTERS = "three_quarters"
    TOTAL = "total"
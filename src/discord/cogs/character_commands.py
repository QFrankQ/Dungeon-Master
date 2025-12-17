"""
Character Commands Cog

Handles character management commands: /character, /register, /switch, /who, /upload-character
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from pathlib import Path

from src.discord.utils.session_pool import get_session_pool


class CharacterCommands(commands.Cog):
    """Commands for character management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_pool = get_session_pool()

    def _get_session_or_error(self, interaction: discord.Interaction):
        """Helper to get session or return error message."""
        session_context = self.session_pool.get(interaction.channel_id)
        if not session_context:
            return None, "⚠️ No active game session in this channel. Use `/start` to begin."
        return session_context, None

    def _validate_character_json(self, data: dict) -> tuple[bool, str]:
        """
        Validate character JSON structure (permissive - allows extra fields).

        Args:
            data: Parsed JSON data

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required top-level fields
        required_fields = {
            "character_id": str,
            "info": dict,
            "ability_scores": dict,
            "hit_points": dict,
            "combat_stats": dict
        }

        for field, expected_type in required_fields.items():
            if field not in data:
                return False, f"Missing required field: '{field}'"
            if not isinstance(data[field], expected_type):
                return False, f"Field '{field}' must be of type {expected_type.__name__}"

        # Validate ability scores (must be 1-30)
        ability_scores = data["ability_scores"]
        required_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

        for ability in required_abilities:
            if ability not in ability_scores:
                return False, f"Missing ability score: '{ability}'"
            score = ability_scores[ability]
            if not isinstance(score, int) or not (1 <= score <= 30):
                return False, f"Ability score '{ability}' must be an integer between 1 and 30"

        # Validate info nested fields
        info = data["info"]
        required_info = {"name": str, "level": int, "classes": list}

        for field, expected_type in required_info.items():
            if field not in info:
                return False, f"Missing required info field: '{field}'"
            if not isinstance(info[field], expected_type):
                return False, f"Info field '{field}' must be of type {expected_type.__name__}"

        # Validate hit_points nested fields
        hp = data["hit_points"]
        required_hp = {"current_hp": int, "maximum_hp": int}

        for field, expected_type in required_hp.items():
            if field not in hp:
                return False, f"Missing required hit_points field: '{field}'"
            if not isinstance(hp[field], expected_type):
                return False, f"Hit_points field '{field}' must be of type {expected_type.__name__}"

        # Validate combat_stats nested fields
        combat = data["combat_stats"]
        required_combat = {"armor_class": int, "initiative_bonus": int, "speed": int}

        for field, expected_type in required_combat.items():
            if field not in combat:
                return False, f"Missing required combat_stats field: '{field}'"
            if not isinstance(combat[field], expected_type):
                return False, f"Combat_stats field '{field}' must be of type {expected_type.__name__}"

        return True, ""

    @app_commands.command(name="character", description="View your character's stats and status")
    async def show_character(self, interaction: discord.Interaction):
        """Show character status (mirrors demo_terminal.py:402-480)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        session_manager = session_context.session_manager
        player_id = str(interaction.user.id)

        # Get character ID from registry
        character_id = session_manager.player_character_registry.get_character_id_by_player_id(player_id)

        if not character_id:
            await interaction.response.send_message(
                f"⚠️ No character registered for you.\n"
                f"Use `/register <character_id>` to link a character.\n"
                f"Available characters: fighter, wizard, cleric",
                ephemeral=True
            )
            return

        # Load character from state manager
        character = session_manager.state_manager.get_character(character_id)

        if not character:
            await interaction.response.send_message(
                f"❌ Character '{character_id}' not found",
                ephemeral=True
            )
            return

        # Build character sheet display
        classes_str = "/".join([c.value.title() for c in character.info.classes])
        char_sheet = (
            f"**🧙 CHARACTER: {character.info.name}**\n"
            f"*{classes_str} Level {character.info.level}*\n\n"
        )

        # HP Status with visual bar
        hp_percent = (character.hit_points.current_hp / character.hit_points.maximum_hp) * 100
        hp_bar_filled = int(hp_percent / 5)  # 20 char bar (5% per char)
        hp_bar = "█" * hp_bar_filled + "░" * (20 - hp_bar_filled)
        char_sheet += f"**HP:** [{hp_bar}] {character.hit_points.current_hp}/{character.hit_points.maximum_hp} ({hp_percent:.0f}%)\n"
        if character.hit_points.temporary_hp > 0:
            char_sheet += f"Temp HP: +{character.hit_points.temporary_hp}\n"
        char_sheet += "\n"

        # Combat Stats
        char_sheet += (
            f"**AC:** {character.combat_stats.armor_class} | "
            f"**Initiative:** +{character.combat_stats.initiative_bonus} | "
            f"**Speed:** {character.combat_stats.speed} ft\n\n"
        )

        # Ability Scores
        char_sheet += "**Ability Scores:**\n"
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(character.ability_scores, ability)
            modifier = (score - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
            char_sheet += f"• {ability.title()[:3].upper()}: {score} ({mod_str})\n"
        char_sheet += "\n"

        # Active Effects
        if character.active_effects:
            char_sheet += "**Active Effects:**\n"
            for effect in character.active_effects:
                duration_str = f"{effect.duration} rounds" if effect.duration else "Permanent"
                conc_str = " [Concentration]" if hasattr(effect, 'requires_concentration') and effect.requires_concentration else ""
                char_sheet += f"• {effect.name}: {effect.summary}{conc_str} ({duration_str})\n"
            char_sheet += "\n"

        # Spell Slots (if spellcaster)
        if hasattr(character, 'spellcasting') and character.spellcasting and character.spellcasting.spell_slots:
            char_sheet += "**Spell Slots:**\n"
            for level in range(1, 10):
                total_slots = character.spellcasting.spell_slots.get(str(level), 0)
                expended = character.spellcasting.spell_slots_expended.get(str(level), 0)
                current = total_slots - expended
                if total_slots > 0:
                    slot_display = "●" * current + "○" * expended
                    char_sheet += f"• Level {level}: {slot_display} ({current}/{total_slots})\n"
            char_sheet += "\n"

        # Hit Dice
        char_sheet += f"**Hit Dice:** {character.hit_dice.total - character.hit_dice.used}/{character.hit_dice.total} {character.hit_dice.die_type}\n\n"

        # Death Saves (if any recorded)
        if character.death_saves.successes > 0 or character.death_saves.failures > 0:
            success_display = "●" * character.death_saves.successes + "○" * (3 - character.death_saves.successes)
            failure_display = "●" * character.death_saves.failures + "○" * (3 - character.death_saves.failures)
            char_sheet += (
                f"**Death Saves:**\n"
                f"• Successes: {success_display}\n"
                f"• Failures: {failure_display}\n"
            )

        await interaction.response.send_message(char_sheet, ephemeral=True)

    @app_commands.command(name="register", description="Register or switch to a character")
    @app_commands.describe(character_id="Character ID (use /who to see available characters)")
    async def register_character(self, interaction: discord.Interaction, character_id: str):
        """Register character (mirrors demo_terminal.py:482-500)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        session_manager = session_context.session_manager
        player_id = str(interaction.user.id)

        # Verify character exists
        character = session_manager.state_manager.load_character(character_id)
        if not character:
            await interaction.response.send_message(
                f"❌ Character '{character_id}' not found\n"
                f"Use `/who` to see available characters or `/upload-character` to upload your own.",
                ephemeral=True
            )
            return

        # Register mapping
        session_manager.player_character_registry.register_player_character(player_id, character_id)
        classes_str = "/".join([c.value.title() for c in character.info.classes])

        await interaction.response.send_message(
            f"✅ Registered '{character.info.name}' ({classes_str} Level {character.info.level}) to {interaction.user.mention}\n"
            f"Use `/character` to view character status"
        )

    @app_commands.command(name="switch", description="Switch to a different character")
    @app_commands.describe(character_id="Character ID to switch to")
    async def switch_character(self, interaction: discord.Interaction, character_id: str):
        """Switch character (alias for /register)."""
        await self.register_character(interaction, character_id)

    @app_commands.command(name="who", description="Show all available characters")
    async def show_characters(self, interaction: discord.Interaction):
        """Show available characters."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        session_manager = session_context.session_manager

        # Get character directory from session's temp directory
        char_dir = session_context.temp_character_dir or "src/characters"

        # Dynamically discover all character JSON files
        all_char_files = []
        if os.path.exists(char_dir):
            all_char_files = [f[:-5] for f in os.listdir(char_dir) if f.endswith('.json')]

        # Separate built-in from custom
        builtin_chars = ["fighter", "wizard", "cleric"]
        builtin_available = [c for c in all_char_files if c in builtin_chars]
        custom_available = [c for c in all_char_files if c not in builtin_chars]

        who_text = "**🎭 Available Characters**\n\n"

        # Show built-in characters
        if builtin_available:
            who_text += "**Built-in:**\n"
            for char_id in builtin_available:
                character = session_manager.state_manager.load_character(char_id)
                if character:
                    classes_str = "/".join([c.value.title() for c in character.info.classes])
                    who_text += (
                        f"• **{char_id}**: {character.info.name} "
                        f"({classes_str} Level {character.info.level})\n"
                    )
            who_text += "\n"

        # Show custom characters
        if custom_available:
            who_text += "**Custom (Uploaded):**\n"
            for char_id in custom_available:
                character = session_manager.state_manager.load_character(char_id)
                if character:
                    classes_str = "/".join([c.value.title() for c in character.info.classes])
                    who_text += (
                        f"• **{char_id}**: {character.info.name} "
                        f"({classes_str} Level {character.info.level})\n"
                    )
            who_text += "\n"

        who_text += "Use `/register <character_id>` to register a character!\n"
        who_text += "Use `/upload-character` to upload your own character JSON file."

        await interaction.response.send_message(who_text, ephemeral=True)

    @app_commands.command(name="upload-character", description="Upload a custom character JSON file")
    @app_commands.describe(character_file="JSON file containing character data")
    async def upload_character(self, interaction: discord.Interaction, character_file: discord.Attachment):
        """Upload a custom character JSON file."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        # Defer response as file processing may take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            # Validate file type
            if not character_file.filename.endswith('.json'):
                await interaction.followup.send(
                    "❌ Invalid file type. Please upload a `.json` file.",
                    ephemeral=True
                )
                return

            # Validate file size (max 1MB)
            if character_file.size > 1_000_000:
                await interaction.followup.send(
                    "❌ File too large. Maximum file size is 1MB.",
                    ephemeral=True
                )
                return

            # Download and parse JSON
            file_bytes = await character_file.read()
            try:
                data = json.loads(file_bytes.decode('utf-8'))
            except json.JSONDecodeError as e:
                await interaction.followup.send(
                    f"❌ Invalid JSON file: {str(e)}",
                    ephemeral=True
                )
                return

            # Validate character structure
            is_valid, error_msg = self._validate_character_json(data)
            if not is_valid:
                await interaction.followup.send(
                    f"❌ Invalid character structure: {error_msg}\n\n"
                    f"Please ensure your JSON file has all required fields.",
                    ephemeral=True
                )
                return

            # Prevent overwriting built-in characters
            character_id = data["character_id"]
            builtin_chars = ["fighter", "wizard", "cleric"]
            if character_id in builtin_chars:
                await interaction.followup.send(
                    f"❌ Cannot upload a character with ID '{character_id}' - this is a built-in character.\n"
                    f"Please use a different character_id in your JSON file.",
                    ephemeral=True
                )
                return

            # Save to session's temp character directory
            char_dir = session_context.temp_character_dir or "src/characters"
            os.makedirs(char_dir, exist_ok=True)

            char_file_path = Path(char_dir) / f"{character_id}.json"

            with open(char_file_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Verify the character can be loaded
            session_manager = session_context.session_manager
            character = session_manager.state_manager.load_character(character_id)

            if not character:
                await interaction.followup.send(
                    f"❌ Failed to load uploaded character. Please check your JSON structure.",
                    ephemeral=True
                )
                return

            # Success!
            classes_str = "/".join([c.value.title() for c in character.info.classes])
            await interaction.followup.send(
                f"✅ **Character Uploaded Successfully!**\n\n"
                f"**ID:** {character_id}\n"
                f"**Name:** {character.info.name}\n"
                f"**Class/Level:** {classes_str} Level {character.info.level}\n\n"
                f"Use `/register {character_id}` to play as this character!\n\n"
                f"⚠️ **Note:** This character will be deleted when the session ends via `/end`.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error uploading character: {str(e)}",
                ephemeral=True
            )
            import traceback
            traceback.print_exc()


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(CharacterCommands(bot))

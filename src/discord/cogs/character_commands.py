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
        Supports new format with nested ability_scores and combat_stats.

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
            "combat_stats": dict
        }

        for field, expected_type in required_fields.items():
            if field not in data:
                return False, f"Missing required field: '{field}'"
            if not isinstance(data[field], expected_type):
                return False, f"Field '{field}' must be of type {expected_type.__name__}"

        # Validate ability scores - supports both old (int) and new ({score: int}) format
        ability_scores = data["ability_scores"]
        required_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

        for ability in required_abilities:
            if ability not in ability_scores:
                return False, f"Missing ability score: '{ability}'"

            ability_data = ability_scores[ability]
            # New format: {"score": 18}
            if isinstance(ability_data, dict):
                if "score" not in ability_data:
                    return False, f"Ability '{ability}' must have 'score' field"
                score = ability_data["score"]
                if not isinstance(score, int) or not (1 <= score <= 30):
                    return False, f"Ability score '{ability}' must be an integer between 1 and 30"
            # Old format: 18 (still accepted for backward compatibility)
            elif isinstance(ability_data, int):
                if not (1 <= ability_data <= 30):
                    return False, f"Ability score '{ability}' must be an integer between 1 and 30"
            else:
                return False, f"Invalid ability score format for '{ability}'"

        # Validate info nested fields - supports both old (level) and new (total_level, classes) format
        info = data["info"]
        if "name" not in info or not isinstance(info["name"], str):
            return False, "Missing required info field: 'name'"
        if "classes" not in info or not isinstance(info["classes"], list):
            return False, "Missing required info field: 'classes'"

        # Validate classes - each entry should be a dict with class_name and level (new format)
        # or just strings (old format with separate level field)
        for i, cls_entry in enumerate(info["classes"]):
            if isinstance(cls_entry, dict):
                # New format: {"class_name": "Fighter", "level": 5}
                if "class_name" not in cls_entry:
                    return False, f"Class entry {i} missing 'class_name'"
                if "level" not in cls_entry or not isinstance(cls_entry["level"], int):
                    return False, f"Class entry {i} missing or invalid 'level'"
            elif isinstance(cls_entry, str):
                # Old format: ["fighter", "wizard"] with separate level field
                if "level" not in info:
                    return False, "Old format requires 'level' field in info"
            else:
                return False, f"Invalid class entry format at index {i}"

        # Validate combat_stats nested fields
        combat = data["combat_stats"]
        if "armor_class" not in combat or not isinstance(combat["armor_class"], int):
            return False, "Missing required combat_stats field: 'armor_class'"

        # New format has hit_points nested in combat_stats
        if "hit_points" in combat:
            hp = combat["hit_points"]
            # New format: {maximum: int, current: int}
            if "maximum" not in hp or "current" not in hp:
                return False, "combat_stats.hit_points must have 'maximum' and 'current'"
        # Old format has hit_points at top level
        elif "hit_points" in data:
            hp = data["hit_points"]
            # Old format: {maximum_hp: int, current_hp: int}
            if not ("maximum_hp" in hp or "maximum" in hp):
                return False, "hit_points must have 'maximum_hp' or 'maximum'"
            if not ("current_hp" in hp or "current" in hp):
                return False, "hit_points must have 'current_hp' or 'current'"
        else:
            return False, "Missing hit_points (either in combat_stats or at top level)"

        # Speed can be int (old) or object (new format)
        if "speed" in combat:
            speed = combat["speed"]
            if not isinstance(speed, (int, dict)):
                return False, "combat_stats.speed must be an int or object"

        return True, ""

    def _get_classes_display(self, character) -> str:
        """Get class display string for character (supports new CharacterClassEntry format)."""
        classes_parts = []
        for cls_entry in character.info.classes:
            if hasattr(cls_entry, 'class_name'):
                # New format: CharacterClassEntry
                subclass_str = f" ({cls_entry.subclass})" if cls_entry.subclass else ""
                classes_parts.append(f"{cls_entry.class_name}{subclass_str} {cls_entry.level}")
            else:
                # Old format: enum value
                classes_parts.append(cls_entry.value.title())
        return "/".join(classes_parts)

    def _get_total_level(self, character) -> int:
        """Get total character level (supports new format with per-class levels)."""
        if hasattr(character.info, 'total_level') and character.info.total_level:
            return character.info.total_level
        # Fallback: sum of class levels or single level field
        if character.info.classes and hasattr(character.info.classes[0], 'level'):
            return sum(c.level for c in character.info.classes)
        return getattr(character.info, 'level', 1)

    def _get_speed_display(self, character) -> str:
        """Get speed display string (supports new Speed format with multiple movement types)."""
        speed = character.combat_stats.speed
        if hasattr(speed, 'walk') and speed.walk:
            parts = []
            if speed.walk:
                parts.append(f"{speed.walk.value} ft")
            if speed.fly:
                parts.append(f"fly {speed.fly.value} ft")
            if speed.swim:
                parts.append(f"swim {speed.swim.value} ft")
            if speed.climb:
                parts.append(f"climb {speed.climb.value} ft")
            if speed.burrow:
                parts.append(f"burrow {speed.burrow.value} ft")
            return ", ".join(parts) if parts else "0 ft"
        # Old format: single int
        return f"{speed} ft"

    @app_commands.command(name="character", description="View your character's stats and status")
    async def show_character(self, interaction: discord.Interaction):
        """Show character status using Character's built-in summary methods."""
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

        # Use Character's get_full_sheet() method for display
        char_sheet = f"**🧙 {character.info.name}**\n\n```\n{character.get_full_sheet()}\n```"

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
        classes_str = self._get_classes_display(character)

        await interaction.response.send_message(
            f"✅ Registered '{character.info.name}' ({classes_str}) to {interaction.user.mention}\n"
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
                    classes_str = self._get_classes_display(character)
                    who_text += (
                        f"• **{char_id}**: {character.info.name} "
                        f"({classes_str})\n"
                    )
            who_text += "\n"

        # Show custom characters
        if custom_available:
            who_text += "**Custom (Uploaded):**\n"
            for char_id in custom_available:
                character = session_manager.state_manager.load_character(char_id)
                if character:
                    classes_str = self._get_classes_display(character)
                    who_text += (
                        f"• **{char_id}**: {character.info.name} "
                        f"({classes_str})\n"
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
            classes_str = self._get_classes_display(character)
            await interaction.followup.send(
                f"✅ **Character Uploaded Successfully!**\n\n"
                f"**ID:** {character_id}\n"
                f"**Name:** {character.info.name}\n"
                f"**Class/Level:** {classes_str}\n\n"
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

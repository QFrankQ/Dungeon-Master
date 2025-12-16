"""
Character Commands Cog

Handles character management commands: /character, /register, /switch, /who
"""

import discord
from discord import app_commands
from discord.ext import commands

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
    @app_commands.describe(character_id="Character ID (fighter, wizard, or cleric)")
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
                f"Available characters: fighter, wizard, cleric",
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

        # Get available character IDs
        available_chars = ["fighter", "wizard", "cleric"]

        who_text = "**🎭 Available Characters**\n\n"

        for char_id in available_chars:
            character = session_manager.state_manager.load_character(char_id)
            if character:
                classes_str = "/".join([c.value.title() for c in character.info.classes])
                who_text += (
                    f"• **{char_id}**: {character.info.name} "
                    f"({classes_str} Level {character.info.level})\n"
                )

        who_text += "\nUse `/register <character_id>` to register a character!"

        await interaction.response.send_message(who_text, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(CharacterCommands(bot))

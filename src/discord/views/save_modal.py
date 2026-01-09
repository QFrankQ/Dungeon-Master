"""
Saving Throw Views for D&D combat.

Provides views and modals for saving throw collection:
- Button to open save modal
- Hybrid manual/auto-roll support
- Progress tracking for AOE effects
- Support for different save types (DEX, CON, WIS, etc.)

Features:
- Auto-roll with appropriate modifier
- Track successes/failures
- Support for partial party saves (subset affected)
"""

import discord
from discord.ui import View, Button, Modal, TextInput
from typing import List, Dict, Optional, Callable, Any
import random


class SaveModal(Modal):
    """
    Modal for submitting a saving throw.

    Supports hybrid manual/auto-roll:
    - Enter a number for manual roll
    - Leave blank for auto-roll (d20 + save modifier)
    """

    manual_roll = TextInput(
        label="Your Roll (leave blank for auto-roll)",
        placeholder="e.g., 14",
        required=False,
        max_length=2
    )

    def __init__(
        self,
        view: 'SaveView',
        character_name: str,
        save_type: str,
        modifier: int = 0,
        dc: Optional[int] = None
    ):
        """
        Initialize the save modal.

        Args:
            view: Parent SaveView
            character_name: Name of the character rolling
            save_type: Type of save (e.g., "DEX", "CON", "WIS")
            modifier: Save modifier to add for auto-rolls
            dc: Difficulty Class for the save (optional)
        """
        super().__init__(title=f"{save_type} Saving Throw")
        self.view = view
        self.character_name = character_name
        self.save_type = save_type
        self.modifier = modifier
        self.dc = dc

    async def on_submit(self, interaction: discord.Interaction):
        """Handle saving throw submission."""
        try:
            # Determine roll value
            if self.manual_roll.value and self.manual_roll.value.strip():
                try:
                    roll = int(self.manual_roll.value.strip())
                    source = "manual"
                except ValueError:
                    await interaction.response.send_message(
                        "Invalid roll value! Please enter a number.",
                        ephemeral=True
                    )
                    return
            else:
                # Auto-roll: d20 + save modifier
                base_roll = random.randint(1, 20)
                roll = base_roll + self.modifier
                source = f"auto (d20={base_roll} + {self.save_type}={self.modifier})"

            # Determine success/failure if DC is known
            success = None
            result_text = ""
            if self.dc is not None:
                success = roll >= self.dc
                result_text = " - **SUCCESS!**" if success else " - **FAILURE!**"

            # Store the roll in the parent view
            self.view.collected[self.character_name] = {
                "roll": roll,
                "source": source,
                "modifier": self.modifier,
                "save_type": self.save_type,
                "success": success,
            }

            # Build response message
            source_text = f" ({source})" if source != "manual" else ""
            dc_text = f" vs DC {self.dc}" if self.dc else ""

            await interaction.response.send_message(
                f"🎲 **{self.character_name}** rolls **{roll}** on {self.save_type} save{dc_text}!{source_text}{result_text}\n"
                f"({len(self.view.collected)}/{len(self.view.expected)} collected)"
            )

            # Check if all have rolled
            if self.view._check_complete():
                self.view.stop()
                if self.view._on_complete:
                    await self.view._on_complete(self.view.get_results())
        except Exception as e:
            # Ensure we always respond to the interaction to prevent "This interaction failed"
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )
            except Exception:
                pass  # Last resort - at least we tried


class SaveView(View):
    """
    View with button to open saving throw modal.

    Tracks which characters have rolled and displays progress.
    Used for AOE effects that require saves from multiple characters.
    """

    def __init__(
        self,
        expected_characters: List[str],
        prompt: str,
        save_type: str = "DEX",
        dc: Optional[int] = None,
        timeout: float = 60.0,
        get_character_for_user: Optional[Callable[[int], str]] = None,
        get_save_modifier: Optional[Callable[[str, str], int]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        """
        Initialize the save view.

        Args:
            expected_characters: List of character names who need to roll
            prompt: Prompt to display (e.g., "Roll DEX save DC 15")
            save_type: Type of save (DEX, CON, WIS, INT, STR, CHA)
            dc: Difficulty Class for the save
            timeout: Seconds before view times out (default 60)
            get_character_for_user: Callback to get character name from user ID
            get_save_modifier: Callback to get save modifier for a character
            on_complete: Callback when all rolls collected
        """
        super().__init__(timeout=timeout)
        self.expected: List[str] = expected_characters
        self.prompt = prompt
        self.save_type = save_type.upper()
        self.dc = dc
        self.collected: Dict[str, Dict[str, Any]] = {}  # character -> roll info
        self._get_character_for_user = get_character_for_user
        self._get_save_modifier = get_save_modifier
        self._on_complete = on_complete

    async def _get_character(self, user_id: int) -> Optional[str]:
        """Get character name for a Discord user."""
        if self._get_character_for_user:
            return self._get_character_for_user(user_id)
        return None

    def _get_save_mod(self, character_name: str) -> int:
        """Get save modifier for a character."""
        if self._get_save_modifier:
            return self._get_save_modifier(character_name, self.save_type)
        return 0  # Default to 0 if no callback provided

    def _check_complete(self) -> bool:
        """Check if all expected characters have rolled."""
        return len(self.collected) >= len(self.expected)

    def get_results(self) -> Dict[str, Any]:
        """Get the collected saving throw results."""
        successes = [c for c, info in self.collected.items() if info.get("success") is True]
        failures = [c for c, info in self.collected.items() if info.get("success") is False]

        return {
            "rolls": self.collected,
            "successes": successes,
            "failures": failures,
            "complete": self._check_complete(),
            "missing": [c for c in self.expected if c not in self.collected],
            "save_type": self.save_type,
            "dc": self.dc,
            "timed_out": False,
        }

    async def on_timeout(self):
        """Handle view timeout - auto-roll for non-responders."""
        # Disable the button
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

        # Auto-roll for anyone who hasn't rolled
        for character in self.expected:
            if character not in self.collected:
                modifier = self._get_save_mod(character)
                base_roll = random.randint(1, 20)
                roll = base_roll + modifier
                success = roll >= self.dc if self.dc else None

                self.collected[character] = {
                    "roll": roll,
                    "source": f"auto-timeout (d20={base_roll} + {self.save_type}={modifier})",
                    "modifier": modifier,
                    "save_type": self.save_type,
                    "success": success,
                }

        # Call completion callback
        if self._on_complete:
            results = self.get_results()
            results["timed_out"] = True
            await self._on_complete(results)

    @discord.ui.button(label="Roll Save", style=discord.ButtonStyle.danger, emoji="🎲")
    async def roll_button(self, interaction: discord.Interaction, button: Button):
        """Handle save roll button click."""
        try:
            character = await self._get_character(interaction.user.id)

            if character is None:
                await interaction.response.send_message(
                    "You're not registered in this session! Use `/register` first.",
                    ephemeral=True
                )
                return

            if character not in self.expected:
                await interaction.response.send_message(
                    "You're not affected by this effect!",
                    ephemeral=True
                )
                return

            if character in self.collected:
                roll_info = self.collected[character]
                result_text = ""
                if roll_info.get("success") is not None:
                    result_text = " (SUCCESS)" if roll_info["success"] else " (FAILURE)"
                await interaction.response.send_message(
                    f"You already rolled: **{roll_info['roll']}**{result_text}",
                    ephemeral=True
                )
                return

            # Get save modifier for this character
            modifier = self._get_save_mod(character)

            # Open the save modal
            await interaction.response.send_modal(
                SaveModal(self, character, self.save_type, modifier, self.dc)
            )
        except Exception as e:
            # Ensure we always respond to the interaction to prevent "This interaction failed"
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )
            except Exception:
                pass  # Last resort - at least we tried

#NOTE: may need a better implementation in the future
def parse_save_from_prompt(prompt: str) -> tuple[str, Optional[int]]:
    """
    Parse save type and DC from a prompt string.

    Examples:
        "Roll DEX save DC 15" -> ("DEX", 15)
        "Make a Constitution saving throw" -> ("CON", None)
        "Wisdom save DC 13" -> ("WIS", 13)

    Args:
        prompt: The DM's save prompt

    Returns:
        Tuple of (save_type, dc) where dc may be None if not specified
    """
    prompt_upper = prompt.upper()

    # Map full names to abbreviations
    save_map = {
        "STRENGTH": "STR",
        "DEXTERITY": "DEX",
        "CONSTITUTION": "CON",
        "INTELLIGENCE": "INT",
        "WISDOM": "WIS",
        "CHARISMA": "CHA",
        "STR": "STR",
        "DEX": "DEX",
        "CON": "CON",
        "INT": "INT",
        "WIS": "WIS",
        "CHA": "CHA",
    }

    # Find save type
    save_type = "DEX"  # Default
    for name, abbrev in save_map.items():
        if name in prompt_upper:
            save_type = abbrev
            break

    # Find DC
    dc = None
    import re
    dc_match = re.search(r"DC\s*(\d+)", prompt_upper)
    if dc_match:
        dc = int(dc_match.group(1))

    return save_type, dc

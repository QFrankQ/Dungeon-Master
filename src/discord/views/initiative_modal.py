"""
Initiative Roll Views for D&D combat.

Provides hybrid manual/auto-roll support for initiative:
- Players can manually enter their roll result
- Or leave blank for automatic d20 + DEX modifier roll
- Optional flavor text for roleplay

Features:
- Button to open initiative modal
- Progress tracking (X/Y collected)
- Auto-finalization when all rolls collected
"""

import discord
from discord.ui import View, Button, Modal, TextInput
from typing import List, Dict, Optional, Callable, Any
import random


class InitiativeModal(Modal, title="Initiative Roll"):
    """
    Modal for submitting initiative roll.

    Supports hybrid manual/auto-roll:
    - Enter a number for manual roll
    - Leave blank for auto-roll (d20 + DEX modifier)
    """

    manual_roll = TextInput(
        label="Your Roll (leave blank for auto-roll)",
        placeholder="e.g., 18",
        required=False,
        max_length=2
    )

    flavor = TextInput(
        label="What does your character do? (optional)",
        placeholder="I ready my sword and scan for threats...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300
    )

    def __init__(
        self,
        view: 'InitiativeView',
        character_name: str,
        dex_modifier: int = 0
    ):
        """
        Initialize the initiative modal.

        Args:
            view: Parent InitiativeView
            character_name: Name of the character rolling
            dex_modifier: DEX modifier to add for auto-rolls
        """
        super().__init__()
        self.view = view
        self.character_name = character_name
        self.dex_modifier = dex_modifier

    async def on_submit(self, interaction: discord.Interaction):
        """Handle initiative roll submission."""
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
                # Auto-roll: d20 + DEX modifier
                base_roll = random.randint(1, 20)
                roll = base_roll + self.dex_modifier
                source = f"auto (d20={base_roll} + DEX={self.dex_modifier})"

            # Store the roll in the parent view
            self.view.collected[self.character_name] = {
                "roll": roll,
                "source": source,
                "flavor": self.flavor.value,
                "dex_modifier": self.dex_modifier,
            }

            # Build response message
            flavor_text = f"\n*{self.flavor.value}*" if self.flavor.value else ""
            source_text = f" ({source})" if source != "manual" else ""

            await interaction.response.send_message(
                f"🎲 **{self.character_name}** rolled **{roll}** for initiative!{source_text}{flavor_text}\n"
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


class InitiativeView(View):
    """
    View with button to open initiative modal.

    Tracks which characters have rolled and displays progress.
    """

    def __init__(
        self,
        expected_characters: List[str],
        timeout: float = 120.0,
        get_character_for_user: Optional[Callable[[int], str]] = None,
        get_dex_modifier: Optional[Callable[[str], int]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        """
        Initialize the initiative view.

        Args:
            expected_characters: List of character names who need to roll
            timeout: Seconds before view times out (default 120)
            get_character_for_user: Callback to get character name from user ID
            get_dex_modifier: Callback to get DEX modifier for a character
            on_complete: Callback when all rolls collected
        """
        super().__init__(timeout=timeout)
        self.expected: List[str] = expected_characters
        self.collected: Dict[str, Dict[str, Any]] = {}  # character -> roll info
        self._get_character_for_user = get_character_for_user
        self._get_dex_modifier = get_dex_modifier
        self._on_complete = on_complete

    async def _get_character(self, user_id: int) -> Optional[str]:
        """Get character name for a Discord user."""
        if self._get_character_for_user:
            return self._get_character_for_user(user_id)
        return None

    def _get_dex_mod(self, character_name: str) -> int:
        """Get DEX modifier for a character."""
        if self._get_dex_modifier:
            return self._get_dex_modifier(character_name)
        return 0  # Default to 0 if no callback provided

    def _check_complete(self) -> bool:
        """Check if all expected characters have rolled."""
        return len(self.collected) >= len(self.expected)

    def get_results(self) -> Dict[str, Any]:
        """Get the collected initiative results."""
        # Sort by roll (descending)
        sorted_results = sorted(
            self.collected.items(),
            key=lambda x: (-x[1]["roll"], -x[1].get("dex_modifier", 0))
        )
        return {
            "rolls": self.collected,
            "order": [char for char, _ in sorted_results],
            "complete": self._check_complete(),
            "missing": [c for c in self.expected if c not in self.collected],
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
                dex_mod = self._get_dex_mod(character)
                base_roll = random.randint(1, 20)
                # Apply disadvantage for timeout (per 2024 PHB rules for surprise)
                roll = base_roll + dex_mod
                self.collected[character] = {
                    "roll": roll,
                    "source": f"auto-timeout (d20={base_roll} + DEX={dex_mod})",
                    "flavor": "",
                    "dex_modifier": dex_mod,
                }

        # Call completion callback
        if self._on_complete:
            results = self.get_results()
            results["timed_out"] = True
            await self._on_complete(results)

    @discord.ui.button(label="Roll Initiative", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll_button(self, interaction: discord.Interaction, button: Button):
        """Handle initiative roll button click."""
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
                    "You're not in this combat!",
                    ephemeral=True
                )
                return

            if character in self.collected:
                roll_info = self.collected[character]
                await interaction.response.send_message(
                    f"You already rolled: **{roll_info['roll']}**",
                    ephemeral=True
                )
                return

            # Get DEX modifier for this character
            dex_mod = self._get_dex_mod(character)

            # Open the initiative modal
            await interaction.response.send_modal(
                InitiativeModal(self, character, dex_mod)
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

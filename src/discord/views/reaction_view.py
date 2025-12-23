"""
Reaction Window View for D&D combat.

Provides buttons for players to declare or pass on reactions during
pre-resolution and post-resolution reaction windows.

Features:
- Pass button for declining reactions (ephemeral confirmation)
- Use Reaction button to declare intent (simple yes, sends to DM for queuing)
- Short-circuit: stops waiting when all players respond
- Timeout support (default 30 seconds)

Future Enhancement:
- ReactionModal could allow players to narrate their reaction directly
  and queue new turns directly in the turn stack.
"""

import discord
from discord.ui import View, Button, Modal, TextInput
from typing import List, Set, Dict, Optional, Callable, Any


# NOTE: ReactionModal is commented out to keep the initial implementation simple.
# For now, we just collect yes/no from users and send to DM.
# The DM will then queue up the reaction turns in the turn context.
# This can be enhanced later to let users narrate and submit reactions directly.
#
# class ReactionModal(Modal, title="Declare Reaction"):
#     """Modal for describing the reaction being used."""
#
#     reaction_type = TextInput(
#         label="What reaction are you using?",
#         placeholder="e.g., Shield, Opportunity Attack, Counterspell",
#         required=True,
#         max_length=100
#     )
#
#     description = TextInput(
#         label="Describe your reaction (optional)",
#         placeholder="e.g., I cast Shield as the arrow flies toward me...",
#         style=discord.TextStyle.paragraph,
#         required=False,
#         max_length=500
#     )
#
#     def __init__(self, view: 'ReactionView', character_name: str):
#         super().__init__()
#         self.view = view
#         self.character_name = character_name
#
#     async def on_submit(self, interaction: discord.Interaction):
#         """Handle reaction declaration submission."""
#         # Store the reaction in the parent view
#         self.view.reactions[self.character_name] = {
#             "type": self.reaction_type.value,
#             "description": self.description.value,
#         }
#
#         # Send public confirmation
#         description_text = f" - {self.description.value}" if self.description.value else ""
#         await interaction.response.send_message(
#             f"**{self.character_name}** uses **{self.reaction_type.value}**!{description_text}"
#         )
#
#         # Check if all have responded
#         if self.view._check_complete():
#             self.view.stop()


class ReactionView(View):
    """
    View for reaction windows with Pass button and short-circuit.

    Used during pre-resolution and post-resolution reaction windows in combat.
    Players can either pass (decline) or declare a reaction.
    """

    def __init__(
        self,
        expected_characters: List[str],
        prompt: Optional[str] = None,
        timeout: float = 30.0,
        get_character_for_user: Optional[Callable[[int], str]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        """
        Initialize the reaction view.

        Args:
            expected_characters: List of character names who can react
            prompt: Optional prompt to display (e.g., "Opportunity attack?")
            timeout: Seconds before view times out (default 30)
            get_character_for_user: Callback to get character name from user ID
            on_complete: Callback when all responses collected
        """
        super().__init__(timeout=timeout)
        self.expected: Set[str] = set(expected_characters)
        self.prompt = prompt or "Does anyone want to use a reaction?"
        self.passed: Set[str] = set()
        self.reactions: Dict[str, Dict[str, str]] = {}  # character -> reaction info
        self._get_character_for_user = get_character_for_user
        self._on_complete = on_complete

    async def _get_character(self, user_id: int) -> Optional[str]:
        """Get character name for a Discord user."""
        if self._get_character_for_user:
            return self._get_character_for_user(user_id)
        # Fallback: return None and let caller handle
        return None

    def _check_complete(self) -> bool:
        """Check if all expected characters have responded."""
        responded = self.passed | set(self.reactions.keys())
        return responded >= self.expected

    def get_results(self) -> Dict[str, Any]:
        """Get the results of the reaction window."""
        return {
            "passed": list(self.passed),
            "reactions": self.reactions,
            "complete": self._check_complete(),
            "timed_out": False,
        }

    async def on_timeout(self):
        """Handle view timeout - treat non-responders as passing."""
        # Disable buttons
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

        # Call completion callback if set
        if self._on_complete:
            results = self.get_results()
            results["timed_out"] = True
            await self._on_complete(results)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        """Handle player passing on their reaction."""
        character = await self._get_character(interaction.user.id)

        if character is None:
            await interaction.response.send_message(
                "You're not registered in this session! Use `/register` first.",
                ephemeral=True
            )
            return

        if character not in self.expected:
            await interaction.response.send_message(
                "You're not eligible for a reaction in this situation.",
                ephemeral=True
            )
            return

        if character in self.passed or character in self.reactions:
            await interaction.response.send_message(
                "You've already responded to this reaction window.",
                ephemeral=True
            )
            return

        # Record the pass
        self.passed.add(character)

        # Send ephemeral confirmation (only sender sees)
        await interaction.response.send_message(
            f"{character} passes on the reaction.",
            ephemeral=True
        )

        # Check if all have responded - short-circuit
        if self._check_complete():
            self.stop()
            if self._on_complete:
                await self._on_complete(self.get_results())

    @discord.ui.button(label="Use Reaction", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def use_reaction_button(self, interaction: discord.Interaction, button: Button):
        """Handle player wanting to use their reaction."""
        character = await self._get_character(interaction.user.id)

        if character is None:
            await interaction.response.send_message(
                "You're not registered in this session! Use `/register` first.",
                ephemeral=True
            )
            return

        if character not in self.expected:
            await interaction.response.send_message(
                "You're not eligible for a reaction in this situation.",
                ephemeral=True
            )
            return

        if character in self.passed or character in self.reactions:
            await interaction.response.send_message(
                "You've already responded to this reaction window.",
                ephemeral=True
            )
            return

        # Simple yes - record intent to use reaction (DM will queue the turn)
        # NOTE: In the future, ReactionModal could be enabled to let players
        # narrate their reaction and queue turns directly.
        self.reactions[character] = {
            "type": "declared",  # Simple declaration, DM will determine specifics
            "description": "",
        }

        # Send ephemeral confirmation (only sender sees)
        # Public announcement happens via on_complete callback after ALL responses collected
        await interaction.response.send_message(
            f"You want to use a reaction. Waiting for others to respond...",
            ephemeral=True
        )

        # Check if all have responded - short-circuit
        if self._check_complete():
            self.stop()
            if self._on_complete:
                await self._on_complete(self.get_results())

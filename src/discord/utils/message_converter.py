"""
Message converter for Discord to ChatMessage format.

Converts Discord message objects to the internal ChatMessage format
used by the SessionManager.
"""

import discord
from src.models.chat_message import ChatMessage


def discord_to_chat_message(
    discord_message: discord.Message,
    character_name: str
) -> ChatMessage:
    """
    Convert Discord message to ChatMessage format.

    Args:
        discord_message: Discord message object
        character_name: Name of the character speaking

    Returns:
        ChatMessage object formatted for SessionManager
    """
    return ChatMessage.create_player_message(
        player_id=str(discord_message.author.id),
        character_id=character_name,
        text=discord_message.content
    )


def format_dm_response(response: str) -> str:
    """
    Format DM response for Discord.

    Args:
        response: Raw response text from DM

    Returns:
        Formatted response for Discord (with bold **DM:** prefix)
    """
    # Split into chunks if too long (Discord has 2000 char limit)
    max_length = 1900  # Leave room for prefix

    if len(response) <= max_length:
        return f"**DM:** {response}"

    # Split into multiple messages
    chunks = []
    current_chunk = ""

    for line in response.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += ('\n' if current_chunk else '') + line

    if current_chunk:
        chunks.append(current_chunk)

    # Return first chunk formatted (caller will handle multiple chunks)
    return chunks[0] if chunks else ""

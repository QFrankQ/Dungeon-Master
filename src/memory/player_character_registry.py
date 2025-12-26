"""
Player-Character Registry for managing player ID to character ID mappings.
Provides lookup methods to retrieve character information by either player ID or character ID.
"""

from typing import Dict, List, Optional
import json
import os
from datetime import datetime

from ..characters.charactersheet import Character


class PlayerCharacterRegistryError(Exception):
    """Exception raised when registry operations fail."""
    pass


class PlayerCharacterRegistry:
    """
    Manages player-character ID mappings and provides character data retrieval.
    
    This class maintains the relationship between player IDs and character IDs,
    and provides methods to retrieve character information using either identifier.
    """
    
    def __init__(self, registry_file_path: str = "src/characters/player_character_registry.json"):
        """
        Initialize the player-character registry.
        
        Args:
            registry_file_path: Path to the registry file for persistence
        """
        self.registry_file_path = registry_file_path
        self.player_to_character: Dict[str, str] = {}
        self.character_to_player: Dict[str, str] = {}
        self.character_cache: Dict[str, Character] = {}
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(registry_file_path), exist_ok=True)
        
        # Load existing mappings
        self._load_registry()
    
    def register_player_character(self, player_id: str, character_id: str) -> bool:
        """
        Register a player-character mapping.
        
        Args:
            player_id: ID of the player
            character_id: ID of the character
        
        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Update mappings
            self.player_to_character[player_id] = character_id
            self.character_to_player[character_id] = player_id
            
            # Save to file
            self._save_registry()
            return True
            
        except Exception as e:
            raise PlayerCharacterRegistryError(f"Failed to register player-character mapping: {e}")
    
    def get_character_id_by_player_id(self, player_id: str) -> Optional[str]:
        """
        Get character ID for a given player ID.
        
        Args:
            player_id: ID of the player
        
        Returns:
            Character ID or None if not found
        """
        return self.player_to_character.get(player_id)
    
    def get_player_id_by_character_id(self, character_id: str) -> Optional[str]:
        """
        Get player ID for a given character ID.
        
        Args:
            character_id: ID of the character
        
        Returns:
            Player ID or None if not found
        """
        return self.character_to_player.get(character_id)
    
    def get_character_by_player_id(self, player_id: str) -> Optional[Character]:
        """
        Get character data for a given player ID.
        
        Args:
            player_id: ID of the player
        
        Returns:
            Character instance or None if not found
        """
        character_id = self.get_character_id_by_player_id(player_id)
        if character_id:
            return self._load_character(character_id)
        return None
    
    def get_character_by_character_id(self, character_id: str) -> Optional[Character]:
        """
        Get character data for a given character ID.
        
        Args:
            character_id: ID of the character
        
        Returns:
            Character instance or None if not found
        """
        return self._load_character(character_id)
    
    def get_all_player_character_mappings(self) -> Dict[str, str]:
        """
        Get all player-character mappings.

        Returns:
            Dictionary of player_id -> character_id mappings
        """
        return self.player_to_character.copy()

    def get_all_character_ids(self) -> List[str]:
        """
        Get all registered character IDs.

        Returns:
            List of character IDs currently registered (e.g., ["fighter", "wizard"])
        """
        return list(self.character_to_player.keys())

    def get_all_character_names(self) -> List[str]:
        """
        Get names for all registered characters.

        Loads each character to get their info.name for narrative use.
        Falls back to character_id if character can't be loaded.

        Returns:
            List of character names (e.g., ["Tharion Stormwind", "Elara"])
        """
        names = []
        for character_id in self.character_to_player.keys():
            character = self._load_character(character_id)
            if character and character.info and character.info.name:
                names.append(character.info.name)
            else:
                names.append(character_id)
        return names

    def get_character_id_to_name_map(self) -> Dict[str, str]:
        """
        Get a mapping from character_id to character name.

        Useful for converting between system IDs and narrative names.

        Returns:
            Dict mapping character_id -> name
        """
        mapping = {}
        for character_id in self.character_to_player.keys():
            character = self._load_character(character_id)
            if character and character.info and character.info.name:
                mapping[character_id] = character.info.name
            else:
                mapping[character_id] = character_id
        return mapping

    def remove_player_character_mapping(self, player_id: str) -> bool:
        """
        Remove a player-character mapping.
        
        Args:
            player_id: ID of the player to remove
        
        Returns:
            True if removal successful, False if player not found
        """
        character_id = self.player_to_character.get(player_id)
        if character_id:
            # Remove from both mappings
            del self.player_to_character[player_id]
            del self.character_to_player[character_id]
            
            # Remove from cache
            if character_id in self.character_cache:
                del self.character_cache[character_id]
            
            # Save changes
            self._save_registry()
            return True
        return False
    
    def _load_character(self, character_id: str) -> Optional[Character]:
        """
        Load character data from file with caching.
        
        Args:
            character_id: ID of the character to load
        
        Returns:
            Character instance or None if not found
        """
        # Check cache first
        if character_id in self.character_cache:
            return self.character_cache[character_id]
        
        # Load from file
        try:
            character_file = f"src/characters/{character_id}.json"
            if os.path.exists(character_file):
                with open(character_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    character = Character.model_validate(data)
                    
                    # Cache the character
                    self.character_cache[character_id] = character
                    return character
        except Exception as e:
            print(f"Failed to load character {character_id}: {e}")
        
        return None
    
    def _load_registry(self) -> None:
        """Load player-character mappings from file."""
        try:
            if os.path.exists(self.registry_file_path):
                with open(self.registry_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    self.player_to_character = data.get("player_to_character", {})
                    self.character_to_player = data.get("character_to_player", {})
        except Exception as e:
            print(f"Failed to load registry: {e}")
            # Initialize empty mappings on failure
            self.player_to_character = {}
            self.character_to_player = {}
    
    def _save_registry(self) -> None:
        """Save player-character mappings to file."""
        try:
            registry_data = {
                "player_to_character": self.player_to_character,
                "character_to_player": self.character_to_player,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.registry_file_path, 'w', encoding='utf-8') as f:
                json.dump(registry_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise PlayerCharacterRegistryError(f"Failed to save registry: {e}")
    
    def clear_cache(self) -> None:
        """Clear the character cache to force reloading from files."""
        self.character_cache.clear()
    
    def get_registry_stats(self) -> Dict[str, int]:
        """
        Get statistics about the registry.
        
        Returns:
            Dictionary with registry statistics
        """
        return {
            "total_mappings": len(self.player_to_character),
            "cached_characters": len(self.character_cache)
        }


def create_player_character_registry(registry_file_path: str = "src/characters/player_character_registry.json") -> PlayerCharacterRegistry:
    """
    Factory function to create a configured player-character registry.
    
    Args:
        registry_file_path: Path to the registry file for persistence
    
    Returns:
        Configured PlayerCharacterRegistry instance
    """
    return PlayerCharacterRegistry(registry_file_path=registry_file_path)
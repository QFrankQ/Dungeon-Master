"""Validate all character JSON files against Character model."""

from pathlib import Path
import json
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.characters.charactersheet import Character

def validate_character_file(file_path: Path):
    """Load and validate a character JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Validate through Pydantic model
        character = Character(**data)

        classes_str = "/".join([c.value for c in character.info.classes])
        print(f"✓ {file_path.name}: Valid - {character.info.name} ({classes_str} {character.info.level})")
        return True
    except Exception as e:
        print(f"✗ {file_path.name}: INVALID - {e}")
        return False

def main():
    characters_dir = Path(__file__).parent.parent / "src" / "characters"

    # Skip non-character files
    excluded_files = {'enemies.json', 'player_character_registry.json'}
    character_files = [f for f in characters_dir.glob("*.json") if f.name not in excluded_files]

    if not character_files:
        print("No character JSON files found")
        return

    print(f"Validating {len(character_files)} character files...")
    print("="*70)

    results = [validate_character_file(f) for f in character_files]

    print("="*70)
    print(f"Results: {sum(results)}/{len(results)} valid")

if __name__ == "__main__":
    main()

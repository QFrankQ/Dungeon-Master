# D&D Rules Rendering Summary

**Generated**: December 1, 2024
**Status**: ✅ Successfully Completed

## Overview

Successfully rendered **2,804 D&D rule entries** from 9 filtered JSON files into clean markdown and structured metadata files for RAG integration and knowledge graph construction.

## Processing Statistics

| File | Type | Entries | Status |
|------|------|---------|--------|
| filtered_actions.json | action | 20 | ✅ |
| filtered_conditions.json | condition | 15 | ✅ |
| filtered_feats.json | feat | 150 | ✅ |
| filtered_items.json | item | 1,789 | ✅ |
| filtered_objects.json | object | 27 | ✅ |
| filtered_optionalfeatures.json | optionalfeature | 127 | ✅ |
| filtered_senses.json | sense | 5 | ✅ |
| filtered_variant_rules.json | variantrule | 114 | ✅ |
| spells_ALL_COMBINED.json | spell | 557 | ✅ |
| **TOTAL** | | **2,804** | **0 errors** |

## Output Structure

**Locations**:
- Content: `src/db/rendered_rules/` (gitignored)
- Graph: `src/db/metadata/` (gitignored)

### Directory Organization
```
src/db/
├── rendered_rules/      # Rule content for embeddings
│   ├── action/          # 20 markdown files
│   ├── condition/       # 15 markdown files
│   ├── feat/            # 150 markdown files
│   ├── item/            # 1,789 markdown files
│   ├── object/          # 27 markdown files
│   ├── optionalfeature/ # 127 markdown files
│   ├── sense/           # 5 markdown files
│   ├── spell/           # 557 markdown files
│   └── variantrule/     # 114 markdown files
└── metadata/            # Graph relationships & edges
    ├── action/          # 20 metadata JSON files
    ├── condition/       # 15 metadata JSON files
    ├── feat/            # 150 metadata JSON files
    ├── item/            # 1,789 metadata JSON files
    ├── object/          # 27 metadata JSON files
    ├── optionalfeature/ # 127 metadata JSON files
    ├── sense/           # 5 metadata JSON files
    ├── spell/           # 557 metadata JSON files
    └── variantrule/     # 114 metadata JSON files
```

**Total Files**:
- 2,804 Markdown files (`.md`)
- 2,804 Metadata files (`.json`)
- 5,608 files total

## Output Format

### Markdown Files
**Purpose**: Clean, readable text ideal for vector embeddings and semantic search

**Naming**: `{entry_name}_{source}.md`

**Example**: [src/db/rendered_rules/spell/fireball_XPHB.md](src/db/rendered_rules/spell/fireball_XPHB.md)
```markdown
### Fireball

A bright streak flashes from you to a point you choose within range and then
blossoms with a low roar into a fiery explosion. Each creature in a 20-foot-radius
Sphere centered on that point makes a Dexterity saving throw, taking 8d6 Fire
damage on a failed save or half as much damage on a successful one.

Flammable objects in the area that aren't being worn or carried start burning.
```

### Metadata Files
**Purpose**: Structured data for knowledge graph construction and filtering

**Naming**: `{entry_name}_{source}.json`

**Example**: [src/db/metadata/spell/fireball_XPHB.json](src/db/metadata/spell/fireball_XPHB.json)
```json
{
  "type": "spell",
  "name": "Fireball",
  "source": "XPHB",
  "tags": [],
  "references": [
    {
      "tagType": "variantrule",
      "content": "Sphere [Area of Effect]|XPHB|Sphere",
      "referenceType": "inline_tag"
    },
    {
      "tagType": "damage",
      "content": "8d6",
      "referenceType": "inline_tag"
    },
    {
      "tagType": "hazard",
      "content": "burning|XPHB",
      "referenceType": "inline_tag"
    }
  ],
  "level": 3,
  "school": "V",
  "time": [
    {
      "number": 1,
      "unit": "action"
    }
  ]
}
```

## Metadata Reference Types

The metadata extraction captured various reference types for graph construction:

### Inline Tags
Automatically extracted from text content:
- `spell` - Spell references
- `damage` - Damage rolls (e.g., "8d6")
- `condition` - Status conditions
- `variantrule` - Rule references
- `hazard` - Environmental hazards
- `item` - Item references
- `creature` - Creature references

### Cross-References
Explicit relationships between entries:
- `seeAlsoAction` - Related actions
- `seeAlsoFeature` - Related features
- `seeAlsoSpell` - Related spells
- `seeAlsoItem` - Related items

### Type-Specific Fields
Additional metadata for specific entry types:
- **Spells**: `level`, `school`, `time`
- **Actions**: `time` (action, bonus, reaction, free)
- **Items**: `rarity`, `tier`, `itemType`

## Source Books

All entries are tagged with their source book:
- **XPHB**: 2024 Player's Handbook (majority of entries)
- **XGE**: Xanathar's Guide to Everything
- **AAG**: Astral Adventurer's Guide
- **DMG**: Dungeon Master's Guide

## Use Cases

### 1. Vector Database Integration
Replace or augment current [src/db/combat_rules.json](src/db/combat_rules.json) with rendered markdown:

```python
from pathlib import Path
import json

# Embed spell entries
for md_file in Path("src/db/rendered_rules/spell").glob("*.md"):
    markdown_content = md_file.read_text()

    # Load metadata
    meta_file = Path("src/db/metadata/spell") / md_file.name.replace(".md", ".json")
    metadata = json.loads(meta_file.read_text())

    # Create embedding
    embedding = embed_model.encode(markdown_content)
    vector_db.insert(
        embedding=embedding,
        document=markdown_content,
        metadata={
            "name": metadata["name"],
            "type": metadata["type"],
            "source": metadata["source"],
            "level": metadata.get("level"),
            "school": metadata.get("school")
        }
    )
```

### 2. Knowledge Graph Construction
Build relationships between rules:

```python
import networkx as nx
from pathlib import Path
import json

graph = nx.DiGraph()

# Build graph from all metadata
for meta_file in Path("src/db/metadata").rglob("*.json"):
    metadata = json.loads(meta_file.read_text())

    # Add node
    node_id = f"{metadata['name']}|{metadata['source']}"
    graph.add_node(node_id, **metadata)

    # Add edges for references
    for ref in metadata.get("references", []):
        target_id = ref["content"]
        edge_type = f"{ref['referenceType']}_{ref['tagType']}"
        graph.add_edge(node_id, target_id, type=edge_type)
```

### 3. Filtered Retrieval
Use metadata for precise queries:

```python
def find_spells_by_level(level: int):
    """Find all spells of a specific level."""
    results = []
    for meta_file in Path("src/db/metadata/spell").glob("*.json"):
        metadata = json.loads(meta_file.read_text())
        if metadata.get("level") == level:
            results.append(metadata["name"])
    return results

# Usage
level_3_spells = find_spells_by_level(3)  # Returns: Fireball, Counterspell, etc.
```

## Tools & Scripts

### Rendering Script
**Location**: [render_rules.py](render_rules.py)

**Usage**:
```bash
uv run python render_rules.py
```

**Features**:
- Processes all rule files from `src/db/rules/`
- Provides progress tracking
- Generates detailed statistics
- Handles errors gracefully

### Submodule Integration
**Location**: [external/5etools-renderer/](external/5etools-renderer/)

**Direct Usage**:
```bash
# Render single file
node external/5etools-renderer/render-to-markdown.js \
  --input src/db/rules/filtered_actions.json \
  --output-dir output/my_rules

# List available data files
node external/5etools-renderer/render-to-markdown.js --list
```

## Next Steps

1. **Update Vector Database**: Replace [src/db/combat_rules.json](src/db/combat_rules.json) with new markdown files
2. **Build Knowledge Graph**: Implement graph-based rule navigation using metadata
3. **Enhance State Extraction**: Use structured metadata for better state updates
4. **Implement Hybrid RAG**: Combine vector search + graph traversal for rule lookup
5. **Add Citation System**: Track rule sources using metadata

## Related Documentation

- [5etools Renderer README](external/5etools-renderer/README.md)
- [Integration Guide](external/5etools-renderer/INTEGRATION.md)
- [Example Usage](external/5etools-renderer/example_usage.py)
- [Project README](README.md)

## Verification

✅ All 2,804 entries rendered successfully
✅ 0 errors during processing
✅ All markdown files generated
✅ All metadata files generated
✅ Output directory: 22 MB total
✅ Clean, readable markdown format
✅ Structured metadata for graphs
✅ Source tracking included
✅ Reference extraction working

---

**Git Submodule**: [external/5etools-renderer](external/5etools-renderer/)
**Content Directory**: [src/db/rendered_rules/](src/db/rendered_rules/)
**Graph Directory**: [src/db/metadata/](src/db/metadata/)
**Rendering Script**: [render_rules.py](render_rules.py)

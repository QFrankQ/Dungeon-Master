#!/usr/bin/env python3
"""
Step 1: Render curated rules to markdown and metadata.

This script:
- Renders all curated rules from external/5etools-renderer/curated_rules/
- Outputs directly to src/db/rendered_rules/ and src/db/metadata/
- Does NOT use the Gemini API (no rate limiting concerns)

Usage:
    uv run python scripts/db/step1_render_rules.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 70)
    print("STEP 1: RENDER CURATED RULES")
    print("=" * 70)
    print()

    renderer_dir = project_root / "external" / "5etools-renderer"
    output_dir = project_root / "src" / "db" / "rendered_rules"
    metadata_dir = project_root / "src" / "db" / "metadata"

    print(f"📂 Renderer directory: {renderer_dir}")
    print(f"📂 Output directory: {output_dir}")
    print(f"📂 Metadata directory: {metadata_dir}")
    print()

    # Import and call the renderer with custom output paths
    original_dir = Path.cwd()
    try:
        # Change to renderer directory (it expects to be run from there)
        os.chdir(renderer_dir)

        # Import the renderer function
        sys.path.insert(0, str(renderer_dir))
        from render_curated import render_curated_rules

        # Render with absolute paths
        render_curated_rules(
            output_dir=str(output_dir.absolute()),
            metadata_dir=str(metadata_dir.absolute())
        )

    finally:
        # Change back to original directory
        os.chdir(original_dir)

    print()
    print("=" * 70)
    print("✅ STEP 1 COMPLETE!")
    print("=" * 70)
    print()
    print("Next step:")
    print("  uv run python scripts/db/step2_build_database.py")
    print()

if __name__ == "__main__":
    main()

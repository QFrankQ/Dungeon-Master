#!/usr/bin/env python3
"""
Step 2: Build LanceDB database with embeddings.

This script:
- Reads rendered rules from src/db/rendered_rules/
- Reads metadata from src/db/metadata/
- Generates embeddings using Gemini API (RATE LIMITED - uses paid tier if available)
- Creates LanceDB table with vector embeddings
- Creates FTS index for hybrid search

⚠️  API USAGE WARNING:
- This script calls the Gemini API ~2,696 times (once per rule)
- Uses GEMINI_API_KEY_PAID_TIER or GOOGLE_API_KEY_PAID_TIER if available (1500 req/min)
- Falls back to free tier: GEMINI_API_KEY or GOOGLE_API_KEY (15 req/min)
- With free tier, this will take ~3 hours due to rate limiting
- With paid tier, this takes ~2-3 minutes

Usage:
    uv run python scripts/db/step2_build_database.py

    # Test mode - only process first 50 entries
    uv run python scripts/db/step2_build_database.py --limit 50
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 70)
    print("STEP 2: BUILD LANCEDB DATABASE")
    print("=" * 70)
    print()

    # Check if rendered rules exist
    rendered_dir = project_root / "src" / "db" / "rendered_rules"
    metadata_dir = project_root / "src" / "db" / "metadata"

    if not rendered_dir.exists() or not metadata_dir.exists():
        print("❌ ERROR: Rendered rules or metadata not found!")
        print(f"   Rendered rules: {rendered_dir}")
        print(f"   Metadata: {metadata_dir}")
        print()
        print("Please run step1_render_rules.py first:")
        print("  uv run python scripts/db/step1_render_rules.py")
        sys.exit(1)

    # Count files
    import os
    rendered_count = sum(1 for _ in rendered_dir.rglob("*.md"))
    metadata_count = sum(1 for _ in metadata_dir.rglob("*.json"))

    print(f"📊 Found {rendered_count} rendered rules")
    print(f"📊 Found {metadata_count} metadata files")
    print()

    if rendered_count == 0 or metadata_count == 0:
        print("❌ ERROR: No files found! Please run step1_render_rules.py first.")
        sys.exit(1)

    # Run the build script
    build_script = project_root / "scripts" / "db" / "build_lance_rules_db.py"

    # Pass through any command line arguments (like --limit)
    result = subprocess.run(
        [sys.executable, str(build_script)] + sys.argv[1:],
        cwd=str(project_root)
    )

    if result.returncode != 0:
        print("\n❌ Database build failed!")
        sys.exit(1)

    print()
    print("=" * 70)
    print("✅ STEP 2 COMPLETE!")
    print("=" * 70)
    print()
    print("Next step:")
    print("  uv run python scripts/db/step3_test_database.py")
    print()

if __name__ == "__main__":
    main()

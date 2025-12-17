#!/usr/bin/env python3
"""
Render curated rules and build LanceDB - ALL STEPS IN ONE COMMAND.

This script runs all three steps:
1. Renders all curated rules from external/5etools-renderer/curated_rules/
2. Builds LanceDB database with embeddings (USES GEMINI API - RATE LIMITED)
3. Tests the database

⚠️  For better rate limit control, run steps individually:
   uv run python scripts/db/step1_render_rules.py
   uv run python scripts/db/step2_build_database.py  # Wait after this if needed
   uv run python scripts/db/step3_test_database.py

Usage:
    uv run python scripts/db/render_and_build.py
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 70)
    print("D&D RULES: COMPLETE RENDER AND BUILD PIPELINE")
    print("=" * 70)
    print()

    scripts_dir = project_root / "scripts" / "db"

    # Step 1: Render rules
    step1 = scripts_dir / "step1_render_rules.py"
    result = subprocess.run([sys.executable, str(step1)], cwd=str(project_root))
    if result.returncode != 0:
        print("\n❌ Step 1 failed!")
        sys.exit(1)

    print()

    # Step 2: Build database
    step2 = scripts_dir / "step2_build_database.py"
    result = subprocess.run([sys.executable, str(step2)] + sys.argv[1:], cwd=str(project_root))
    if result.returncode != 0:
        print("\n❌ Step 2 failed!")
        sys.exit(1)

    print()

    # Step 3: Test database
    step3 = scripts_dir / "step3_test_database.py"
    result = subprocess.run([sys.executable, str(step3)], cwd=str(project_root))
    if result.returncode != 0:
        print("\n❌ Step 3 failed!")
        sys.exit(1)

    print()
    print("=" * 70)
    print("🎉 ALL STEPS COMPLETE!")
    print("=" * 70)
    print()

if __name__ == "__main__":
    main()

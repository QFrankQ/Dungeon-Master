#!/usr/bin/env python3
"""
Step 3: Test LanceDB database.

This script:
- Verifies the database was built correctly
- Runs integration tests
- Shows example queries

⚠️  API USAGE WARNING:
- Test queries use the Gemini API for embeddings
- Uses free tier: GEMINI_API_KEY or GOOGLE_API_KEY (15 req/min)
- ~20-30 API calls total for all tests

Usage:
    uv run python scripts/db/step3_test_database.py
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 70)
    print("STEP 3: TEST LANCEDB DATABASE")
    print("=" * 70)
    print()

    # Check if database exists
    db_path = project_root / "src" / "db" / "lancedb"

    if not db_path.exists():
        print("❌ ERROR: Database not found!")
        print(f"   Expected location: {db_path}")
        print()
        print("Please run step2_build_database.py first:")
        print("  uv run python scripts/db/step2_build_database.py")
        sys.exit(1)

    # Check if database has content
    rules_table = db_path / "rules.lance"
    if not rules_table.exists():
        print("❌ ERROR: Database table not found!")
        print(f"   Expected location: {rules_table}")
        print()
        print("Please run step2_build_database.py first:")
        print("  uv run python scripts/db/step2_build_database.py")
        sys.exit(1)

    print(f"✅ Database found at: {db_path}")
    print()

    # Run pytest integration tests
    print("Running integration tests...")
    print("-" * 70)

    test_file = project_root / "tests" / "test_lance_rules_service.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-v"],
        cwd=str(project_root)
    )

    print()

    if result.returncode != 0:
        print("❌ Some tests failed!")
        sys.exit(1)

    print("=" * 70)
    print("✅ STEP 3 COMPLETE - ALL TESTS PASSED!")
    print("=" * 70)
    print()
    print("🎉 Database is ready to use!")
    print()
    print("Example usage:")
    print("  from src.db.lance_rules_service import create_lance_rules_service")
    print("  service = create_lance_rules_service()")
    print("  results = service.search('fireball', limit=3)")
    print()

if __name__ == "__main__":
    main()

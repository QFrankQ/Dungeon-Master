"""
Build LanceDB rules database from rendered files.

This is a one-time setup script that:
1. Loads all rules from src/db/rendered_rules/ and src/db/metadata/
2. Creates embeddings using gemini-embedding-001
3. Deduplicates and validates references
4. Builds LanceDB table

Usage:
    # Process all entries
    uv run python scripts/db/build_lance_rules_db.py

    # Test mode - process only first 10 entries
    uv run python scripts/db/build_lance_rules_db.py --limit 10
"""

import argparse
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.lance_rules_service import LanceRulesService


def print_stats(stats: dict):
    """Print loading statistics in a readable format."""
    print("\n" + "=" * 70)
    print("LOADING STATISTICS")
    print("=" * 70)

    print(f"\n📊 Entry Statistics:")
    print(f"  Total entries loaded: {stats['total_entries']}")

    print(f"\n🔗 Reference Statistics:")
    print(f"  Total references found: {stats['total_references_found']}")
    print(f"  Valid references retained: {stats['final_valid_references']}")
    print(f"  Duplicate references removed: {stats['duplicate_references_removed']}")
    print(f"  Invalid references filtered: {stats['invalid_references_filtered']}")

    if stats['reference_types']:
        print(f"\n📑 References by Type:")
        for ref_type, count in sorted(stats['reference_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {ref_type}: {count}")

    if stats['errors']:
        print(f"\n⚠️  Errors ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")

    print("\n" + "=" * 70)


def main():
    """Build LanceDB from rendered rule files."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Build LanceDB rules database")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of entries to process (for testing). Default: process all"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("D&D RULES LANCEDB BUILD")
    if args.limit:
        print(f"⚠️  TEST MODE: Processing only {args.limit} entries")
    print("=" * 70)
    print()

    # Setup paths
    rendered_rules_dir = Path("src/db/rendered_rules")
    metadata_dir = Path("src/db/metadata")

    # Check paths exist
    if not rendered_rules_dir.exists():
        print(f"❌ Error: {rendered_rules_dir} does not exist")
        print("   Please run render_rules.py first to generate rule files")
        return

    if not metadata_dir.exists():
        print(f"❌ Error: {metadata_dir} does not exist")
        print("   Please run render_rules.py first to generate metadata files")
        return

    print(f"📂 Input directories:")
    print(f"  Markdown: {rendered_rules_dir}")
    print(f"  Metadata: {metadata_dir}")
    print(f"\n📂 Output database:")
    print(f"  LanceDB: src/db/lancedb/")
    print()

    # Create service with paid tier API key for higher rate limits during build
    print("💡 Using paid tier API key for building database (higher rate limits)")
    service = LanceRulesService(use_paid_tier=True)

    # Load all rules
    try:
        print("🚀 Starting load process...\n")

        stats = service.load_from_files(
            rendered_rules_dir=rendered_rules_dir,
            metadata_dir=metadata_dir,
            show_progress=True,
            max_entries=args.limit
        )

        # Calculate invalid references
        stats['invalid_references_filtered'] = (
            stats['total_references_found'] -
            stats['final_valid_references'] -
            stats.get('duplicate_references_removed', 0)
        )

        # Print statistics
        print_stats(stats)

        print("\n✅ SUCCESS!")
        print(f"   LanceDB database created at: src/db/lancedb/")
        print(f"   Total entries: {stats['total_entries']}")
        print(f"   Valid references: {stats['final_valid_references']}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Test the database:")
    print("   uv run python scripts/db/example_lance_usage.py")
    print()
    print("2. Run integration tests:")
    print("   uv run pytest tests/test_lance_rules_service.py")
    print()
    print("3. Update code to use LanceRulesService instead of VectorService")
    print()
    print("💡 Note: Queries will use free tier API key by default.")
    print("   Build used paid tier for higher rate limits.")
    print("=" * 70)


if __name__ == "__main__":
    main()

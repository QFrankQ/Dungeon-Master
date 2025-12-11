"""
Example: Using LanceDB for rule lookup with hybrid search and reference expansion.

Demonstrates:
1. Connecting to the database
2. Hybrid search (combining semantic vector search + full-text keyword search)
3. Automatic reference expansion
4. Formatting for LLM context
5. Direct ID lookup

Usage:
    uv run python scripts/db/example_lance_usage.py

Note: You must run build_lance_rules_db.py first to create the database.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.lance_rules_service import create_lance_rules_service


def example_1_basic_search():
    """Example 1: Hybrid search (semantic + keyword)."""
    print("=" * 70)
    print("EXAMPLE 1: Hybrid Search")
    print("=" * 70)
    print()

    # Create service and connect to database
    service = create_lance_rules_service()

    # Hybrid search works for both conceptual and keyword queries
    print("Semantic query: 'How does fireball work?'")
    results = service.search(
        query="How does fireball work?",
        limit=1,
        expand_references=False  # Don't expand yet
    )

    if results:
        result = results[0]
        print(f"Found: {result['name']} ({result['type']})")
        print(f"Source: {result['source']}")
        print(f"\nContent:\n{result['content'][:200]}...")

        if result.get('references'):
            print(f"\nReferences ({len(result['references'])}):")
            for ref in result['references'][:5]:
                print(f"  - {ref}")
    else:
        print("No results found")

    # Now try a keyword query
    print("\n" + "-" * 70)
    print("\nKeyword query: 'Fireball'")
    results = service.search(
        query="Fireball",
        limit=1,
        expand_references=False
    )

    if results:
        result = results[0]
        print(f"Found: {result['name']} ({result['type']})")
        print(f"Type: {result['type']}")
        print(f"Note: Hybrid search combines semantic understanding + exact keyword matching!")

    print()


def example_2_with_references():
    """Example 2: Search with reference expansion."""
    print("=" * 70)
    print("EXAMPLE 2: Search with Reference Expansion")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    # Search with reference expansion
    results = service.search(
        query="How does fireball work?",
        limit=1,
        expand_references=True,  # Expand references!
        max_depth=1
    )

    if results:
        result = results[0]
        print(f"Primary Result: {result['name']}")

        # Show expanded references
        expanded = result.get('expanded_references', [])
        if expanded:
            print(f"\nExpanded References ({len(expanded)}):")
            for ref in expanded:
                print(f"  • {ref['name']} ({ref['type']})")
                # Show first 100 chars of content
                preview = ref['content'].replace('\n', ' ')[:100]
                print(f"    {preview}...")
        else:
            print("\nNo references to expand")
    else:
        print("No results found")

    print()


def example_3_formatted_context():
    """Example 3: Format results for LLM context."""
    print("=" * 70)
    print("EXAMPLE 3: Formatted Context for LLM")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    # Search with expansion
    results = service.search(
        query="fireball spell",
        limit=1,
        expand_references=True
    )

    # Format for LLM
    context = service.format_for_context(results, include_references=True)

    print("Formatted context (ready to pass to LLM):")
    print(context)

    print()


def example_4_direct_lookup():
    """Example 4: Direct ID lookup."""
    print("=" * 70)
    print("EXAMPLE 4: Direct ID Lookup")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    # Look up specific entry by ID
    entry = service.get_by_id("Fireball|XPHB")

    if entry:
        print(f"Found: {entry['name']}")
        print(f"Type: {entry['type']}")
        print(f"Source: {entry['source']}")

        if entry.get('level') is not None:
            print(f"Level: {entry['level']}")
        if entry.get('school'):
            print(f"School: {entry['school']}")

        print(f"\nReferences: {len(entry.get('references', []))}")
        for ref in entry.get('references', []):
            print(f"  - {ref}")
    else:
        print("Entry not found")

    print()


def example_5_filtered_search():
    """Example 5: Search with type filtering."""
    print("=" * 70)
    print("EXAMPLE 5: Filtered Search (Spells Only)")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    # Search only within spells
    results = service.search(
        query="area of effect damage",
        limit=3,
        filter_type="spell",  # Only search spells
        expand_references=False
    )

    print(f"Found {len(results)} spells:")
    for i, result in enumerate(results, 1):
        level = result.get('level', 'N/A')
        print(f"  {i}. {result['name']} (Level {level})")

    print()


def example_6_backward_compatibility():
    """Example 6: Backward-compatible API."""
    print("=" * 70)
    print("EXAMPLE 6: Backward-Compatible API")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    # Use old VectorService API
    results = service.search_combat_rules(
        query="advantage and disadvantage",
        top_k=2
    )

    print("Results (using old API format):")
    for result in results:
        print(f"  ID: {result['id']}")
        print(f"  Score: {result['score']}")
        print(f"  Text preview: {result['text'][:100]}...")
        print()


def example_7_stats():
    """Example 7: Database statistics."""
    print("=" * 70)
    print("EXAMPLE 7: Database Statistics")
    print("=" * 70)
    print()

    service = create_lance_rules_service()

    stats = service.get_stats()

    print(f"Database: {stats['db_path']}")
    print(f"Table: {stats['table_name']}")
    print(f"Total entries: {stats['total_entries']}")

    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("LANCEDB RULES SERVICE - EXAMPLES")
    print("=" * 70)
    print()

    try:
        # Run all examples
        example_1_basic_search()
        example_2_with_references()
        example_3_formatted_context()
        example_4_direct_lookup()
        example_5_filtered_search()
        example_6_backward_compatibility()
        example_7_stats()

        print("=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you've run build_lance_rules_db.py first:")
        print("  uv run python build_lance_rules_db.py")


if __name__ == "__main__":
    main()

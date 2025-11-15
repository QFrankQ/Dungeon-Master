"""
Test script for LanceDB rules search.

This script provides an interactive interface to test semantic search
over the D&D 5e SRD rules database.

Usage:
    python src/db/test_lance_db.py
"""

from lance_service import LanceService
import sys


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader."""
    print("\n" + "-" * 70)
    print(text)
    print("-" * 70)


def display_stats(service: LanceService):
    """Display database statistics."""
    print_header("DATABASE STATISTICS")

    stats = service.get_stats()

    print(f"\nTable: {stats['table_name']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Embedding model: {stats['embedding_model']}")
    print(f"Embedding dimension: {stats['embedding_dimension']}")

    print(f"\nChunks by category:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        print(f"  {cat:20s}: {count:4d} chunks")


def run_test_queries(service: LanceService):
    """Run a set of predefined test queries."""
    print_header("RUNNING TEST QUERIES")

    test_queries = [
        ("How does grappling work in combat?", None),
        ("What are the Fighter class features?", "Classes"),
        ("How does the Fireball spell work?", "Spells"),
        ("What are the rules for surprise in combat?", "Gameplay"),
        ("Tell me about the Beholder monster", "Monsters"),
        ("What weapons can a Fighter use?", "Equipment"),
    ]

    for query, category in test_queries:
        print_subheader(f"Query: '{query}'")
        if category:
            print(f"Category filter: {category}")

        results = service.search_rules(query, top_k=2, category_filter=category)

        if results:
            for i, result in enumerate(results, 1):
                score = result.get('similarity_score', 0)
                print(f"\n[Result {i}] Relevance: {score:.1%}")
                print(f"  File: {result['filename']}")
                print(f"  Category: {result['category']}")
                if result.get('section_header'):
                    print(f"  Section: {result['section_header']}")
                print(f"  Preview: {result['text'][:200].strip()}...")
        else:
            print("\n  No results found.")


def interactive_search(service: LanceService):
    """Interactive search mode."""
    print_header("INTERACTIVE SEARCH MODE")
    print("\nEnter your questions about D&D 5e rules.")
    print("Type 'quit' or 'exit' to return to menu.")
    print("Type 'stats' to see database statistics.")

    while True:
        try:
            query = input("\nYour question: ").strip()

            if not query:
                continue

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if query.lower() == 'stats':
                display_stats(service)
                continue

            # Parse optional parameters
            top_k = 3
            category = None

            # Check for category filter in query
            if "[category:" in query.lower():
                import re
                match = re.search(r'\[category:\s*([^\]]+)\]', query, re.IGNORECASE)
                if match:
                    category = match.group(1).strip()
                    query = re.sub(r'\[category:[^\]]+\]', '', query, flags=re.IGNORECASE).strip()

            # Search
            results = service.search_rules(query, top_k=top_k, category_filter=category)

            if results:
                print(f"\nFound {len(results)} relevant results:\n")
                print(service.format_search_results(results, include_metadata=True))
            else:
                print("\nNo relevant results found. Try rephrasing your question.")

        except KeyboardInterrupt:
            print("\n\nExiting interactive mode...")
            break
        except Exception as e:
            print(f"\nError: {e}")


def main():
    """Main test interface."""
    print_header("D&D 5e Rules Database - Test Interface")

    # Initialize service
    try:
        service = LanceService(db_path="/home/kenshin/Dungeon-Master/lancedb", table_name="dnd_rules")
        print("\n✓ Connected to LanceDB")
    except Exception as e:
        print(f"\n✗ Error connecting to database: {e}")
        print("\nPlease run 'python src/db/embed_markdown_rules.py' first to create the database.")
        sys.exit(1)

    # Main menu
    while True:
        print("\n" + "=" * 70)
        print("MAIN MENU")
        print("=" * 70)
        print("\n1. Show database statistics")
        print("2. Run test queries")
        print("3. Interactive search")
        print("4. Exit")

        choice = input("\nSelect an option (1-4): ").strip()

        if choice == '1':
            display_stats(service)

        elif choice == '2':
            run_test_queries(service)

        elif choice == '3':
            interactive_search(service)

        elif choice == '4':
            print("\nGoodbye!")
            break

        else:
            print("\nInvalid choice. Please select 1-4.")


if __name__ == "__main__":
    main()

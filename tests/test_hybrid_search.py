"""
Test hybrid search functionality.

Usage:
    uv run python scripts/db/test_hybrid_search.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.lance_rules_service import create_lance_rules_service

def test_hybrid_search():
    """Test that hybrid search works for both semantic and keyword queries."""
    service = create_lance_rules_service()

    print("=" * 70)
    print("TESTING HYBRID SEARCH")
    print("=" * 70)

    # Test 1: Semantic query (should use vector search primarily)
    print("\n1. Semantic query: 'area of effect fire damage'")
    results = service.search("area of effect fire damage", limit=3, expand_references=False)
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r['id']} ({r['type']})")

    # Test 2: Exact name query (should use FTS primarily)
    print("\n2. Exact name query: 'Fireball'")
    results = service.search("Fireball", limit=3, expand_references=False)
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r['id']} ({r['type']})")

    # Test 3: Keyword query (should benefit from FTS)
    print("\n3. Keyword query: 'poisoned condition'")
    results = service.search("poisoned condition", limit=3, expand_references=False)
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r['id']} ({r['type']})")

    # Test 4: With type filtering
    print("\n4. Filtered query: 'shield' (spells only)")
    results = service.search("shield", limit=3, expand_references=False, filter_type="spell")
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r['id']} ({r['type']})")

    print("\n" + "=" * 70)
    print("✅ Hybrid search tests completed!")
    print("=" * 70)

if __name__ == "__main__":
    test_hybrid_search()

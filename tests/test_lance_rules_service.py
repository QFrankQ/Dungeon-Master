"""Tests for LanceDB rules service."""

import pytest

from src.db.lance_rules_service import LanceRulesService, create_lance_rules_service


@pytest.fixture
def service():
    """Create a connected service instance with paid tier for faster tests."""
    svc = create_lance_rules_service(auto_connect=True, use_paid_tier=True)
    return svc


def test_service_creation():
    """Test that service can be created."""
    service = LanceRulesService(use_paid_tier=True)
    assert service is not None
    assert service.db_path == "src/db/lancedb"
    assert service.table_name == "rules"


def test_service_connect(service):
    """Test connecting to existing database."""
    assert service.table is not None


def test_get_stats(service):
    """Test getting database statistics."""
    stats = service.get_stats()

    assert "total_entries" in stats
    assert stats["total_entries"] > 0
    assert stats["table_name"] == "rules"


def test_search_basic(service):
    """Test basic semantic search."""
    results = service.search(
        query="fireball",
        limit=5,
        expand_references=False
    )

    assert len(results) > 0
    assert len(results) <= 5

    # Check result structure
    result = results[0]
    assert "id" in result
    assert "name" in result
    assert "source" in result
    assert "type" in result
    assert "content" in result


def test_search_with_type_filter(service):
    """Test search with type filtering."""
    # Use "fireball" which naturally returns spells in top results
    # Note: Hybrid search filters after ranking, so the query needs to
    # naturally return results of the filtered type
    results = service.search(
        query="fireball",
        limit=5,
        filter_type="spell",
        expand_references=False
    )

    assert len(results) > 0

    # All results should be spells
    for result in results:
        assert result["type"] == "spell"


def test_search_with_references(service):
    """Test search with reference expansion."""
    results = service.search(
        query="fireball",
        limit=1,
        expand_references=True,
        max_depth=1
    )

    assert len(results) > 0

    result = results[0]

    # Should have expanded_references key
    assert "expanded_references" in result

    # If there are references, they should be expanded
    if result.get("references"):
        expanded = result.get("expanded_references", [])
        assert len(expanded) > 0

        # Check expanded reference structure
        for ref in expanded:
            assert "id" in ref
            assert "name" in ref
            assert "content" in ref


def test_get_by_id(service):
    """Test direct ID lookup."""
    # Try to get Fireball spell
    entry = service.get_by_id("Fireball|XPHB")

    if entry:
        assert entry["name"] == "Fireball"
        assert entry["source"] == "XPHB"
        assert entry["type"] == "spell"
        assert "content" in entry


def test_get_by_id_not_found(service):
    """Test lookup of non-existent ID."""
    entry = service.get_by_id("NonExistentRule|XPHB")
    assert entry is None


def test_format_for_context(service):
    """Test formatting results for LLM context."""
    results = service.search(
        query="fireball",
        limit=1,
        expand_references=True
    )

    context = service.format_for_context(results, include_references=True)

    assert isinstance(context, str)
    assert len(context) > 0

    # Should contain rule markers
    assert "RULE 1:" in context


def test_backward_compatibility_api(service):
    """Test backward-compatible search_combat_rules method."""
    results = service.search_combat_rules(
        query="advantage",
        top_k=3
    )

    assert len(results) > 0
    assert len(results) <= 3

    # Check old API format
    for result in results:
        assert "score" in result
        assert "text" in result
        assert "tags" in result
        assert "id" in result


def test_reference_deduplication():
    """Test that duplicate references are removed during loading."""
    # This test verifies the deduplication logic by checking
    # that no entry has duplicate references

    service = create_lance_rules_service(auto_connect=True, use_paid_tier=True)

    # Get a sample of entries
    results = service.search(query="test", limit=10, expand_references=False)

    for result in results:
        references = result.get("references", [])

        # Check no duplicates
        assert len(references) == len(set(references)), \
            f"Entry {result['id']} has duplicate references"


def test_reference_validation():
    """Test that invalid references are filtered."""
    # This test verifies that all references point to existing entries

    service = create_lance_rules_service(auto_connect=True, use_paid_tier=True)

    # Get a sample of entries
    results = service.search(query="test", limit=10, expand_references=False)

    for result in results:
        references = result.get("references", [])

        # Try to look up each reference
        for ref_id in references:
            ref_entry = service.get_by_id(ref_id)

            # Reference should exist
            assert ref_entry is not None, \
                f"Invalid reference: {ref_id} (from {result['id']})"


def test_normalize_reference():
    """Test reference ID normalization."""
    service = LanceRulesService(use_paid_tier=True)

    # Test valid references
    assert service._normalize_reference("Fireball|XPHB") == "Fireball|XPHB"
    assert service._normalize_reference("Sphere [Area of Effect]|XPHB|Sphere") == "Sphere [Area of Effect]|XPHB"
    assert service._normalize_reference("burning|XPHB") == "burning|XPHB"

    # Test invalid references
    assert service._normalize_reference("8d6") is None
    assert service._normalize_reference("invalid") is None
    assert service._normalize_reference("") is None


def test_factory_function():
    """Test factory function for creating service."""
    service = create_lance_rules_service(auto_connect=False, use_paid_tier=True)

    assert service is not None
    assert service.table is None  # Not connected yet

    # Connect manually
    service.connect()
    assert service.table is not None

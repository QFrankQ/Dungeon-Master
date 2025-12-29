"""Tests for DM Tools - query_rules_database tool and dependencies."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from pydantic_ai import RunContext

from src.agents.dm_tools import (
    query_rules_database,
    DMToolsDependencies,
    create_dm_tools,
    _format_lance_entry_to_cache,
    _format_rule_for_dm
)
from src.models.turn_context import TurnContext


# ==================== Test Fixtures ====================

@pytest.fixture
def mock_lance_service():
    """Create mock LanceRulesService for testing."""
    service = Mock()
    service.get_by_name = Mock()
    service.search = Mock()
    return service


@pytest.fixture
def mock_turn_manager():
    """Create mock TurnManager with current turn."""
    manager = Mock()

    # Create a mock current turn
    current_turn = TurnContext(
        turn_id="1",
        turn_level=0,
        current_step_objective="Test objective",
        metadata={}
    )
    manager.get_current_turn_context = Mock(return_value=current_turn)

    return manager


@pytest.fixture
def mock_rules_cache_service():
    """Create mock RulesCacheService for testing."""
    service = Mock()
    service.add_to_cache = Mock()
    return service


@pytest.fixture
def dm_deps(mock_lance_service, mock_turn_manager, mock_rules_cache_service):
    """Create DMToolsDependencies with mocks."""
    return DMToolsDependencies(
        lance_service=mock_lance_service,
        turn_manager=mock_turn_manager,
        rules_cache_service=mock_rules_cache_service
    )


@pytest.fixture
def mock_run_context(dm_deps):
    """Create mock RunContext for tool testing."""
    ctx = Mock(spec=RunContext)
    ctx.deps = dm_deps
    return ctx


# ==================== Sample Data ====================

def create_sample_lance_entry(name="Bless", entry_type="spell"):
    """Create sample LanceDB entry for testing."""
    return {
        "name": name,
        "type": entry_type,
        "content": "Whenever you make an attack roll or saving throw, you can roll 1d4 and add the number rolled to the attack roll or saving throw.",
        "metadata": {
            "level": 1,
            "school": "enchantment",
            "duration": "Concentration, up to 1 minute"
        }
    }


# ==================== Auto-Detect Short Query Tests ====================

class TestAutoDetectShortQueries:
    """Tests for auto-detect with short queries (≤10 words)."""

    @pytest.mark.asyncio
    async def test_short_query_exact_match_found(self, mock_run_context, mock_lance_service):
        """Test short query finds exact match and returns single result."""
        # Setup
        lance_entry = create_sample_lance_entry("Bless", "spell")
        mock_lance_service.get_by_name.return_value = lance_entry

        # Execute
        result = await query_rules_database(
            mock_run_context,
            query="Bless"  # Short query, auto-detects
        )

        # Verify exact match was tried
        mock_lance_service.get_by_name.assert_called_once_with("Bless")
        # Verify search was NOT called (exact match succeeded)
        mock_lance_service.search.assert_not_called()

        # Verify cache was updated
        mock_run_context.deps.rules_cache_service.add_to_cache.assert_called_once()
        cache_entry = mock_run_context.deps.rules_cache_service.add_to_cache.call_args[0][0]
        assert cache_entry["name"] == "Bless"
        assert cache_entry["entry_type"] == "spell"
        assert cache_entry["source"] == "lancedb"

        # Verify formatted result
        assert "Bless" in result
        assert "Spell" in result

    @pytest.mark.asyncio
    async def test_short_query_fallback_to_search(self, mock_run_context, mock_lance_service):
        """Test short query falls back to search when exact match fails."""
        # Setup
        lance_entry = create_sample_lance_entry("Fireball", "spell")
        mock_lance_service.get_by_name.return_value = None  # Exact match fails
        mock_lance_service.search.return_value = [lance_entry]  # Search succeeds

        # Execute
        result = await query_rules_database(
            mock_run_context,
            query="firebal"  # Typo - short query
        )

        # Verify fallback occurred
        mock_lance_service.get_by_name.assert_called_once_with("firebal")
        mock_lance_service.search.assert_called_once_with("firebal", limit=3)

        # Verify cache updated with search result
        mock_run_context.deps.rules_cache_service.add_to_cache.assert_called_once()
        cache_entry = mock_run_context.deps.rules_cache_service.add_to_cache.call_args[0][0]
        assert cache_entry["name"] == "Fireball"

        # Verify result
        assert "Fireball" in result


# ==================== Auto-Detect Long Query Tests ====================

class TestAutoDetectLongQueries:
    """Tests for auto-detect with long queries (>10 words)."""

    @pytest.mark.asyncio
    async def test_long_query_skips_exact_match(self, mock_run_context, mock_lance_service):
        """Test long query skips exact match and goes directly to search."""
        # Setup
        lance_entry = create_sample_lance_entry("Bless", "spell")
        mock_lance_service.search.return_value = [lance_entry]

        # Execute - query with >10 words
        result = await query_rules_database(
            mock_run_context,
            query="how does the blessing spell work and what are its effects on attack rolls?"
        )

        # Verify exact match was SKIPPED (query >10 words)
        mock_lance_service.get_by_name.assert_not_called()
        # Verify search was called directly
        mock_lance_service.search.assert_called_once()

        # Verify cache was updated
        mock_run_context.deps.rules_cache_service.add_to_cache.assert_called_once()
        cache_entry = mock_run_context.deps.rules_cache_service.add_to_cache.call_args[0][0]
        assert cache_entry["name"] == "Bless"

        # Verify result
        assert "Bless" in result

    @pytest.mark.asyncio
    async def test_long_query_no_results(self, mock_run_context, mock_lance_service):
        """Test long query returns error when search finds nothing."""
        # Setup
        mock_lance_service.search.return_value = []

        # Execute
        result = await query_rules_database(
            mock_run_context,
            query="this is a completely unknown query that has more than ten words total"
        )

        # Verify
        assert "No rules found" in result
        mock_run_context.deps.rules_cache_service.add_to_cache.assert_not_called()


# ==================== Limit Parameter Tests ====================

class TestLimitParameter:
    """Tests for limit parameter controlling number of results."""

    @pytest.mark.asyncio
    async def test_limit_default_three_results(self, mock_run_context, mock_lance_service):
        """Test default limit returns up to 3 results."""
        # Setup - mock search returns 5 results
        results = [
            create_sample_lance_entry("Bless", "spell"),
            create_sample_lance_entry("Shield", "spell"),
            create_sample_lance_entry("Haste", "spell"),
            create_sample_lance_entry("Fireball", "spell"),
            create_sample_lance_entry("Heal", "spell")
        ]
        mock_lance_service.get_by_name.return_value = None  # Force search
        mock_lance_service.search.return_value = results[:3]  # LanceDB returns limit

        # Execute without specifying limit (default=3)
        result = await query_rules_database(
            mock_run_context,
            query="spellcasting"
        )

        # Verify search was called with limit=3
        mock_lance_service.search.assert_called_once_with("spellcasting", limit=3)

        # Verify 3 results were cached
        assert mock_run_context.deps.rules_cache_service.add_to_cache.call_count == 3

        # Verify separator in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_limit_custom_value(self, mock_run_context, mock_lance_service):
        """Test custom limit parameter."""
        # Setup
        results = [create_sample_lance_entry(f"Spell{i}", "spell") for i in range(5)]
        mock_lance_service.get_by_name.return_value = None
        mock_lance_service.search.return_value = results

        # Execute with limit=5
        result = await query_rules_database(
            mock_run_context,
            query="magic spells",
            limit=5
        )

        # Verify search was called with limit=5
        mock_lance_service.search.assert_called_once_with("magic spells", limit=5)

        # Verify 5 results were cached
        assert mock_run_context.deps.rules_cache_service.add_to_cache.call_count == 5

    @pytest.mark.asyncio
    async def test_limit_clamped_to_max_ten(self, mock_run_context, mock_lance_service):
        """Test limit is clamped to maximum of 10."""
        # Setup
        mock_lance_service.get_by_name.return_value = None
        mock_lance_service.search.return_value = []

        # Execute with limit=20 (should be clamped to 10)
        await query_rules_database(
            mock_run_context,
            query="spells",
            limit=20
        )

        # Verify search was called with limit=10 (clamped)
        mock_lance_service.search.assert_called_once_with("spells", limit=10)


# ==================== Multi-Keyword Query Tests ====================

class TestMultiKeywordQueries:
    """Tests for multi-keyword queries (user's main use case)."""

    @pytest.mark.asyncio
    async def test_multi_keyword_query(self, mock_run_context, mock_lance_service):
        """Test query with multiple keywords returns multiple related rules."""
        # Setup - simulate finding bonus action, fireball, and concentration rules
        results = [
            {"name": "Bonus Action", "type": "action", "content": "You can take a bonus action..."},
            {"name": "Fireball", "type": "spell", "content": "A bright streak...", "metadata": {"level": 3}},
            {"name": "Concentration", "type": "variantrule", "content": "Some spells require concentration..."},
        ]
        mock_lance_service.get_by_name.return_value = None  # Short query but no exact match
        mock_lance_service.search.return_value = results

        # Execute multi-keyword query
        result = await query_rules_database(
            mock_run_context,
            query="bonus action fireball concentration",
            limit=5
        )

        # Verify search was called
        mock_lance_service.search.assert_called_once_with("bonus action fireball concentration", limit=5)

        # Verify all 3 results were cached
        assert mock_run_context.deps.rules_cache_service.add_to_cache.call_count == 3

        # Verify result contains separator
        assert "---" in result
        # Verify all rules mentioned
        assert "Bonus Action" in result
        assert "Fireball" in result
        assert "Concentration" in result


# ==================== Cache Population Tests ====================

class TestCachePopulation:
    """Tests for cache population behavior."""

    @pytest.mark.asyncio
    async def test_cache_populated_with_correct_schema(self, mock_run_context, mock_lance_service):
        """Test cache entry matches expected schema."""
        # Setup
        lance_entry = {
            "name": "Haste",
            "type": "spell",
            "content": "Target creature's speed doubles...",
            "metadata": {
                "level": 3,
                "school": "transmutation",
                "duration": "Concentration, up to 1 minute",
                "damage": "None"
            }
        }
        mock_lance_service.get_by_name.return_value = lance_entry

        # Execute (short query with exact match)
        await query_rules_database(mock_run_context, query="Haste")

        # Verify cache entry schema
        cache_entry = mock_run_context.deps.rules_cache_service.add_to_cache.call_args[0][0]

        # Required fields
        assert "name" in cache_entry
        assert "entry_type" in cache_entry
        assert "description" in cache_entry
        assert "source" in cache_entry

        # Values
        assert cache_entry["name"] == "Haste"
        assert cache_entry["entry_type"] == "spell"
        assert cache_entry["description"] == "Target creature's speed doubles..."
        assert cache_entry["source"] == "lancedb"

        # Metadata fields
        assert cache_entry["level"] == 3
        assert cache_entry["school"] == "transmutation"
        assert cache_entry["duration_text"] == "Concentration, up to 1 minute"

    @pytest.mark.asyncio
    async def test_cache_passed_to_current_turn(self, mock_run_context, mock_lance_service, mock_turn_manager):
        """Test cache entry is added to current turn context."""
        # Setup
        lance_entry = create_sample_lance_entry()
        mock_lance_service.get_by_name.return_value = lance_entry

        # Execute (short query with exact match)
        await query_rules_database(mock_run_context, query="Bless")

        # Verify turn context was passed to add_to_cache
        call_args = mock_run_context.deps.rules_cache_service.add_to_cache.call_args[0]
        turn_context = call_args[1]

        assert turn_context.turn_id == "1"
        assert turn_context.turn_level == 0

    @pytest.mark.asyncio
    async def test_all_results_cached(self, mock_run_context, mock_lance_service):
        """Test all results from multi-result query are cached."""
        # Setup
        results = [
            create_sample_lance_entry("Spell1", "spell"),
            create_sample_lance_entry("Spell2", "spell"),
            create_sample_lance_entry("Spell3", "spell")
        ]
        mock_lance_service.get_by_name.return_value = None  # Force search
        mock_lance_service.search.return_value = results

        # Execute
        await query_rules_database(mock_run_context, query="magic", limit=3)

        # Verify all 3 results were cached
        assert mock_run_context.deps.rules_cache_service.add_to_cache.call_count == 3

        # Verify each result was cached correctly
        cache_calls = mock_run_context.deps.rules_cache_service.add_to_cache.call_args_list
        assert cache_calls[0][0][0]["name"] == "Spell1"
        assert cache_calls[1][0][0]["name"] == "Spell2"
        assert cache_calls[2][0][0]["name"] == "Spell3"


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_no_active_turn(self, mock_run_context, mock_lance_service, mock_turn_manager):
        """Test error when no active turn exists."""
        # Setup
        mock_turn_manager.get_current_turn_context.return_value = None

        # Execute
        result = await query_rules_database(mock_run_context, query="Bless")

        # Verify
        assert "Error" in result
        assert "No active turn" in result

    @pytest.mark.asyncio
    async def test_both_exact_and_search_fail(self, mock_run_context, mock_lance_service):
        """Test error when both exact match and search fail."""
        # Setup
        mock_lance_service.get_by_name.return_value = None
        mock_lance_service.search.return_value = []

        # Execute
        result = await query_rules_database(
            mock_run_context,
            query="nonexistent"
        )

        # Verify both were tried
        mock_lance_service.get_by_name.assert_called_once()
        mock_lance_service.search.assert_called_once()

        # Verify error message
        assert "No rules found" in result
        mock_run_context.deps.rules_cache_service.add_to_cache.assert_not_called()


# ==================== Format Helper Tests ====================

class TestFormatHelpers:
    """Tests for _format_lance_entry_to_cache and _format_rule_for_dm."""

    def test_format_lance_entry_minimal(self):
        """Test formatting LanceDB entry with minimal fields."""
        lance_entry = {
            "name": "Test Spell",
            "type": "spell",
            "content": "Test description"
        }

        cache_entry = _format_lance_entry_to_cache(lance_entry)

        assert cache_entry["name"] == "Test Spell"
        assert cache_entry["entry_type"] == "spell"
        assert cache_entry["description"] == "Test description"
        assert cache_entry["source"] == "lancedb"

    def test_format_lance_entry_with_metadata(self):
        """Test formatting LanceDB entry with full metadata."""
        lance_entry = {
            "name": "Fireball",
            "type": "spell",
            "content": "Bright streak...",
            "metadata": {
                "level": 3,
                "school": "evocation",
                "duration": "Instantaneous",
                "damage": "8d6 fire"
            }
        }

        cache_entry = _format_lance_entry_to_cache(lance_entry)

        assert cache_entry["level"] == 3
        assert cache_entry["school"] == "evocation"
        assert cache_entry["duration_text"] == "Instantaneous"
        assert cache_entry["damage"] == "8d6 fire"

    def test_format_rule_for_dm_spell(self):
        """Test formatting cache entry for DM output (spell)."""
        cache_entry = {
            "name": "Bless",
            "entry_type": "spell",
            "description": "Test description",
            "level": 1,
            "school": "enchantment",
            "duration_text": "Concentration, up to 1 minute"
        }

        formatted = _format_rule_for_dm(cache_entry)

        assert "Bless (Spell, Level 1)" in formatted
        assert "Test description" in formatted
        assert "Duration: Concentration, up to 1 minute" in formatted
        assert "School: Enchantment" in formatted

    def test_format_rule_for_dm_item(self):
        """Test formatting cache entry for DM output (item)."""
        cache_entry = {
            "name": "Longsword",
            "entry_type": "item",
            "description": "Martial melee weapon",
            "rarity": "common",
            "damage": "1d8 slashing"
        }

        formatted = _format_rule_for_dm(cache_entry)

        assert "Longsword (Item, Common)" in formatted
        assert "Martial melee weapon" in formatted
        assert "Damage: 1d8 slashing" in formatted

    def test_format_rule_for_dm_condition(self):
        """Test formatting cache entry for DM output (condition)."""
        cache_entry = {
            "name": "Poisoned",
            "entry_type": "condition",
            "description": "Disadvantage on attack rolls and ability checks"
        }

        formatted = _format_rule_for_dm(cache_entry)

        assert "Poisoned (Condition)" in formatted
        assert "Disadvantage on attack rolls" in formatted


# ==================== Factory Function Tests ====================

class TestFactoryFunction:
    """Tests for create_dm_tools factory function."""

    def test_create_dm_tools(self, mock_lance_service, mock_turn_manager, mock_rules_cache_service):
        """Test factory function creates tools and dependencies."""
        tools, deps = create_dm_tools(
            lance_service=mock_lance_service,
            turn_manager=mock_turn_manager,
            rules_cache_service=mock_rules_cache_service
        )

        # Verify tools list (query_rules_database + query_character_ability)
        assert len(tools) == 2
        assert query_rules_database in tools

        # Verify dependencies
        assert isinstance(deps, DMToolsDependencies)
        assert deps.lance_service == mock_lance_service
        assert deps.turn_manager == mock_turn_manager
        assert deps.rules_cache_service == mock_rules_cache_service
        assert deps.state_manager is None  # Optional, not provided


# ==================== Integration Tests ====================

class TestDMToolsIntegration:
    """Integration tests with real TurnContext (mocked services)."""

    @pytest.mark.asyncio
    async def test_end_to_end_exact_match(self, mock_lance_service, mock_rules_cache_service):
        """Test end-to-end flow with exact match."""
        # Setup real TurnContext
        turn_manager = Mock()
        current_turn = TurnContext(
            turn_id="1",
            turn_level=0,
            current_step_objective="Test",
            metadata={}
        )
        turn_manager.get_current_turn_context = Mock(return_value=current_turn)

        # Setup deps
        deps = DMToolsDependencies(
            lance_service=mock_lance_service,
            turn_manager=turn_manager,
            rules_cache_service=mock_rules_cache_service
        )
        ctx = Mock(spec=RunContext)
        ctx.deps = deps

        # Setup LanceDB response
        lance_entry = create_sample_lance_entry("Shield", "spell")
        mock_lance_service.get_by_name.return_value = lance_entry

        # Execute (short query auto-detects exact match)
        result = await query_rules_database(ctx, query="Shield")

        # Verify
        assert "Shield" in result
        mock_rules_cache_service.add_to_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_queries_same_turn(self, mock_lance_service, mock_rules_cache_service):
        """Test multiple queries in same turn accumulate cache."""
        # Setup
        turn_manager = Mock()
        current_turn = TurnContext(
            turn_id="1",
            turn_level=0,
            current_step_objective="Test",
            metadata={}
        )
        turn_manager.get_current_turn_context = Mock(return_value=current_turn)

        deps = DMToolsDependencies(
            lance_service=mock_lance_service,
            turn_manager=turn_manager,
            rules_cache_service=mock_rules_cache_service
        )
        ctx = Mock(spec=RunContext)
        ctx.deps = deps

        # Setup responses
        mock_lance_service.get_by_name.side_effect = [
            create_sample_lance_entry("Bless", "spell"),
            create_sample_lance_entry("Shield", "spell"),
            create_sample_lance_entry("Haste", "spell")
        ]

        # Execute multiple queries (all short, auto-detect)
        await query_rules_database(ctx, query="Bless")
        await query_rules_database(ctx, query="Shield")
        await query_rules_database(ctx, query="Haste")

        # Verify all were cached
        assert mock_rules_cache_service.add_to_cache.call_count == 3

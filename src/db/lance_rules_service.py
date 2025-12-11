"""
Integrated LanceDB service for D&D rules with reference expansion.

This service provides:
1. Unified storage of rule content + embeddings + metadata
2. Automatic reference expansion using database queries
3. Validated and deduplicated references
4. Backward compatibility with existing VectorService API

Replaces both Qdrant vector database and filesystem-based reference lookups.
"""

import json
import logging
import os
import dotenv
dotenv.load_dotenv()

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import lancedb
from google import genai
from google.genai import types
from lancedb.pydantic import LanceModel, Vector


logger = logging.getLogger(__name__)


class RuleEntry(LanceModel):
    """Schema for D&D rule entries in LanceDB."""

    # Primary identifiers
    id: str  # Format: "Name|Source" (e.g., "Fireball|XPHB")
    name: str
    source: str
    type: str  # spell, item, feat, action, etc.

    # Content and embedding
    content: str  # Full markdown content
    vector: Vector(768)  # pyright: ignore[reportInvalidTypeForm] # Gemini embedding (gemini-embedding-001)

    # Metadata for filtering (spell-specific)
    level: Optional[int] = None
    school: Optional[str] = None

    # Metadata for filtering (item-specific)
    rarity: Optional[str] = None

    # Metadata for compatibility
    tags: List[str] = []

    # References for expansion (deduplicated and validated)
    references: List[str] = []  # ["Sphere|XPHB", "burning|XPHB"]
    reference_types: Dict[str, List[str]] = {}  # {"variantrule": ["Sphere|XPHB"], ...}


class LanceRulesService:
    """
    Unified vector database service for D&D rules.

    Features:
    - Semantic search using embeddings
    - Automatic reference expansion
    - Metadata filtering
    - Efficient batch operations
    - Backward compatibility with VectorService API
    """

    def __init__(
        self,
        db_path: str = "src/db/lancedb",
        table_name: str = "rules",
        api_key: Optional[str] = None,
        use_paid_tier: bool = False
    ):
        """
        Initialize the Lance rules service.

        Args:
            db_path: Path to LanceDB database
            table_name: Name of the table to use
            api_key: Optional API key override. If None, uses environment variables
            use_paid_tier: If True, use paid tier API key for higher rate limits
        """
        self.db_path = db_path
        self.table_name = table_name
        self.db = None
        self.table = None
        self._embedding_client = None
        self._api_key = api_key
        self._use_paid_tier = use_paid_tier
        self._name_index = None  # Built on connect() for fast name lookups

    def connect(self):
        """Connect to existing LanceDB database."""
        self.db = lancedb.connect(self.db_path)
        try:
            self.table = self.db.open_table(self.table_name)
            logger.info(f"Connected to existing table '{self.table_name}'")
            # Build name index for fast lookups
            self._build_name_index()
        except Exception as e:
            logger.error(f"Failed to open table '{self.table_name}': {e}")
            raise

    def _get_embedding_client(self):
        """Get or create embedding client (lazy initialization)."""
        if self._embedding_client is None:
            # Determine which API key to use
            if self._api_key:
                # Use explicitly provided key
                api_key = self._api_key
                logger.debug("Using explicitly provided API key")
            elif self._use_paid_tier:
                # Try paid tier keys first
                api_key = os.getenv("GEMINI_API_KEY_PAID_TIER") or os.getenv("GOOGLE_API_KEY_PAID_TIER")
                if not api_key:
                    raise ValueError(
                        "Paid tier API key requested but GEMINI_API_KEY_PAID_TIER or "
                        "GOOGLE_API_KEY_PAID_TIER environment variable not set"
                    )
                logger.info("Using paid tier API key for higher rate limits")
            else:
                # Use free tier key (default)
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError(
                        "GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set"
                    )
                logger.debug("Using free tier API key")

            self._embedding_client = genai.Client(api_key=api_key)

        return self._embedding_client

    def _build_name_index(self):
        """Build in-memory index mapping names to entry IDs for fast lookup."""
        if self.table is None:
            raise ValueError("Table not connected. Call connect() first.")

        logger.info("Building name index for fast lookups...")
        self._name_index = {}

        # Fetch all entries using LanceDB's native query
        # Only select name, id, and type fields for efficiency
        all_entries = self.table.search().limit(10000).to_list()

        for entry in all_entries:
            name = entry['name']
            entry_id = entry['id']
            entry_type = entry['type']

            if name not in self._name_index:
                self._name_index[name] = []

            self._name_index[name].append({
                'id': entry_id,
                'type': entry_type
            })

        logger.info(f"Name index built: {len(self._name_index)} unique names")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using Gemini.

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector
        """
        client = self._get_embedding_client()

        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=[text],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )

        return result.embeddings[0].values

    def _get_content_file(
        self,
        metadata_file: Path,
        rendered_rules_dir: Path
    ) -> Optional[Path]:
        """
        Find the corresponding markdown file for a metadata file.

        Args:
            metadata_file: Path to metadata JSON file
            rendered_rules_dir: Base directory for rendered rules

        Returns:
            Path to markdown file or None if not found
        """
        # Get relative path from metadata_dir
        # metadata_file is like: metadata/spell/fireball_XPHB.json
        # We want: rendered_rules/spell/fireball_XPHB.md

        relative_path = metadata_file.relative_to(metadata_file.parent.parent)
        content_file = rendered_rules_dir / relative_path.parent / metadata_file.name.replace('.json', '.md')

        if content_file.exists():
            return content_file

        logger.warning(f"Content file not found for {metadata_file.name}")
        return None

    def _normalize_reference(self, ref_content: str) -> Optional[str]:
        """
        Normalize a reference string to a clean ID.

        Examples:
            "Sphere [Area of Effect]|XPHB|Sphere" → "Sphere [Area of Effect]|XPHB"
            "burning|XPHB" → "burning|XPHB"
            "8d6" → None (not a reference to another entry)

        Args:
            ref_content: Raw reference string from metadata

        Returns:
            Normalized ID or None if not a valid reference
        """
        parts = ref_content.split('|')

        # Must have at least name|source
        if len(parts) >= 2:
            name = parts[0].strip()
            source = parts[1].strip()
            return f"{name}|{source}"

        # Not a valid reference (e.g., "8d6" dice notation)
        return None

    def _process_references(
        self,
        metadata: Dict,
        valid_ids: Set[str],
        entry_id: str
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Process references with deduplication and validation.

        Steps:
        1. Extract all references from metadata
        2. Normalize reference IDs ("Name|Source" format)
        3. Deduplicate using set
        4. Filter to only valid IDs (exist in dataset)
        5. Group by reference type

        Args:
            metadata: Entry metadata dictionary
            valid_ids: Set of all valid entry IDs
            entry_id: ID of current entry (for logging)

        Returns:
            (deduplicated_refs, refs_by_type)
        """
        seen = set()
        references = []
        reference_types = {}

        for ref in metadata.get('references', []):
            ref_content = ref.get('content', '')
            ref_type = ref.get('tagType', 'unknown')

            # Normalize to "Name|Source" format
            ref_id = self._normalize_reference(ref_content)

            # Skip if invalid format
            if not ref_id:
                logger.debug(f"Skipping non-reference: {ref_content}")
                continue

            # Skip if duplicate
            if ref_id in seen:
                logger.debug(f"Duplicate reference removed: {ref_id} (from {entry_id})")
                continue

            # Skip if doesn't exist in dataset
            if ref_id not in valid_ids:
                logger.warning(f"Dangling reference filtered: {ref_id} (from {entry_id})")
                continue

            # Valid reference - add it
            seen.add(ref_id)
            references.append(ref_id)

            # Group by type
            if ref_type not in reference_types:
                reference_types[ref_type] = []
            reference_types[ref_type].append(ref_id)

        return references, reference_types

    def load_from_files(
        self,
        rendered_rules_dir: Path,
        metadata_dir: Path,
        show_progress: bool = True,
        max_entries: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Load all rules from filesystem into LanceDB.

        Uses two-phase loading:
        1. Phase 1: Build set of all valid IDs
        2. Phase 2: Process entries with validated references

        Args:
            rendered_rules_dir: Directory containing markdown files
            metadata_dir: Directory containing metadata JSON files
            show_progress: Whether to print progress updates
            max_entries: Maximum number of entries to process (for testing). None = process all

        Returns:
            Statistics dictionary with loading results
        """
        logger.info("Starting LanceDB loading process...")

        # Phase 1: Load all entries to build valid ID set
        if show_progress:
            print("Phase 1: Scanning all metadata files to build ID index...")

        entries = []
        valid_ids = set()

        for i, meta_file in enumerate(metadata_dir.rglob("*.json"), 1):
            try:
                # Show progress every 100 files
                if show_progress and i % 100 == 0:
                    print(f"  Scanned {i} files...")

                metadata = json.loads(meta_file.read_text())

                # Build unique ID
                entry_id = f"{metadata['name']}|{metadata['source']}"
                valid_ids.add(entry_id)

                # Store for phase 2
                entries.append((meta_file, metadata, entry_id))

            except Exception as e:
                logger.error(f"Error loading metadata from {meta_file}: {e}")
                continue

        if show_progress:
            print(f"  Found {len(valid_ids)} unique rule entries")

        # Phase 2: Process entries with validated references
        if show_progress:
            print("\nPhase 2: Processing entries with validated references...")
            if max_entries:
                print(f"  ⚠️  TEST MODE: Processing only first {max_entries} entries")

        # Limit entries if max_entries specified
        if max_entries:
            entries = entries[:max_entries]

        final_entries = []
        stats = {
            "total_entries": 0,
            "total_references_found": 0,
            "duplicate_references_removed": 0,
            "invalid_references_filtered": 0,
            "final_valid_references": 0,
            "reference_types": {},
            "fts_index_created": False,
            "errors": []
        }

        for i, (meta_file, metadata, entry_id) in enumerate(entries, 1):
            if show_progress and i % 100 == 0:
                print(f"  Processed {i}/{len(entries)} entries...")

            try:
                # Get content file
                content_file = self._get_content_file(meta_file, rendered_rules_dir)
                if not content_file:
                    stats["errors"].append(f"Missing content for {entry_id}")
                    continue

                content = content_file.read_text()

                # Process references (deduplicate + validate)
                refs_before = len(metadata.get('references', []))
                refs, ref_types = self._process_references(metadata, valid_ids, entry_id)

                # Update stats
                stats["total_references_found"] += refs_before
                stats["final_valid_references"] += len(refs)

                for ref_type, ref_list in ref_types.items():
                    if ref_type not in stats["reference_types"]:
                        stats["reference_types"][ref_type] = 0
                    stats["reference_types"][ref_type] += len(ref_list)

                # Create embedding
                embedding = self._get_embedding(content)

                # Create entry
                entry = {
                    "id": entry_id,
                    "name": metadata['name'],
                    "source": metadata['source'],
                    "type": metadata['type'],
                    "content": content,
                    "vector": embedding,
                    "level": metadata.get('level'),
                    "school": metadata.get('school'),
                    "rarity": metadata.get('rarity'),
                    "tags": metadata.get('tags', []),
                    "references": refs,
                    "reference_types": ref_types
                }

                final_entries.append(entry)
                stats["total_entries"] += 1

            except Exception as e:
                logger.error(f"Error processing {entry_id}: {e}")
                stats["errors"].append(f"Error processing {entry_id}: {str(e)}")
                continue

        # Calculate derived stats
        stats["duplicate_references_removed"] = (
            stats["total_references_found"] - stats["final_valid_references"]
        )

        if show_progress:
            print(f"\nPhase 3: Creating LanceDB table...")

        # Create or overwrite table
        self.db = lancedb.connect(self.db_path)
        self.table = self.db.create_table(
            self.table_name,
            data=final_entries,
            mode="overwrite"
        )

        if show_progress:
            print(f"✓ Created table '{self.table_name}' with {len(final_entries)} entries")

        # Phase 4: Create FTS index for hybrid search
        if show_progress:
            print(f"\nPhase 4: Creating FTS index for hybrid search...")

        try:
            self.table.create_fts_index("content", replace=True)
            if show_progress:
                print(f"✓ Created FTS index on 'content' column")
            stats["fts_index_created"] = True
        except Exception as e:
            logger.warning(f"Failed to create FTS index: {e}")
            if show_progress:
                print(f"⚠️  Failed to create FTS index: {e}")
            stats["fts_index_created"] = False

        logger.info(f"Successfully loaded {len(final_entries)} entries into LanceDB")

        return stats

    def search(
        self,
        query: str,
        limit: int = 5,
        expand_references: bool = True,
        max_depth: int = 1,
        filter_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Hybrid search combining semantic vector search and full-text search.

        Uses LanceDB's native hybrid search with automatic reciprocal rank fusion (RRF)
        to combine results from:
        1. Vector similarity search (semantic understanding)
        2. Full-text search (keyword matching on content and name)

        This provides better results for both conceptual queries ("how does fireball work?")
        and exact name queries ("Shield spell").

        Args:
            query: Search query (used for both vector and text search)
            limit: Maximum number of results
            expand_references: Whether to include referenced entries
            max_depth: How deep to expand references (recursion depth)
            filter_type: Optional filter by type (spell, item, etc.)

        Returns:
            List of results with hybrid scoring and optional expanded references
        """
        if self.table is None:
            self.connect()

        # Get query embedding for vector search
        query_embedding = self._get_embedding(query)

        # Perform hybrid search (vector + FTS)
        # Since we have pre-computed embeddings, use the explicit vector()/text() API
        # LanceDB automatically uses reciprocal rank fusion (RRF) to combine results
        search = self.table.search(query_type="hybrid").vector(query_embedding).text(query)

        # Apply type filter if specified
        if filter_type:
            search = search.where(f"type = '{filter_type}'")

        # Set limit
        search = search.limit(limit)

        # Execute search
        results = search.to_list()

        # Expand references if requested
        if expand_references:
            for result in results:
                result['expanded_references'] = self._expand_references(
                    result.get('references', []),
                    max_depth=max_depth,
                    visited=set([result['id']])
                )

        return results

    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        """
        Retrieve a specific entry by ID.

        Args:
            entry_id: Entry ID (format: "Name|Source")

        Returns:
            Entry dictionary or None if not found
        """
        if self.table is None:
            self.connect()
        #TODO: .search() might not be the most efficient way to get by ID
        results = self.table.search().where(f"id = '{entry_id}'").limit(1).to_list()

        if results:
            return results[0]
        return None

    def get_by_name(
        self,
        name: str,
        entry_type: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Retrieve an entry by name without needing to know the source.

        Uses in-memory name index for O(1) lookup, then fetches full entry by ID.
        If multiple entries match the name, returns the first match.
        Use entry_type to disambiguate (e.g., "Shield" spell vs "Shield" action).

        Args:
            name: Entry name (e.g., "Shield", "Fireball", "Poisoned")
            entry_type: Optional type filter (e.g., "spell", "condition", "item")

        Returns:
            Matching entry or None if not found

        Examples:
            >>> service.get_by_name('Fireball')  # Returns Fireball spell
            >>> service.get_by_name('Shield', entry_type='spell')  # Returns Shield spell, not action
            >>> service.get_by_name('Poisoned', entry_type='condition')  # Returns Poisoned condition
        """
        if self.table is None:
            self.connect()

        if self._name_index is None:
            raise ValueError("Name index not built. This should happen automatically on connect().")

        # Look up name in index
        if name not in self._name_index:
            return None

        candidates = self._name_index[name]

        # Filter by type if specified
        if entry_type:
            candidates = [c for c in candidates if c['type'] == entry_type]

        if not candidates:
            return None

        # Return first match (fetch full entry by ID)
        return self.get_by_id(candidates[0]['id'])

    def _expand_references(
        self,
        reference_ids: List[str],
        max_depth: int = 1,
        visited: Set[str] = None
    ) -> List[Dict]:
        """
        Recursively expand references.

        Args:
            reference_ids: List of reference IDs to expand
            max_depth: Maximum recursion depth
            visited: Set of already-visited IDs (cycle detection)

        Returns:
            List of referenced entries
        """
        if max_depth == 0 or not reference_ids:
            return []

        if visited is None:
            visited = set()

        expanded = []

        for ref_id in reference_ids:
            # Skip if already visited
            if ref_id in visited:
                continue

            visited.add(ref_id)

            # Fetch the referenced entry
            entry = self.get_by_id(ref_id)

            if entry:
                # Recursively expand nested references
                if max_depth > 1 and entry.get('references'):
                    entry['expanded_references'] = self._expand_references(
                        entry['references'],
                        max_depth=max_depth - 1,
                        visited=visited.copy()
                    )

                expanded.append(entry)

        return expanded

    def format_for_context(
        self,
        results: List[Dict],
        include_references: bool = True
    ) -> str:
        """
        Format search results into a context string for LLM prompts.

        Args:
            results: Search results from search()
            include_references: Whether to include expanded references

        Returns:
            Formatted context string
        """
        lines = []

        for i, result in enumerate(results, 1):
            lines.append("=" * 70)
            lines.append(f"RULE {i}: {result['name']} ({result['type']})")
            lines.append("=" * 70)
            lines.append(result['content'])
            lines.append("")

            # Add expanded references
            if include_references and result.get('expanded_references'):
                lines.append(f"--- Referenced Rules for {result['name']} ---")
                lines.append("")

                for ref in result['expanded_references']:
                    lines.append(f"  • {ref['name']} ({ref['type']})")
                    # Indent the content
                    ref_content = ref['content'].replace('\n', '\n    ')
                    lines.append(f"    {ref_content}")
                    lines.append("")

        return "\n".join(lines)

    def search_combat_rules(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Backward-compatible method matching VectorService.search_combat_rules().

        This allows existing code to use LanceDB without changes.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Results formatted to match old API: {score, text, tags, id}
        """
        results = self.search(query, limit=top_k, expand_references=False)

        # Format to match old API
        return [
            {
                "score": 1.0,  # LanceDB returns distance, normalize if needed
                "text": r['content'],
                "tags": r.get('tags', []),
                "id": r['id']
            }
            for r in results
        ]

    def get_stats(self) -> Dict:
        """Get database statistics."""
        if self.table is None:
            self.connect()

        total_entries = self.table.count_rows()

        # This would require pandas, simplified for now
        return {
            "total_entries": total_entries,
            "table_name": self.table_name,
            "db_path": self.db_path
        }


def create_lance_rules_service(
    db_path: str = "src/db/lancedb",
    auto_connect: bool = True,
    use_paid_tier: bool = False,
    api_key: Optional[str] = None
) -> LanceRulesService:
    """
    Factory function for LanceRulesService.

    Args:
        db_path: Path to LanceDB database
        auto_connect: Whether to automatically connect to existing DB
        use_paid_tier: If True, use paid tier API key for higher rate limits
        api_key: Optional explicit API key override

    Returns:
        Initialized LanceRulesService
    """
    service = LanceRulesService(
        db_path=db_path,
        use_paid_tier=use_paid_tier,
        api_key=api_key
    )

    if auto_connect:
        try:
            service.connect()
        except Exception as e:
            logger.warning(f"Auto-connect failed: {e}. Database may not exist yet.")

    return service

"""
LanceDB service for D&D 5e rules retrieval.

This module provides a local vector database using LanceDB and sentence-transformers
for fast, semantic search over D&D 5e SRD markdown files.
"""

import lancedb
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import pyarrow as pa


class LanceService:
    """Local vector database service using LanceDB."""

    def __init__(
        self,
        db_path: str = ".lancedb",
        table_name: str = "dnd_rules",
        model_name: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the LanceDB service.

        Args:
            db_path: Path to store the LanceDB database
            table_name: Name of the table to use
            model_name: Sentence-transformers model for embeddings
                       (all-MiniLM-L6-v2: 384 dims, fast, good quality)
        """
        self.db_path = db_path
        self.table_name = table_name
        self.model_name = model_name

        # Initialize sentence-transformers model
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Connect to LanceDB
        self.db = lancedb.connect(db_path)

        # Reference to table (lazy loaded)
        self._table = None

    @property
    def table(self):
        """Lazy load the table."""
        if self._table is None:
            if self.table_name in self.db.table_names():
                self._table = self.db.open_table(self.table_name)
            else:
                raise ValueError(
                    f"Table '{self.table_name}' does not exist. "
                    f"Run embed_markdown_rules.py to create it."
                )
        return self._table

    def create_table(self, initial_data: Optional[List[Dict]] = None) -> None:
        """
        Create the rules table.

        Args:
            initial_data: Optional list of dictionaries with embeddings
        """
        if self.table_name in self.db.table_names():
            print(f"Table '{self.table_name}' already exists. Overwriting...")
            self.db.drop_table(self.table_name)

        # Define schema
        schema = pa.schema([
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), self.embedding_dim)),
            pa.field("file_path", pa.string()),
            pa.field("category", pa.string()),
            pa.field("filename", pa.string()),
            pa.field("main_header", pa.string()),
            pa.field("section_header", pa.string()),
            pa.field("subsection_header", pa.string()),
            pa.field("chunk_index", pa.int32()),
        ])

        # Create table with schema
        if initial_data:
            self._table = self.db.create_table(self.table_name, data=initial_data, schema=schema)
        else:
            # Create empty table
            self._table = self.db.create_table(self.table_name, schema=schema)

        print(f"Created table '{self.table_name}' with {len(initial_data) if initial_data else 0} records")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a text string.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_tensor=False
        )
        return [emb.tolist() for emb in embeddings]

    def add_documents(self, documents: List[Dict]) -> None:
        """
        Add documents to the table.

        Args:
            documents: List of dicts with 'text' and metadata fields
                      (embeddings will be generated automatically)
        """
        # Generate embeddings for all documents
        texts = [doc["text"] for doc in documents]
        embeddings = self.embed_batch(texts)

        # Add vectors to documents
        for doc, embedding in zip(documents, embeddings):
            doc["vector"] = embedding

        # Insert into table
        self.table.add(documents)
        print(f"Added {len(documents)} documents to table")

    def search_rules(
        self,
        query: str,
        top_k: int = 3,
        category_filter: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict]:
        """
        Search for relevant rules using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            category_filter: Optional category to filter (e.g., "Spells", "Combat")
            min_score: Minimum similarity score (0-1, higher is more similar)

        Returns:
            List of matching documents with metadata and scores
        """
        # Generate query embedding
        query_vector = self.embed_text(query)

        # Build search
        search = self.table.search(query_vector).limit(top_k * 2)  # Get more for filtering

        # Apply category filter if provided
        if category_filter:
            search = search.where(f"category = '{category_filter}'")

        # Execute search
        results = search.to_list()

        # Filter by minimum score and limit
        filtered_results = []
        for result in results:
            # LanceDB uses _distance (L2 distance), convert to similarity score
            # Lower distance = higher similarity
            # Normalize to 0-1 range (approximate)
            distance = result.get("_distance", 1.0)
            similarity = 1 / (1 + distance)  # Convert distance to similarity

            if similarity >= min_score:
                result["similarity_score"] = similarity
                filtered_results.append(result)

            if len(filtered_results) >= top_k:
                break

        return filtered_results

    def format_search_results(self, results: List[Dict], include_metadata: bool = True) -> str:
        """
        Format search results for display or injection into context.

        Args:
            results: Search results from search_rules()
            include_metadata: Whether to include file paths and categories

        Returns:
            Formatted string with results
        """
        if not results:
            return "No relevant rules found."

        formatted = []
        for i, result in enumerate(results, 1):
            parts = [f"[Result {i}]"]

            if include_metadata:
                parts.append(f"Source: {result['filename']} ({result['category']})")
                if result.get('section_header'):
                    parts.append(f"Section: {result['section_header']}")
                parts.append(f"Relevance: {result.get('similarity_score', 0):.2%}")

            parts.append(f"\n{result['text']}\n")
            formatted.append('\n'.join(parts))

        return '\n---\n'.join(formatted)

    def get_stats(self) -> Dict:
        """Get statistics about the database."""
        if self._table is None:
            return {"status": "Table not loaded"}

        count = self.table.count_rows()
        categories = self.table.to_pandas()['category'].value_counts().to_dict()

        return {
            "table_name": self.table_name,
            "total_chunks": count,
            "categories": categories,
            "embedding_model": self.model_name,
            "embedding_dimension": self.embedding_dim
        }


def main():
    """Test the LanceService."""
    service = LanceService()

    try:
        stats = service.get_stats()
        print(stats)
        print("Database Stats:")
        print(f"  Total chunks: {stats['total_chunks']}")
        print(f"  Embedding model: {stats['embedding_model']}")
        print(f"  Embedding dim: {stats['embedding_dimension']}")
        print(f"\nCategories:")
        for cat, count in stats['categories'].items():
            print(f"  {cat}: {count}")

        # Test search
        print("\n" + "="*60)
        print("Testing search: 'How does grappling work?'")
        print("="*60 + "\n")

        results = service.search_rules("How does grappling work?", top_k=2)
        print(service.format_search_results(results))

    except ValueError as e:
        print(f"Error: {e}")
        print("Run embed_markdown_rules.py first to create the database.")


if __name__ == "__main__":
    main()

"""
Embedding script to process D&D 5e SRD markdown files and populate LanceDB.

This script:
1. Scans the rules/ directory for all markdown files
2. Chunks them using the MarkdownChunker
3. Generates embeddings using sentence-transformers
4. Stores everything in LanceDB for semantic search

Usage:
    python src/db/embed_markdown_rules.py
"""

from pathlib import Path
from markdown_chunker import MarkdownChunker
from lance_service import LanceService
import time


def main():
    """Main embedding pipeline."""
    print("="*70)
    print("D&D 5e SRD Rules Embedding Pipeline")
    print("="*70)

    # Configuration
    rules_dir = Path("/home/kenshin/Dungeon-Master/rules")
    db_path = "/home/kenshin/Dungeon-Master/lancedb"
    table_name = "dnd_rules"
    model_name = "all-MiniLM-L6-v2"  # Fast, lightweight, 384 dimensions

    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        print("Please ensure the rules folder exists.")
        return

    print(f"\nConfiguration:")
    print(f"  Rules directory: {rules_dir}")
    print(f"  Database path: {db_path}")
    print(f"  Table name: {table_name}")
    print(f"  Embedding model: {model_name}")
    print()

    # Step 1: Chunk all markdown files
    print("STEP 1: Chunking markdown files")
    print("-" * 70)

    chunker = MarkdownChunker(min_chunk_size=100, max_chunk_size=1000)
    start_time = time.time()

    chunks = chunker.chunk_directory(rules_dir, file_pattern="*.md")

    chunk_time = time.time() - start_time
    print(f"\n[OK] Chunked {len(chunks)} chunks in {chunk_time:.2f} seconds")
    print()

    if not chunks:
        print("ERROR: No chunks generated. Check the rules directory.")
        return

    # Show sample chunks
    print("Sample chunks:")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n  Chunk {i}:")
        print(f"    File: {chunk.filename}")
        print(f"    Category: {chunk.category}")
        print(f"    Section: {chunk.section_header or 'N/A'}")
        print(f"    Length: {len(chunk.text)} chars")

    # Step 2: Initialize LanceDB service
    print("\n" + "-" * 70)
    print("STEP 2: Initializing LanceDB")
    print("-" * 70)

    service = LanceService(
        db_path=db_path,
        table_name=table_name,
        model_name=model_name
    )

    # Step 3: Generate embeddings and create table
    print("\n" + "-" * 70)
    print("STEP 3: Generating embeddings and populating database")
    print("-" * 70)
    print("This may take several minutes depending on the number of chunks...")
    print()

    start_time = time.time()

    # Convert chunks to dictionaries
    chunk_dicts = [chunk.to_dict() for chunk in chunks]

    # Generate embeddings in batch
    texts = [chunk.text for chunk in chunks]
    print(f"Generating embeddings for {len(texts)} chunks...")
    embeddings = service.embed_batch(texts, batch_size=32)

    # Add embeddings to chunk dictionaries
    for chunk_dict, embedding in zip(chunk_dicts, embeddings):
        chunk_dict["vector"] = embedding

    # Create table with all data
    service.create_table(initial_data=chunk_dicts)

    embed_time = time.time() - start_time
    print(f"\n[OK] Generated embeddings and created table in {embed_time:.2f} seconds")

    # Step 4: Show statistics
    print("\n" + "=" * 70)
    print("DATABASE STATISTICS")
    print("=" * 70)

    stats = service.get_stats()
    print(f"\nTable: {stats['table_name']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Embedding model: {stats['embedding_model']}")
    print(f"Embedding dimension: {stats['embedding_dimension']}")
    print(f"\nChunks by category:")
    for cat, count in sorted(stats['categories'].items()):
        print(f"  {cat:20s}: {count:4d} chunks")

    # Step 5: Test search
    print("\n" + "=" * 70)
    print("TESTING SEARCH")
    print("=" * 70)

    test_queries = [
        "How does grappling work?",
        "What are the Fighter class features?",
        "How does the Fireball spell work?",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 70)

        results = service.search_rules(query, top_k=2)

        for i, result in enumerate(results, 1):
            print(f"\n[Result {i}] ({result.get('similarity_score', 0):.1%} match)")
            print(f"  File: {result['filename']}")
            print(f"  Category: {result['category']}")
            if result.get('section_header'):
                print(f"  Section: {result['section_header']}")
            print(f"  Preview: {result['text'][:150]}...")

    # Summary
    print("\n" + "=" * 70)
    print("EMBEDDING COMPLETE!")
    print("=" * 70)
    print(f"\n[OK] Processed {len(chunks)} chunks from {rules_dir}")
    print(f"[OK] Database ready at: {db_path}/{table_name}")
    print(f"[OK] Total time: {chunk_time + embed_time:.2f} seconds")
    print(f"\nYou can now use LanceService to search D&D 5e rules semantically!")


if __name__ == "__main__":
    main()

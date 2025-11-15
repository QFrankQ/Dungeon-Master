"""
Markdown chunking utility for D&D 5e SRD rules.

This module provides functionality to chunk markdown files by headers,
preserving metadata and context for semantic search.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class MarkdownChunk:
    """Represents a chunk of markdown content with metadata."""

    text: str
    file_path: str
    category: str  # e.g., "Classes", "Spells", "Gameplay"
    filename: str
    main_header: str  # The main # header (e.g., "COMBAT")
    section_header: Optional[str]  # The ## header for this chunk
    subsection_header: Optional[str]  # The ### header if present
    chunk_index: int  # Order within the file

    def to_dict(self) -> Dict:
        """Convert chunk to dictionary for LanceDB storage."""
        return {
            "text": self.text,
            "file_path": self.file_path,
            "category": self.category,
            "filename": self.filename,
            "main_header": self.main_header,
            "section_header": self.section_header or "",
            "subsection_header": self.subsection_header or "",
            "chunk_index": self.chunk_index,
        }


class MarkdownChunker:
    """Chunks markdown files by headers for semantic search."""

    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 1000):
        """
        Initialize the chunker.

        Args:
            min_chunk_size: Minimum characters per chunk (will merge small chunks)
            max_chunk_size: Maximum characters per chunk (will split large chunks)
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk_file(self, file_path: Path) -> List[MarkdownChunk]:
        """
        Chunk a markdown file by headers.

        Args:
            file_path: Path to the markdown file

        Returns:
            List of MarkdownChunk objects
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract category from path (e.g., "Classes", "Spells", "Gameplay")
        parts = file_path.parts
        rules_idx = parts.index('rules') if 'rules' in parts else -1
        category = parts[rules_idx + 1] if rules_idx >= 0 and rules_idx + 1 < len(parts) else "Unknown"

        filename = file_path.name
        file_path_str = str(file_path)

        # Extract main header (# Header)
        main_header_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        main_header = main_header_match.group(1).strip() if main_header_match else filename.replace('.md', '')

        # Split by ## headers (level 2)
        chunks = []
        sections = re.split(r'\n(?=##\s+)', content)

        chunk_index = 0
        for section in sections:
            if not section.strip():
                continue

            # Extract section header (##)
            section_header_match = re.search(r'^##\s+(.+)$', section, re.MULTILINE)
            section_header = section_header_match.group(1).strip() if section_header_match else None

            # For very large sections, split by ### headers
            if len(section) > self.max_chunk_size and '###' in section:
                subsections = re.split(r'\n(?=###\s+)', section)
                for subsection in subsections:
                    if not subsection.strip():
                        continue

                    subsection_header_match = re.search(r'^###\s+(.+)$', subsection, re.MULTILINE)
                    subsection_header = subsection_header_match.group(1).strip() if subsection_header_match else None

                    # Build context-aware chunk text
                    chunk_text = self._build_chunk_text(
                        main_header, section_header, subsection_header, subsection
                    )

                    chunk = MarkdownChunk(
                        text=chunk_text,
                        file_path=file_path_str,
                        category=category,
                        filename=filename,
                        main_header=main_header,
                        section_header=section_header,
                        subsection_header=subsection_header,
                        chunk_index=chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            else:
                # Single chunk for this section
                chunk_text = self._build_chunk_text(
                    main_header, section_header, None, section
                )

                chunk = MarkdownChunk(
                    text=chunk_text,
                    file_path=file_path_str,
                    category=category,
                    filename=filename,
                    main_header=main_header,
                    section_header=section_header,
                    subsection_header=None,
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1

        # Handle files with no ## headers (chunk entire content)
        if not chunks:
            chunk_text = f"# {main_header}\n\n{content}"
            chunk = MarkdownChunk(
                text=chunk_text,
                file_path=file_path_str,
                category=category,
                filename=filename,
                main_header=main_header,
                section_header=None,
                subsection_header=None,
                chunk_index=0
            )
            chunks.append(chunk)

        return chunks

    def _build_chunk_text(
        self,
        main_header: str,
        section_header: Optional[str],
        subsection_header: Optional[str],
        content: str
    ) -> str:
        """
        Build context-aware chunk text with header hierarchy.

        This ensures the chunk contains enough context for semantic search.
        """
        parts = [f"# {main_header}"]

        if section_header:
            parts.append(f"## {section_header}")

        if subsection_header:
            parts.append(f"### {subsection_header}")

        # Add the actual content (clean up extra headers already included)
        clean_content = content
        if subsection_header:
            clean_content = re.sub(r'^###\s+' + re.escape(subsection_header) + r'\s*\n', '', clean_content, count=1)
        if section_header:
            clean_content = re.sub(r'^##\s+' + re.escape(section_header) + r'\s*\n', '', clean_content, count=1)

        parts.append(clean_content.strip())

        return '\n\n'.join(parts)

    def chunk_directory(self, rules_dir: Path, file_pattern: str = "*.md") -> List[MarkdownChunk]:
        """
        Recursively chunk all markdown files in a directory.

        Args:
            rules_dir: Path to the rules directory
            file_pattern: Glob pattern for files to process

        Returns:
            List of all chunks from all files
        """
        all_chunks = []
        markdown_files = list(rules_dir.rglob(file_pattern))

        print(f"Found {len(markdown_files)} markdown files to process")

        for idx, file_path in enumerate(markdown_files, 1):
            try:
                chunks = self.chunk_file(file_path)
                all_chunks.extend(chunks)

                if idx % 50 == 0:
                    print(f"Processed {idx}/{len(markdown_files)} files ({len(all_chunks)} chunks so far)")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        print(f"\nCompleted! Total chunks: {len(all_chunks)}")
        return all_chunks


def main():
    """Test the chunker on a sample file."""
    from pathlib import Path

    # Test on Combat.md
    test_file = Path("//wsl.localhost/Ubuntu/home/kenshin/Dungeon-Master/rules/Gameplay/Combat.md")

    if test_file.exists():
        chunker = MarkdownChunker(min_chunk_size=100, max_chunk_size=1000)
        chunks = chunker.chunk_file(test_file)

        print(f"Chunked {test_file.name} into {len(chunks)} chunks:\n")
        for i, chunk in enumerate(chunks[:3], 1):  # Show first 3 chunks
            print(f"--- Chunk {i} ---")
            print(f"Category: {chunk.category}")
            print(f"Main Header: {chunk.main_header}")
            print(f"Section: {chunk.section_header}")
            print(f"Text preview: {chunk.text[:200]}...")
            print()
    else:
        print(f"Test file not found: {test_file}")


if __name__ == "__main__":
    main()

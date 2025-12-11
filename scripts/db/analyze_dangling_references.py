"""
Analyze dangling references in D&D rules metadata.

This script identifies all references that point to rules not in the dataset,
grouped and sorted by source, without requiring database rebuild or embeddings.

Usage:
    uv run python scripts/db/analyze_dangling_references.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def normalize_reference(ref_content: str) -> tuple[str, str] | None:
    """
    Normalize a reference string to (name, source) tuple.

    Returns:
        (name, source) tuple or None if invalid
    """
    parts = ref_content.split('|')

    if len(parts) >= 2:
        name = parts[0].strip()
        source = parts[1].strip()
        return (name, source)

    return None


def load_valid_ids(metadata_dir: Path) -> Set[str]:
    """Load all valid rule IDs from metadata."""
    valid_ids = set()

    for meta_file in metadata_dir.rglob("*.json"):
        try:
            metadata = json.loads(meta_file.read_text())
            entry_id = f"{metadata['name']}|{metadata['source']}"
            valid_ids.add(entry_id)
        except Exception as e:
            print(f"Error loading {meta_file.name}: {e}")
            continue

    return valid_ids


def analyze_references(metadata_dir: Path, valid_ids: Set[str]) -> Dict:
    """
    Analyze all references and find dangling ones.

    Returns:
        Dictionary with analysis results
    """
    # Track statistics
    stats = {
        'total_entries': 0,
        'total_references': 0,
        'duplicate_references': 0,
        'dangling_references': 0,
        'valid_references': 0,
    }

    # Track dangling references by source
    dangling_by_source = defaultdict(set)  # source -> set of (name, ref_type)
    dangling_details = []  # List of (ref_id, ref_type, referencing_entry)

    # Track actual duplicates
    duplicate_count = 0

    for meta_file in metadata_dir.rglob("*.json"):
        try:
            metadata = json.loads(meta_file.read_text())
            entry_id = f"{metadata['name']}|{metadata['source']}"
            stats['total_entries'] += 1

            # Process references with deduplication tracking
            seen = set()

            for ref in metadata.get('references', []):
                ref_content = ref.get('content', '')
                ref_type = ref.get('tagType', 'unknown')
                stats['total_references'] += 1

                # Normalize reference
                normalized = normalize_reference(ref_content)
                if not normalized:
                    continue  # Skip invalid format

                name, source = normalized
                ref_id = f"{name}|{source}"

                # Check for duplicates
                if ref_id in seen:
                    duplicate_count += 1
                    stats['duplicate_references'] += 1
                    continue

                seen.add(ref_id)

                # Check if valid
                if ref_id not in valid_ids:
                    stats['dangling_references'] += 1
                    dangling_by_source[source].add((name, ref_type))
                    dangling_details.append((ref_id, ref_type, entry_id))
                else:
                    stats['valid_references'] += 1

        except Exception as e:
            print(f"Error processing {meta_file.name}: {e}")
            continue

    return {
        'stats': stats,
        'dangling_by_source': dict(dangling_by_source),
        'dangling_details': dangling_details
    }


def print_analysis(results: Dict):
    """Print formatted analysis results."""
    stats = results['stats']
    dangling_by_source = results['dangling_by_source']
    dangling_details = results['dangling_details']

    print("\n" + "=" * 70)
    print("DANGLING REFERENCES ANALYSIS")
    print("=" * 70)

    print(f"\n📊 Overall Statistics:")
    print(f"  Total entries analyzed: {stats['total_entries']}")
    print(f"  Total references found: {stats['total_references']}")
    print(f"  Valid references: {stats['valid_references']}")
    print(f"  Duplicate references: {stats['duplicate_references']}")
    print(f"  Dangling references: {stats['dangling_references']}")

    # Calculate percentages
    if stats['total_references'] > 0:
        dangling_pct = (stats['dangling_references'] / stats['total_references']) * 100
        duplicate_pct = (stats['duplicate_references'] / stats['total_references']) * 100
        print(f"\n📈 Breakdown:")
        print(f"  Dangling: {dangling_pct:.1f}%")
        print(f"  Duplicates: {duplicate_pct:.1f}%")

    # Print dangling references by source
    print(f"\n📚 Dangling References by Source:")
    print(f"  (Sorted by count)")
    print()

    # Sort sources by count
    sorted_sources = sorted(
        dangling_by_source.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    for source, refs in sorted_sources:
        print(f"  {source}: {len(refs)} dangling references")

        # Group by reference type
        by_type = defaultdict(list)
        for name, ref_type in refs:
            by_type[ref_type].append(name)

        for ref_type, names in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"    [{ref_type}]: {len(names)} references")
            # Show first 5 examples
            for name in sorted(names)[:5]:
                print(f"      - {name}")
            if len(names) > 5:
                print(f"      ... and {len(names) - 5} more")
        print()

    # Export detailed report
    print("=" * 70)
    print("DETAILED REPORT")
    print("=" * 70)

    # Ensure output directory exists
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)

    # Write report to output directory
    report_path = output_dir / 'dangling_references_report.json'
    print(f"\nExporting detailed report to: {report_path}")

    # Create detailed report
    report = {
        'summary': stats,
        'by_source': {
            source: {
                'count': len(refs),
                'references': [
                    {'name': name, 'type': ref_type}
                    for name, ref_type in sorted(refs)
                ]
            }
            for source, refs in sorted_sources
        },
        'all_dangling': [
            {
                'reference_id': ref_id,
                'type': ref_type,
                'referenced_by': entry_id
            }
            for ref_id, ref_type, entry_id in sorted(dangling_details)
        ]
    }

    # Write report
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print("\n✅ Report saved!")
    print("\nThe report includes:")
    print("  - Summary statistics")
    print("  - Dangling references grouped by source")
    print("  - Complete list with reference types and sources")


def main():
    """Run dangling reference analysis."""
    print("=" * 70)
    print("DANGLING REFERENCES ANALYZER")
    print("=" * 70)
    print()

    metadata_dir = Path("src/db/metadata")

    if not metadata_dir.exists():
        print(f"❌ Error: {metadata_dir} does not exist")
        return

    print(f"📂 Analyzing metadata from: {metadata_dir}")
    print()

    # Phase 1: Load valid IDs
    print("Phase 1: Loading valid rule IDs...")
    valid_ids = load_valid_ids(metadata_dir)
    print(f"  Found {len(valid_ids)} valid rules")

    # Phase 2: Analyze references
    print("\nPhase 2: Analyzing references...")
    results = analyze_references(metadata_dir, valid_ids)

    # Print results
    print_analysis(results)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

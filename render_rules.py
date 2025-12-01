"""
Render all D&D rule files from src/db/rules/ to markdown and metadata.

This script processes all the filtered rule JSON files and generates:
1. Clean markdown files for vector embeddings (src/db/rendered_rules/)
2. Structured metadata JSON files for knowledge graph construction (src/db/metadata/)
"""

import subprocess
import re
import shutil
from pathlib import Path


def parse_renderer_output(output):
    """Parse the renderer output to extract statistics."""
    # Look for "Found X {type} entries"
    found_match = re.search(r'Found (\d+) \w+ entries', output)
    # Look for "Completed: X successful, Y errors"
    completed_match = re.search(r'Completed: (\d+) successful, (\d+) errors', output)

    if found_match and completed_match:
        return {
            'found': int(found_match.group(1)),
            'success': int(completed_match.group(1)),
            'errors': int(completed_match.group(2))
        }
    return {'found': 0, 'success': 0, 'errors': 0}


def render_file(input_file, output_dir, renderer_script):
    """Render a single file using the Node.js renderer."""
    result = subprocess.run(
        ['node', str(renderer_script), '--input', str(input_file), '--output-dir', str(output_dir)],
        capture_output=True,
        text=True,
        check=True
    )
    return parse_renderer_output(result.stdout)


def main():
    # Setup paths
    rules_dir = Path('src/db/rules')
    rendered_rules_dir = Path('src/db/rendered_rules')
    metadata_dir = Path('src/db/metadata')
    renderer_script = Path('external/5etools-renderer/render-to-markdown.js')

    # Use temporary directory for rendering, then move metadata
    temp_output_dir = Path('output/temp_render')

    rule_files = [
        'filtered_actions.json',
        'filtered_conditions.json',
        'filtered_feats.json',
        'filtered_items.json',
        'filtered_objects.json',
        'filtered_optionalfeatures.json',
        'filtered_senses.json',
        'filtered_variant_rules.json',
        'spells_ALL_COMBINED.json'
    ]

    print("=" * 70)
    print("D&D RULES RENDERING PIPELINE")
    print("=" * 70)
    print(f"\nInput directory: {rules_dir}")
    print(f"Markdown output: {rendered_rules_dir}")
    print(f"Metadata output: {metadata_dir}")
    print(f"Files to process: {len(rule_files)}")
    print()

    # Track statistics
    total_success = 0
    total_errors = 0
    results = []

    # Process each file
    for i, filename in enumerate(rule_files, 1):
        input_file = rules_dir / filename

        if not input_file.exists():
            print(f"[{i}/{len(rule_files)}] ⚠️  SKIPPED: {filename} (file not found)")
            results.append({
                'file': filename,
                'status': 'skipped',
                'reason': 'not found'
            })
            continue

        print(f"[{i}/{len(rule_files)}] Processing: {filename}")

        try:
            # Render the file to temporary directory
            stats = render_file(input_file, temp_output_dir, renderer_script)

            success = stats['success']
            errors = stats['errors']

            total_success += success
            total_errors += errors

            status = "✅" if errors == 0 else "⚠️"
            print(f"    {status} Rendered {success} entries successfully")
            if errors > 0:
                print(f"    ⚠️  {errors} errors")

            results.append({
                'file': filename,
                'status': 'success',
                'entries': success,
                'errors': errors
            })

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results.append({
                'file': filename,
                'status': 'error',
                'reason': str(e)
            })

    # Move rendered files to final locations
    print("\n" + "=" * 70)
    print("ORGANIZING OUTPUT")
    print("=" * 70)

    # Move content directories to rendered_rules
    for type_dir in temp_output_dir.iterdir():
        if type_dir.is_dir() and type_dir.name != 'metadata':
            target_dir = rendered_rules_dir / type_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(type_dir), str(target_dir))
            print(f"  ✓ Moved {type_dir.name} to rendered_rules/")

    # Move metadata directory
    temp_metadata = temp_output_dir / 'metadata'
    if temp_metadata.exists():
        for type_dir in temp_metadata.iterdir():
            if type_dir.is_dir():
                target_dir = metadata_dir / type_dir.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.move(str(type_dir), str(target_dir))
                print(f"  ✓ Moved {type_dir.name} metadata to metadata/")

    # Clean up temp directory
    if temp_output_dir.exists():
        shutil.rmtree(temp_output_dir)

    # Print summary
    print("\n" + "=" * 70)
    print("RENDERING COMPLETE")
    print("=" * 70)
    print(f"\nTotal entries rendered: {total_success}")
    print(f"Total errors: {total_errors}")
    print(f"\nOutput structure:")
    print(f"  - Markdown files: {rendered_rules_dir}/{{type}}/{{name}}_{{source}}.md")
    print(f"  - Metadata files: {metadata_dir}/{{type}}/{{name}}_{{source}}.json")

    # Show file breakdown
    print("\n" + "-" * 70)
    print("File Breakdown:")
    print("-" * 70)
    for result in results:
        if result['status'] == 'success':
            print(f"  ✅ {result['file']}: {result['entries']} entries")
        elif result['status'] == 'skipped':
            print(f"  ⚠️  {result['file']}: SKIPPED ({result['reason']})")
        else:
            print(f"  ❌ {result['file']}: ERROR - {result['reason']}")

    print("\n" + "=" * 70)
    print("Next steps:")
    print("  1. Check markdown in:", rendered_rules_dir)
    print("  2. Check metadata in:", metadata_dir)
    print("  3. Use markdown files for vector embeddings")
    print("  4. Use metadata files for knowledge graph construction")
    print("=" * 70)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Import markdown files into SQLite cache with dynamic schema.

Based on Simon Willison's markdown-to-sqlite approach, this tool:
- Scans markdown files recursively
- Parses YAML frontmatter
- Extracts H1 title and H2 sections
- Creates database columns dynamically from frontmatter fields
- Stores full body content for retrieval

The database schema evolves automatically based on frontmatter fields found.
"""

import click
from pathlib import Path
import hashlib
import yaml
import re
import sys
from typing import Dict, Optional, Tuple
from sqlite_utils import Database


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown content

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    if not content.startswith('---'):
        return {}, content

    try:
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            remaining = parts[2].strip()
            return frontmatter or {}, remaining
    except yaml.YAMLError:
        pass

    return {}, content


def extract_h1_title(content: str) -> Optional[str]:
    """Extract the first H1 heading as the title.

    Args:
        content: Markdown content

    Returns:
        H1 title or None
    """
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else None


def extract_lead(content: str) -> str:
    """Extract lead paragraph (content between H1 and first H2).

    Args:
        content: Markdown content

    Returns:
        Lead paragraph text
    """
    # Remove H1 if present
    content_after_h1 = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE).strip()

    # Extract content before first H2
    match = re.search(r'^(.*?)(?=^##\s+|\Z)', content_after_h1, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return content_after_h1


def parse_h2_sections(content: str, allowed_sections: Optional[set] = None) -> Dict[str, str]:
    """Parse H2 sections from markdown content.

    Args:
        content: Markdown content
        allowed_sections: If provided, only extract these section names

    Returns:
        Dictionary mapping normalized section names to content
    """
    sections = {}
    current_section = None
    current_content = []

    for line in content.split('\n'):
        if line.startswith('## '):
            # Save previous section
            if current_section and (allowed_sections is None or current_section in allowed_sections):
                sections[current_section] = '\n'.join(current_content).strip()

            # Start new section - normalize name
            section_name = line[3:].strip().lower()
            section_name = re.sub(r'[^a-z0-9_]', '_', section_name)
            section_name = re.sub(r'_+', '_', section_name).strip('_')

            current_section = section_name
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section and (allowed_sections is None or current_section in allowed_sections):
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def get_section_names(content: str) -> list[str]:
    """Extract just the section names from markdown content.

    Args:
        content: Markdown content

    Returns:
        List of normalized section names
    """
    sections = []
    for line in content.split('\n'):
        if line.startswith('## '):
            section_name = line[3:].strip().lower()
            section_name = re.sub(r'[^a-z0-9_]', '_', section_name)
            section_name = re.sub(r'_+', '_', section_name).strip('_')
            sections.append(section_name)
    return sections


def analyze_section_frequency(files: list[Path], top_n: int) -> set[str]:
    """Analyze section frequency across files and return top N sections.

    Args:
        files: List of markdown files to analyze
        top_n: Number of top sections to return (0 means all)

    Returns:
        Set of top N most common section names
    """
    from collections import Counter

    if top_n == 0:
        return None  # None means extract all sections

    all_sections = []
    for file_path in files:
        try:
            content = file_path.read_text(encoding='utf-8')
            sections = get_section_names(content)
            all_sections.extend(sections)
        except Exception:
            continue

    section_counts = Counter(all_sections)
    top_sections = [name for name, _ in section_counts.most_common(top_n)]
    return set(top_sections)


def process_markdown_file(path: Path, root: Path, allowed_sections: Optional[set] = None) -> Dict:
    """Process a single markdown file into a database record.

    Args:
        path: Path to markdown file
        root: Root directory for relative path calculation
        allowed_sections: If provided, only extract these section names

    Returns:
        Dictionary with all fields for database insertion
    """
    content = path.read_text(encoding='utf-8')

    # Parse frontmatter
    frontmatter, body = parse_frontmatter(content)

    # Extract structure
    title = extract_h1_title(body)
    lead = extract_lead(body)
    sections = parse_h2_sections(body, allowed_sections)

    # Calculate relative path
    try:
        rel_path = str(path.relative_to(root))
    except ValueError:
        rel_path = str(path)

    # Prefix section columns to distinguish from frontmatter
    prefixed_sections = {f'section_{key}': value for key, value in sections.items()}

    # Create document with dynamic fields from frontmatter
    doc = {
        '_id': hashlib.sha1(rel_path.encode('utf-8')).hexdigest(),
        '_path': rel_path,
        '_sections': list(sections.keys()),  # Ordered list of section names
        'title': title or '',
        'body': body,
        'lead': lead,
        'file_modified': path.stat().st_mtime,
        **(frontmatter or {}),  # Unpack frontmatter as columns
        **prefixed_sections,  # Unpack H2 sections as prefixed columns
    }

    return doc


def validate_column_count(docs: list, max_columns: int) -> tuple[bool, int, dict]:
    """Validate that total unique columns won't exceed SQLite limit.

    Args:
        docs: List of document dictionaries
        max_columns: Maximum allowed columns

    Returns:
        Tuple of (is_valid, total_columns, column_breakdown)
        where column_breakdown is a dict with counts by category
    """
    if not docs:
        return True, 0, {}

    # Collect all unique column names across all documents
    all_columns = set()
    frontmatter_cols = set()
    section_cols = set()
    base_cols = {'_id', '_path', '_sections', 'title', 'body', 'lead', 'file_modified'}

    for doc in docs:
        for col in doc.keys():
            all_columns.add(col)
            if col.startswith('section_'):
                section_cols.add(col)
            elif col not in base_cols:
                frontmatter_cols.add(col)

    total = len(all_columns)
    breakdown = {
        'total': total,
        'base': len(base_cols),
        'frontmatter': len(frontmatter_cols),
        'sections': len(section_cols)
    }

    is_valid = total <= max_columns
    return is_valid, total, breakdown


@click.command()
@click.option('--db', default='cache.db', help='Database file path')
@click.option('--root', default='.', help='Root directory containing markdown files', type=click.Path(exists=True))
@click.option('--table', default='docs', help='Table name (default: docs)')
@click.option('--pattern', default='**/*.md', help='Glob pattern for markdown files')
@click.option('--max-columns', default=1800, type=int, help='Maximum allowed columns (default: 1800, SQLite limit: 2000)')
@click.option('--top-sections', default=20, type=int, help='Extract only top N most common sections (default: 20, 0=all)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(db, root, table, pattern, max_columns, top_sections, verbose):
    """
    Import markdown files into SQLite cache with dynamic schema.

    The database schema is created automatically based on YAML frontmatter
    fields and H2 section headings found in the files.

    Examples:
        import.py --db cache.db --root ~/notes
        import.py --db tasks.db --root ~/tasks --table tasks
        import.py --db skills.db --root ~/.claude/skills --pattern "*/SKILL.md"
    """
    root_path = Path(root).resolve()
    db_path = Path(db)

    if verbose:
        click.echo(f"📂 Scanning {root_path} for {pattern}")
        click.echo(f"💾 Database: {db_path}")
        click.echo(f"📊 Table: {table}")
        click.echo()

    # Find all markdown files
    md_files = list(root_path.glob(pattern))

    if not md_files:
        click.echo(f"❌ No markdown files found matching {pattern} in {root_path}", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Found {len(md_files)} files")
        click.echo()

    # Analyze section frequency if top-sections is enabled
    allowed_sections = None
    if top_sections > 0:
        if verbose:
            click.echo(f"🔍 Analyzing section frequency across {len(md_files)} files...")
        allowed_sections = analyze_section_frequency(md_files, top_sections)
        if verbose and allowed_sections:
            click.echo(f"📊 Extracting top {len(allowed_sections)} sections:")
            for section in sorted(allowed_sections):
                click.echo(f"  - {section}")
            click.echo()

    # Process all files
    docs = []
    for md_file in md_files:
        if verbose:
            click.echo(f"📄 {md_file.relative_to(root_path)}")

        try:
            doc = process_markdown_file(md_file, root_path, allowed_sections)
            docs.append(doc)
        except Exception as e:
            click.echo(f"⚠️  Error processing {md_file}: {e}", err=True)
            continue

    # Validate column count before importing
    if verbose:
        click.echo("\n🔍 Validating schema...")

    is_valid, total_cols, breakdown = validate_column_count(docs, max_columns)

    if verbose:
        click.echo(f"📊 Column breakdown:")
        click.echo(f"  - Base columns: {breakdown['base']}")
        click.echo(f"  - Frontmatter columns: {breakdown['frontmatter']}")
        click.echo(f"  - Section columns: {breakdown['sections']}")
        click.echo(f"  - Total: {breakdown['total']} (limit: {max_columns})")
        click.echo()

    # Show warning if approaching limit (within 10% of max)
    warning_threshold = int(max_columns * 0.9)
    if total_cols >= warning_threshold and total_cols <= max_columns:
        click.echo(f"⚠️  Warning: Approaching column limit ({total_cols}/{max_columns})", err=True)
        click.echo(f"   Consider reducing document diversity or increasing --max-columns", err=True)
        click.echo()

    if not is_valid:
        click.echo(f"❌ Column limit exceeded: {total_cols} columns > {max_columns} limit", err=True)
        click.echo(f"   Base columns: {breakdown['base']}", err=True)
        click.echo(f"   Frontmatter columns: {breakdown['frontmatter']}", err=True)
        click.echo(f"   Section columns: {breakdown['sections']}", err=True)
        click.echo(f"\n💡 Options:", err=True)
        click.echo(f"   1. Reduce document diversity (fewer unique H2 sections/frontmatter fields)", err=True)
        click.echo(f"   2. Increase limit with --max-columns (SQLite max: 2000)", err=True)
        click.echo(f"   3. Split into multiple databases by document type", err=True)
        sys.exit(1)

    # Import to database with dynamic schema
    # Use upsert one at a time to allow schema evolution
    database = Database(str(db_path))

    imported = 0
    for doc in docs:
        try:
            database[table].upsert(doc, pk='_id', alter=True)
            imported += 1
        except Exception as e:
            click.echo(f"⚠️  Error upserting {doc.get('_path', 'unknown')}: {e}", err=True)

    if verbose:
        click.echo()
    click.echo(f"✅ Imported {imported} of {len(docs)} documents into {db_path}:{table}")

    # Show schema info
    columns = database[table].columns
    click.echo(f"📋 Schema has {len(columns)} columns")

    if verbose:
        click.echo("\nColumns:")
        for col in columns:
            click.echo(f"  - {col.name} ({col.type})")


if __name__ == '__main__':
    main()

"""Core markdown processing functions for sqldown.

Extracts from markdown files:
- YAML frontmatter
- H1 titles
- Lead paragraphs
- H2 sections (with optional filtering)

Includes column limit validation and top-N section extraction.
"""

import hashlib
import re
import yaml
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


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
    content_after_h1 = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE).strip()
    match = re.search(r'^(.*?)(?=^##\s+|\Z)', content_after_h1, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return content_after_h1


def parse_h2_sections(content: str, allowed_sections: Optional[Set[str]] = None) -> Dict[str, str]:
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


def get_section_names(content: str) -> List[str]:
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


def analyze_section_frequency(files: List[Path], top_n: int) -> Optional[Set[str]]:
    """Analyze section frequency across files and return top N sections.

    Args:
        files: List of markdown files to analyze
        top_n: Number of top sections to return (0 means all)

    Returns:
        Set of top N most common section names, or None if top_n is 0
    """
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


def process_markdown_file(path: Path, root: Path, allowed_sections: Optional[Set[str]] = None) -> Dict:
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


def validate_column_count(docs: List[Dict], max_columns: int) -> Tuple[bool, int, Dict[str, int]]:
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


def load_markdown(
    root_path: Path,
    db_path: Path,
    table: str = "docs",
    pattern: str = "**/*.md",
    max_columns: int = 1800,
    top_sections: int = 20,
    verbose: bool = False
) -> int:
    """Load markdown files into SQLite database.

    Args:
        root_path: Directory containing markdown files
        db_path: Database file path
        table: Table name
        pattern: Glob pattern for markdown files
        max_columns: Maximum allowed columns
        top_sections: Extract only top N most common sections (0=all)
        verbose: Show detailed progress

    Returns:
        Number of documents successfully loaded

    Raises:
        ValueError: If column limit would be exceeded
    """
    from sqlite_utils import Database

    # Find all markdown files
    md_files = list(root_path.glob(pattern))

    if not md_files:
        raise ValueError(f"No markdown files found matching {pattern} in {root_path}")

    # Analyze section frequency if top-sections is enabled
    allowed_sections = None
    if top_sections > 0:
        allowed_sections = analyze_section_frequency(md_files, top_sections)

    # Process all files
    docs = []
    for md_file in md_files:
        try:
            doc = process_markdown_file(md_file, root_path, allowed_sections)
            docs.append(doc)
        except Exception as e:
            if verbose:
                print(f"Warning: Error processing {md_file}: {e}")
            continue

    # Validate column count before importing
    is_valid, total_cols, breakdown = validate_column_count(docs, max_columns)

    if not is_valid:
        raise ValueError(
            f"Column limit exceeded: {total_cols} columns > {max_columns} limit. "
            f"Base: {breakdown['base']}, Frontmatter: {breakdown['frontmatter']}, "
            f"Sections: {breakdown['sections']}"
        )

    # Import to database
    database = Database(str(db_path))
    imported = 0
    for doc in docs:
        try:
            database[table].upsert(doc, pk='_id', alter=True)
            imported += 1
        except Exception as e:
            if verbose:
                print(f"Warning: Error upserting {doc.get('_path', 'unknown')}: {e}")

    return imported


def reconstruct_markdown(row: Dict) -> str:
    """Reconstruct markdown content from a database row.

    Args:
        row: Database row as dictionary

    Returns:
        Complete markdown content with frontmatter, title, and sections
    """
    import json

    # System columns that shouldn't go into frontmatter or sections
    SYSTEM_COLUMNS = {
        '_id', '_path', '_sections', 'title', 'body', 'lead', 'file_modified'
    }

    parts = []

    # 1. Build frontmatter from non-system, non-section columns
    frontmatter = {}
    for key, value in row.items():
        if key not in SYSTEM_COLUMNS and not key.startswith('section_') and value is not None:
            frontmatter[key] = value

    if frontmatter:
        parts.append('---')
        parts.append(yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip())
        parts.append('---')
        parts.append('')

    # 2. Add H1 title
    if row.get('title'):
        parts.append(f"# {row['title']}")
        parts.append('')

    # 3. Add lead paragraph if exists
    if row.get('lead'):
        parts.append(row['lead'].strip())
        parts.append('')

    # 4. Add H2 sections in the order specified by _sections
    if row.get('_sections'):
        try:
            # Parse _sections JSON array
            sections_order = json.loads(row['_sections']) if isinstance(row['_sections'], str) else row['_sections']

            for section_name in sections_order:
                column_name = f'section_{section_name}'
                if column_name in row and row[column_name]:
                    # Convert section_name back to title case
                    section_title = section_name.replace('_', ' ').title()
                    parts.append(f"## {section_title}")
                    parts.append(row[column_name].strip())
                    parts.append('')
        except (json.JSONDecodeError, TypeError):
            pass

    return '\n'.join(parts).rstrip() + '\n'

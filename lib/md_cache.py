"""Markdown cache parsing functions.

Extracts from markdown files:
- YAML frontmatter
- H1 titles
- Lead paragraphs
- H2 sections
"""

import hashlib
import re
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple


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


def parse_h2_sections(content: str) -> Dict[str, str]:
    """Parse H2 sections from markdown content.

    Args:
        content: Markdown content

    Returns:
        Dictionary mapping normalized section names to content
    """
    sections = {}
    current_section = None
    current_content = []

    for line in content.split('\n'):
        if line.startswith('## '):
            # Save previous section
            if current_section:
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
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def process_markdown_file(path: Path, root: Path) -> Dict:
    """Process a single markdown file into a database record.

    Args:
        path: Path to markdown file
        root: Root directory for relative path calculation

    Returns:
        Dictionary with all fields for database insertion
    """
    content = path.read_text(encoding='utf-8')

    # Parse frontmatter
    frontmatter, body = parse_frontmatter(content)

    # Extract structure
    title = extract_h1_title(body)
    lead = extract_lead(body)
    sections = parse_h2_sections(body)

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

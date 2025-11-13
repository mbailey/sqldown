"""SQLDown - Bidirectional markdown ↔ SQLite conversion.

Public API:
    load_markdown() - Load markdown files into database
    process_file() - Process a single markdown file
    reconstruct_markdown() - Reconstruct markdown from database row
    analyze_section_frequency() - Analyze section frequency across files
    validate_column_count() - Validate column count against limit
"""

from .core import (
    analyze_section_frequency,
    extract_h1_title,
    extract_lead,
    get_section_names,
    load_markdown,
    parse_frontmatter,
    parse_h2_sections,
    process_markdown_file,
    reconstruct_markdown,
    validate_column_count,
)

from .__version__ import __version__
__all__ = [
    'analyze_section_frequency',
    'extract_h1_title',
    'extract_lead',
    'get_section_names',
    'load_markdown',
    'parse_frontmatter',
    'parse_h2_sections',
    'process_markdown_file',
    'reconstruct_markdown',
    'validate_column_count',
]

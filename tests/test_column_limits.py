"""Unit tests for column limit validation and top-N section extraction."""
import pytest
from pathlib import Path
from collections import Counter
import sqldown


class TestValidateColumnCount:
    """Test column limit validation functionality."""

    def test_validate_within_limit(self):
        """Validation should pass when columns are within limit."""
        docs = [
            {
                '_id': 'doc1',
                '_path': 'doc1.md',
                '_sections': '[]',
                'title': 'Doc 1',
                'body': 'Body',
                'lead': 'Lead',
                'file_modified': 123.45,
                'status': 'active',
                'section_notes': 'Notes'
            }
        ]

        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=100)

        assert is_valid is True
        assert total_cols == 9  # 7 base + 1 frontmatter + 1 section
        assert breakdown['base'] == 7
        assert breakdown['frontmatter'] == 1
        assert breakdown['sections'] == 1
        assert breakdown['total'] == 9

    def test_validate_exceeds_limit(self):
        """Validation should fail when columns exceed limit."""
        # Create document with many frontmatter fields and sections
        doc = {
            '_id': 'doc1',
            '_path': 'doc1.md',
            '_sections': '[]',
            'title': 'Doc',
            'body': 'Body',
            'lead': 'Lead',
            'file_modified': 123.45
        }

        # Add 20 frontmatter fields
        for i in range(20):
            doc[f'field_{i}'] = f'value_{i}'

        # Add 20 sections
        for i in range(20):
            doc[f'section_{i}'] = f'Section {i} content'

        docs = [doc]

        # With limit of 30, should exceed (7 base + 20 frontmatter + 20 sections = 47)
        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=30)

        assert is_valid is False
        assert total_cols == 47
        assert breakdown['base'] == 7
        assert breakdown['frontmatter'] == 20
        assert breakdown['sections'] == 20

    def test_validate_multiple_documents(self):
        """Validation should consider union of all columns across documents."""
        docs = [
            {
                '_id': 'doc1',
                '_path': 'doc1.md',
                '_sections': '[]',
                'title': 'Doc 1',
                'body': 'Body',
                'lead': 'Lead',
                'file_modified': 123.45,
                'status': 'active',
                'section_overview': 'Overview'
            },
            {
                '_id': 'doc2',
                '_path': 'doc2.md',
                '_sections': '[]',
                'title': 'Doc 2',
                'body': 'Body',
                'lead': 'Lead',
                'file_modified': 123.45,
                'priority': 'high',
                'section_notes': 'Notes'
            }
        ]

        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=100)

        # Should have: 7 base + 2 frontmatter (status, priority) + 2 sections (overview, notes)
        assert total_cols == 11
        assert breakdown['frontmatter'] == 2
        assert breakdown['sections'] == 2

    def test_validate_empty_docs(self):
        """Validation should handle empty document list."""
        is_valid, total_cols, breakdown = sqldown.validate_column_count([], max_columns=100)

        assert is_valid is True
        assert total_cols == 0
        assert breakdown == {}

    def test_validate_at_exact_limit(self):
        """Validation should pass when exactly at limit."""
        doc = {
            '_id': 'doc1',
            '_path': 'doc1.md',
            '_sections': '[]',
            'title': 'Doc',
            'body': 'Body',
            'lead': 'Lead',
            'file_modified': 123.45,
            'field1': 'value1',
            'field2': 'value2'
        }

        docs = [doc]

        # Exactly 9 columns (7 base + 2 frontmatter)
        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=9)

        assert is_valid is True
        assert total_cols == 9


class TestSectionFrequencyAnalysis:
    """Test top-N section extraction functionality."""

    def test_analyze_section_frequency(self, tmp_path):
        """Analyze section frequency across multiple files."""
        # Create test files with varying sections
        files = []

        # File 1: overview, notes
        f1 = tmp_path / "f1.md"
        f1.write_text("""# Doc 1

## Overview
Content

## Notes
Content
""")
        files.append(f1)

        # File 2: overview, implementation
        f2 = tmp_path / "f2.md"
        f2.write_text("""# Doc 2

## Overview
Content

## Implementation
Content
""")
        files.append(f2)

        # File 3: notes, testing
        f3 = tmp_path / "f3.md"
        f3.write_text("""# Doc 3

## Notes
Content

## Testing
Content
""")
        files.append(f3)

        # Analyze frequency, get top 2
        allowed_sections = sqldown.analyze_section_frequency(files, top_n=2)

        # Should return the 2 most common sections
        # overview: 2 occurrences, notes: 2 occurrences
        # implementation: 1, testing: 1
        assert len(allowed_sections) == 2
        assert 'overview' in allowed_sections or 'notes' in allowed_sections

    def test_analyze_returns_all_when_top_n_zero(self, tmp_path):
        """Should return all sections when top_n=0."""
        f1 = tmp_path / "f1.md"
        f1.write_text("""# Doc

## Section1
Content

## Section2
Content

## Section3
Content
""")

        allowed_sections = sqldown.analyze_section_frequency([f1], top_n=0)

        # top_n=0 means return all
        assert allowed_sections is None

    def test_analyze_with_duplicate_sections_in_file(self, tmp_path):
        """Each section should only count once per file."""
        # File with duplicate section names (unusual but possible in malformed docs)
        f1 = tmp_path / "f1.md"
        f1.write_text("""# Doc

## Notes
First notes

## Overview
Content

## Notes
More notes
""")

        # Should still work and count each section once per file
        allowed_sections = sqldown.analyze_section_frequency([f1], top_n=10)

        assert allowed_sections is not None
        assert 'notes' in allowed_sections
        assert 'overview' in allowed_sections

    def test_analyze_empty_file_list(self):
        """Handle empty file list gracefully."""
        allowed_sections = sqldown.analyze_section_frequency([], top_n=5)

        assert allowed_sections is None or len(allowed_sections) == 0

    def test_analyze_files_without_sections(self, tmp_path):
        """Handle files without H2 sections."""
        f1 = tmp_path / "nosections.md"
        f1.write_text("""# Doc

Just content, no sections.
""")

        allowed_sections = sqldown.analyze_section_frequency([f1], top_n=5)

        # Should return empty set or None
        assert allowed_sections is None or len(allowed_sections) == 0


class TestTopNSectionExtraction:
    """Test that top-N sections are properly extracted during processing."""

    def test_process_with_allowed_sections(self, tmp_path):
        """Process file with section filtering."""
        f1 = tmp_path / "test.md"
        f1.write_text("""---
status: active
---

# Test Doc

Lead paragraph.

## Overview
Keep this

## Notes
Keep this

## Rare Section
Filter this out
""")

        # Process with allowed sections
        allowed = {'overview', 'notes'}
        doc = sqldown.process_markdown_file(f1, tmp_path, allowed_sections=allowed)

        # Should have overview and notes
        assert 'section_overview' in doc
        assert 'section_notes' in doc

        # Should NOT have rare_section
        assert 'section_rare_section' not in doc

        # Body should still contain everything
        assert 'Rare Section' in doc['body']

    def test_process_without_allowed_sections(self, tmp_path):
        """Process file without section filtering (None means all)."""
        f1 = tmp_path / "test.md"
        f1.write_text("""# Test Doc

## Section1
Content

## Section2
Content

## Section3
Content
""")

        # Process without filtering
        doc = sqldown.process_markdown_file(f1, tmp_path, allowed_sections=None)

        # Should have all sections
        assert 'section_section1' in doc
        assert 'section_section2' in doc
        assert 'section_section3' in doc

    def test_process_with_empty_allowed_sections(self, tmp_path):
        """Process file with empty allowed set filters all sections."""
        f1 = tmp_path / "test.md"
        f1.write_text("""# Test Doc

## Section1
Content

## Section2
Content
""")

        # Process with empty set
        doc = sqldown.process_markdown_file(f1, tmp_path, allowed_sections=set())

        # Should NOT have any sections
        assert 'section_section1' not in doc
        assert 'section_section2' not in doc

        # But should still have other fields
        assert doc['title'] == 'Test Doc'
        assert 'Section1' in doc['body']


class TestColumnLimitScenarios:
    """Test real-world column limit scenarios."""

    def test_diverse_documents_exceed_limit(self, tmp_path):
        """Diverse documents with many unique fields should be caught."""
        # Create documents with different frontmatter and sections
        docs = []

        for i in range(100):
            doc = {
                '_id': f'doc{i}',
                '_path': f'doc{i}.md',
                '_sections': '[]',
                'title': f'Doc {i}',
                'body': 'Body',
                'lead': 'Lead',
                'file_modified': 123.45,
                f'field_{i}': f'value_{i}',  # Each doc has unique frontmatter
                f'section_{i}': f'Section {i}'  # Each doc has unique section
            }
            docs.append(doc)

        # Should massively exceed reasonable limit
        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=100)

        assert is_valid is False
        assert total_cols > 100
        assert breakdown['frontmatter'] == 100
        assert breakdown['sections'] == 100

    def test_uniform_documents_within_limit(self, tmp_path):
        """Uniform documents with same fields should stay within limit."""
        docs = []

        for i in range(1000):
            doc = {
                '_id': f'doc{i}',
                '_path': f'doc{i}.md',
                '_sections': '[]',
                'title': f'Doc {i}',
                'body': 'Body',
                'lead': 'Lead',
                'file_modified': 123.45,
                'status': 'active',  # Same frontmatter fields
                'project': 'test',
                'section_overview': 'Overview',  # Same sections
                'section_notes': 'Notes'
            }
            docs.append(doc)

        # Should be well within limit
        is_valid, total_cols, breakdown = sqldown.validate_column_count(docs, max_columns=100)

        assert is_valid is True
        assert total_cols == 11  # 7 base + 2 frontmatter + 2 sections

"""Unit tests for dump functionality and markdown reconstruction."""
import pytest
from pathlib import Path
import json
import sqldown
from sqlite_utils import Database


class TestReconstructMarkdown:
    """Test markdown reconstruction from database rows."""

    def test_reconstruct_basic_document(self):
        """Reconstruct document with frontmatter, title, and sections."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': json.dumps(['overview', 'notes']),
            'title': 'Test Document',
            'body': 'Full body text',
            'lead': 'This is the lead paragraph.',
            'status': 'active',
            'project': 'test',
            'section_overview': 'This is the overview section.',
            'section_notes': 'Some notes here.'
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Should have frontmatter
        assert '---' in markdown
        assert 'status: active' in markdown
        assert 'project: test' in markdown

        # Should have title
        assert '# Test Document' in markdown

        # Should have lead
        assert 'This is the lead paragraph.' in markdown

        # Should have sections
        assert '## Overview' in markdown
        assert 'This is the overview section.' in markdown
        assert '## Notes' in markdown
        assert 'Some notes here.' in markdown

    def test_reconstruct_without_frontmatter(self):
        """Reconstruct document without frontmatter fields."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': json.dumps([]),
            'title': 'Simple Document',
            'body': 'Body text',
            'lead': 'Lead paragraph.'
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Should not have frontmatter
        assert not markdown.startswith('---')

        # Should have title and lead
        assert '# Simple Document' in markdown
        assert 'Lead paragraph.' in markdown

    def test_reconstruct_without_lead(self):
        """Reconstruct document without lead paragraph."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': json.dumps(['notes']),
            'title': 'No Lead Document',
            'body': 'Body text',
            'lead': None,
            'section_notes': 'Just notes.'
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Should have title directly followed by section
        assert '# No Lead Document' in markdown
        assert '## Notes' in markdown
        assert 'Just notes.' in markdown

    def test_reconstruct_section_order(self):
        """Sections should appear in order specified by _sections."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': json.dumps(['conclusion', 'introduction', 'analysis']),
            'title': 'Ordered Document',
            'body': 'Body',
            'section_introduction': 'Intro text',
            'section_analysis': 'Analysis text',
            'section_conclusion': 'Conclusion text'
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Find positions of each section
        conclusion_pos = markdown.find('## Conclusion')
        intro_pos = markdown.find('## Introduction')
        analysis_pos = markdown.find('## Analysis')

        # Should appear in the order: conclusion, introduction, analysis
        assert conclusion_pos < intro_pos < analysis_pos

    def test_reconstruct_section_name_conversion(self):
        """Section names should be converted back to title case."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': json.dumps(['implementation_plan', 'next_steps']),
            'title': 'Test',
            'body': 'Body',
            'section_implementation_plan': 'Plan details',
            'section_next_steps': 'Steps to take'
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Underscores should be converted to spaces and title-cased
        assert '## Implementation Plan' in markdown
        assert '## Next Steps' in markdown

    def test_reconstruct_with_none_values(self):
        """Handle None values in row gracefully."""
        row = {
            '_id': 'test123',
            '_path': 'test.md',
            '_sections': None,
            'title': 'Test',
            'body': None,
            'lead': None,
            'status': None
        }

        markdown = sqldown.reconstruct_markdown(row)

        # Should still produce valid markdown
        assert '# Test' in markdown
        assert markdown.endswith('\n')


class TestRoundTrip:
    """Test complete round-trip: markdown → database → markdown."""

    def test_roundtrip_basic_document(self, tmp_path):
        """Document should be identical after load → dump cycle."""
        # Create original markdown
        original_md = tmp_path / "original.md"
        original_content = """---
status: active
project: test
---

# Test Document

This is the lead paragraph.

## Overview
This is the overview.

## Notes
Some notes here.
"""
        original_md.write_text(original_content)

        # Process and load into database
        doc = sqldown.process_markdown_file(original_md, tmp_path)

        # Reconstruct markdown
        reconstructed = sqldown.reconstruct_markdown(doc)

        # Should match original
        assert reconstructed == original_content

    def test_roundtrip_complex_frontmatter(self, tmp_path):
        """Handle complex frontmatter values in round-trip."""
        original_md = tmp_path / "complex.md"
        original_content = """---
status: active
priority: high
tags:
- python
- testing
count: 42
---

# Complex Document

Lead paragraph.

## Section
Content.
"""
        original_md.write_text(original_content)

        # Process and load into database
        doc = sqldown.process_markdown_file(original_md, tmp_path)

        # Reconstruct markdown
        reconstructed = sqldown.reconstruct_markdown(doc)

        # Parse both to compare structures
        orig_fm, _ = sqldown.parse_frontmatter(original_content)
        recon_fm, _ = sqldown.parse_frontmatter(reconstructed)

        # Frontmatter should match
        assert orig_fm == recon_fm

    def test_roundtrip_without_sections(self, tmp_path):
        """Handle documents without H2 sections."""
        original_md = tmp_path / "nosections.md"
        original_content = """---
status: draft
---

# Simple Document

Just a lead paragraph, no sections.
"""
        original_md.write_text(original_content)

        doc = sqldown.process_markdown_file(original_md, tmp_path)
        reconstructed = sqldown.reconstruct_markdown(doc)

        assert '# Simple Document' in reconstructed
        assert 'Just a lead paragraph' in reconstructed
        assert '##' not in reconstructed


class TestDumpIntegration:
    """Integration tests for the dump command functionality."""

    def test_dump_creates_files(self, tmp_path):
        """Dump command should create markdown files from database."""
        # Create test database
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        # Insert test document
        doc = {
            '_id': 'abc123',
            '_path': 'test/doc.md',
            '_sections': json.dumps(['notes']),
            'title': 'Test Doc',
            'body': 'Body',
            'lead': 'Lead text',
            'status': 'active',
            'section_notes': 'Notes content'
        }
        db['docs'].insert(doc)

        # Reconstruct and verify
        markdown = sqldown.reconstruct_markdown(doc)

        assert '# Test Doc' in markdown
        assert 'Lead text' in markdown
        assert '## Notes' in markdown
        assert 'Notes content' in markdown

    def test_dump_preserves_structure(self, tmp_path):
        """Dump should preserve directory structure from _path."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        # Insert documents with different paths
        docs = [
            {
                '_id': 'doc1',
                '_path': 'folder1/doc1.md',
                'title': 'Doc 1',
                'body': 'Body 1',
                '_sections': '[]'
            },
            {
                '_id': 'doc2',
                '_path': 'folder2/subfolder/doc2.md',
                'title': 'Doc 2',
                'body': 'Body 2',
                '_sections': '[]'
            }
        ]

        for doc in docs:
            db['docs'].insert(doc)
            markdown = sqldown.reconstruct_markdown(doc)
            assert f"# {doc['title']}" in markdown

    def test_dump_skip_unchanged(self, tmp_path):
        """Dump should detect and skip unchanged files."""
        # Create a markdown file
        output_file = tmp_path / "existing.md"
        content = """---
status: active
---

# Existing Doc

Content here.
"""
        output_file.write_text(content)

        # Create matching database row
        doc = {
            '_id': 'test123',
            '_path': 'existing.md',
            '_sections': json.dumps([]),
            'title': 'Existing Doc',
            'body': content,
            'lead': 'Content here.',
            'status': 'active'
        }

        # Reconstruct should produce identical content
        reconstructed = sqldown.reconstruct_markdown(doc)

        # Content should match
        assert reconstructed == content

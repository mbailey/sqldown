"""Unit tests for markdown parsing functions."""
import pytest
from pathlib import Path
import sqldown


class TestFrontmatterParsing:
    """Test YAML frontmatter extraction."""

    def test_parse_frontmatter_with_valid_yaml(self):
        """Parse valid YAML frontmatter."""
        content = """---
status: active
project: test
priority: high
---

# Test Document

Content here.
"""
        frontmatter, body = sqldown.parse_frontmatter(content)

        assert frontmatter == {'status': 'active', 'project': 'test', 'priority': 'high'}
        assert body.startswith('# Test Document')

    def test_parse_frontmatter_without_yaml(self):
        """Handle documents without frontmatter."""
        content = """# Test Document

No frontmatter here.
"""
        frontmatter, body = sqldown.parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content

    def test_parse_frontmatter_with_empty_yaml(self):
        """Handle empty YAML frontmatter."""
        content = """---
---

# Test Document
"""
        frontmatter, body = sqldown.parse_frontmatter(content)

        assert frontmatter == {}
        assert body.startswith('# Test Document')

    def test_parse_frontmatter_with_invalid_yaml(self):
        """Handle invalid YAML gracefully."""
        content = """---
invalid: yaml: syntax:
---

# Test Document
"""
        frontmatter, body = sqldown.parse_frontmatter(content)

        # Should return empty dict for invalid YAML
        assert frontmatter == {}


class TestH1Extraction:
    """Test H1 title extraction."""

    def test_extract_h1_title(self):
        """Extract H1 heading as title."""
        content = """# My Title

Content here.
"""
        title = sqldown.extract_h1_title(content)
        assert title == "My Title"

    def test_extract_h1_with_leading_content(self):
        """Extract H1 even with preceding content."""
        content = """Some intro text

# My Title

Content here.
"""
        title = sqldown.extract_h1_title(content)
        assert title == "My Title"

    def test_extract_h1_no_title(self):
        """Return None when no H1 exists."""
        content = """## H2 Header

Content without H1.
"""
        title = sqldown.extract_h1_title(content)
        assert title is None


class TestLeadExtraction:
    """Test lead paragraph extraction."""

    def test_extract_lead_basic(self):
        """Extract content between H1 and first H2."""
        content = """# Title

This is the lead paragraph.
It spans multiple lines.

## First Section

Section content.
"""
        lead = sqldown.extract_lead(content)
        assert "lead paragraph" in lead
        assert "multiple lines" in lead
        assert "Section content" not in lead

    def test_extract_lead_no_h2(self):
        """Extract all content after H1 when no H2 exists."""
        content = """# Title

All of this is the lead.
"""
        lead = sqldown.extract_lead(content)
        assert "All of this is the lead" in lead


class TestH2SectionParsing:
    """Test H2 section extraction."""

    def test_parse_h2_sections(self):
        """Parse multiple H2 sections."""
        content = """# Title

Lead content.

## Objective

The objective section.

## Implementation Plan

1. Step one
2. Step two

## Notes

Final notes.
"""
        sections = sqldown.parse_h2_sections(content)

        assert 'objective' in sections
        assert 'implementation_plan' in sections
        assert 'notes' in sections
        assert "objective section" in sections['objective']
        assert "Step one" in sections['implementation_plan']

    def test_section_name_normalization(self):
        """Normalize H2 section names properly."""
        content = """# Title

## Complex Section-Name (With) Special!!!

Content.
"""
        sections = sqldown.parse_h2_sections(content)

        # Should normalize to snake_case, remove special chars
        assert 'complex_section_name_with_special' in sections

    def test_empty_sections(self):
        """Handle sections with no content."""
        content = """# Title

## Section One

## Section Two

Content for section two.
"""
        sections = sqldown.parse_h2_sections(content)

        assert 'section_one' in sections
        assert sections['section_one'] == ''
        assert 'section_two' in sections
        assert sections['section_two'] != ''


class TestDocumentProcessing:
    """Test full document processing."""

    def test_process_markdown_file(self, tmp_path):
        """Process a complete markdown file."""
        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
status: active
project: test
---

# Test Document

This is the lead.

## Objective

The goal here.

## Notes

Some notes.
""")

        doc = sqldown.process_markdown_file(test_file, tmp_path)

        # Check core fields
        assert doc['_id']
        assert doc['_path'] == 'test.md'
        assert doc['title'] == 'Test Document'
        assert doc['body']
        assert 'lead' in doc['lead'].lower()

        # Check frontmatter
        assert doc['status'] == 'active'
        assert doc['project'] == 'test'

        # Check sections
        assert doc['section_objective']
        assert 'goal' in doc['section_objective'].lower()
        assert doc['section_notes']

        # Check _sections order
        assert doc['_sections'] == ['objective', 'notes']

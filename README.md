# ☠️ SQLDown - pre-alpha - USE AT OWN RISK

[![PyPI version](https://badge.fury.io/py/sqldown.svg)](https://pypi.org/project/sqldown/)
[![Python versions](https://img.shields.io/pypi/pyversions/sqldown.svg)](https://pypi.org/project/sqldown/)
[![CI/CD](https://github.com/mbailey/sqldown/actions/workflows/ci.yml/badge.svg)](https://github.com/mbailey/sqldown/actions)

**Bidirectional markdown ↔ SQLite conversion** - Load markdown files into SQLite, query with SQL, and export back to markdown.

## Features

☠️ **Pre-Alpha Software (v0.1.0) - USE AT YOUR OWN RISK:**
- Dynamic schema generation from YAML frontmatter and markdown structure
- Column limit protection with intelligent section extraction
- Import markdown collections into queryable SQLite databases
- Export database rows back to markdown files
- Watch mode for auto-refresh on file changes
- Gitignore-aware file filtering
- Smart change detection (skip unchanged files)

## Installation

```bash
# Install from PyPI
pip install sqldown

# Or use uv for faster installation
uv pip install sqldown
```

## Quick Start

```bash
# Load markdown files into SQLite
sqldown load ~/tasks

# Query with sqlite3
sqlite3 sqldown.db "SELECT * FROM docs WHERE status='active'"

# Export back to markdown
sqldown dump -d sqldown.db -o ~/restored

# Get database info
sqldown info

# Show table details
sqldown info -t docs
```

## Load Command

```bash
sqldown load PATH [OPTIONS]
```

**What it does:**
- Scans markdown files recursively
- Parses YAML frontmatter → database columns
- Extracts H2 sections → `section_*` columns
- Creates schema dynamically based on discovered fields
- Upserts into SQLite (idempotent - safe to run multiple times)
- Respects `.gitignore` patterns automatically

**Options:**
- `-d, --db PATH` - Database file (default: `sqldown.db`)
- `-t, --table NAME` - Table name (default: `docs`)
- `-p, --pattern GLOB` - File pattern (default: `**/*.md`)
- `--max-columns N` - Maximum allowed columns (default: 1800, SQLite limit: 2000)
- `--top-sections N` - Extract only top N most common sections (default: 20, 0=all)
- `-w, --watch` - Watch for file changes and auto-update
- `-v, --verbose` - Show detailed progress

## Dump Command

```bash
sqldown dump -d DATABASE -o OUTPUT_DIR [OPTIONS]
```

**What it does:**
- Exports database rows back to markdown files
- Reconstructs original markdown structure with frontmatter
- Preserves file paths from original import
- Skips unchanged files (smart change detection)
- Supports SQL filtering to export subsets

**Options:**
- `-d, --db PATH` - Database file (required)
- `-t, --table NAME` - Table name (default: `docs`)
- `-o, --output PATH` - Output directory (required)
- `-f, --filter WHERE` - SQL WHERE clause to filter rows
- `--force` - Always write files, even if unchanged
- `--dry-run` - Preview what would be exported without writing
- `-v, --verbose` - Show detailed progress

**Examples:**
```bash
# Export all documents
sqldown dump -d cache.db -o ~/restored

# Export only active tasks
sqldown dump -d cache.db -t tasks -o ~/active --filter "status='active'"

# Preview export without writing files
sqldown dump -d cache.db -o ~/export --dry-run
```

## Info Command

```bash
sqldown info [OPTIONS]
```

**What it does:**
- Shows database statistics and table information
- Lists all tables with document counts
- Displays column breakdown (frontmatter vs sections)
- Provides schema details for specific tables

**Options:**
- `-d, --db PATH` - Database file (default: `sqldown.db` if exists)
- `-t, --table NAME` - Show detailed info for specific table

**Examples:**
```bash
# Show database overview (uses sqldown.db if present)
sqldown info

# Show info for specific database
sqldown info -d cache.db

# Show detailed table information
sqldown info -t tasks
```

## Using SQLite3

Once imported, use sqlite3 directly for all queries:

```bash
# List tables
sqlite3 cache.db ".tables"

# Show schema
sqlite3 cache.db ".schema tasks"

# Query
sqlite3 cache.db "SELECT title, status FROM tasks WHERE status='active' LIMIT 10"

# Aggregate
sqlite3 cache.db "SELECT status, COUNT(*) FROM tasks GROUP BY status"

# Complex queries
sqlite3 cache.db "
  SELECT project, COUNT(*) as active_count
  FROM tasks
  WHERE status='active'
  GROUP BY project
  ORDER BY active_count DESC
"

# Export to CSV
sqlite3 -csv cache.db "SELECT * FROM tasks WHERE status='active'" > active.csv

# Interactive mode
sqlite3 cache.db
```

## Dynamic Schema Example

From this markdown:
```markdown
---
status: active
project: agents
priority: high
---

# Add SQLite caching

## Objective
Create a cache layer...

## Implementation Plan
1. Parser
2. Schema
```

Creates these columns automatically:
- Core: `_id`, `_path`, `_sections`, `title`, `body`, `lead`, `file_modified`
- Frontmatter: `status`, `project`, `priority`
- Sections: `section_objective`, `section_implementation_plan`

**Real example:** 87 tasks → 181 columns (no schema design needed!)

## Column Limit Protection

SQLite has a hard limit of 2000 columns per table. With diverse markdown documents, you can easily hit this limit:

**Problem:** 5,225 tasks with diverse sections = 6,694 columns (💥 exceeds limit!)

**Solution:** Use `--top-sections` to extract only the most common sections:

```bash
# Extract only top 20 most common sections (default)
sqldown load ~/tasks -d cache.db --top-sections 20

# Result: 5,225 tasks → 116 columns ✅
# - 7 base columns (_id, _path, title, body, lead, _sections, file_modified)
# - 89 frontmatter columns (status, project, type, priority, etc.)
# - 20 section columns (overview, usage, objective, notes, next_steps, etc.)
```

**What happens to other sections?**
- All content is preserved in the `body` field
- You can still search across all sections using SQLite FTS5
- Only the top N sections become queryable columns

**Column limit validation:**
```bash
# Check if your documents will fit before importing
sqldown load ~/docs -d test.db --verbose

# Output shows breakdown:
# 📊 Column breakdown:
#   - Base columns: 7
#   - Frontmatter columns: 89
#   - Section columns: 20
#   - Total: 116 (limit: 1800)
```

**When approaching limit (>90%):**
- Shows warning but continues import
- Consider: reducing --top-sections or increasing --max-columns

**When exceeding limit:**
- Stops before import to prevent database corruption
- Shows breakdown and suggestions

## Multiple Collections

One database, multiple tables:

```bash
# Import different document types
sqldown load ~/tasks -d cache.db -t tasks
sqldown load ~/notes -d cache.db -t notes
sqldown load ~/.claude/skills -d cache.db -t skills

# Query them
sqlite3 cache.db "SELECT * FROM tasks WHERE status='active'"
sqlite3 cache.db "SELECT * FROM notes WHERE tags LIKE '%sqlite%'"

# Join across tables
sqlite3 cache.db "
  SELECT t.title as task, n.title as note
  FROM tasks t
  JOIN notes n ON n.tags LIKE '%' || t.project || '%'
  WHERE t.status='active'
"
```

## Refresh Strategy

**One-time import:**

Import is idempotent - just run it again:

```bash
# Add this to cron or a git hook
sqldown load ~/tasks -d cache.db -t tasks
```

**Watch mode (auto-refresh):**

Use the `--watch` / `-w` flag to automatically update the cache when files change:

```bash
# Watch mode: import once, then auto-update on file changes
sqldown load ~/tasks -d cache.db -t tasks --watch

# Output:
# ✅ Imported 87 documents into cache.db:tasks
# 📋 Schema has 181 columns
#
# 👀 Watching /Users/admin/tasks for changes... (Ctrl-C to stop)
# [2025-01-15 10:23:45] Updated: AG-22_feat_add-configuration/README.md
# [2025-01-15 10:24:12] Added: AG-31_feat_new-feature/README.md
```

Watch mode is ideal for development workflows where you want the cache to stay in sync with your files.

## Common Queries

```bash
# Active tasks
sqlite3 cache.db "SELECT title FROM tasks WHERE status='active'"

# Recent updates
sqlite3 cache.db "SELECT title, updated FROM tasks ORDER BY updated DESC LIMIT 10"

# By project
sqlite3 cache.db "SELECT project, COUNT(*) FROM tasks GROUP BY project"

# Search content
sqlite3 cache.db "SELECT title FROM tasks WHERE body LIKE '%cache%'"

# High priority incomplete
sqlite3 cache.db "SELECT title FROM tasks WHERE priority='high' AND status != 'completed'"
```

## Philosophy

SQLDown follows the Unix philosophy: do one thing well.

- **Load**: SQLDown handles the complex markdown → SQLite conversion
- **Query**: sqlite3 provides perfect SQL interface (no wrapper needed)
- **Dump**: SQLDown reconstructs markdown from database rows

Why not wrap sqlite3? Because it's already perfect for queries:
- Full SQL power without wrapper limitations
- Standard tool with excellent documentation
- Multiple output formats (CSV, JSON, column, etc.)
- Interactive shell with history and completion
- Zero overhead for read operations

## Requirements

- Python 3.8+ (includes sqlite3 module)
- sqlite3 CLI (built-in on macOS/Linux)

**Python Dependencies** (installed automatically):
- click >= 8.0 - CLI framework
- sqlite-utils >= 3.30 - SQLite schema management
- PyYAML >= 6.0 - YAML frontmatter parsing
- pathspec >= 0.11 - Gitignore pattern support
- watchdog >= 3.0 - File system monitoring

## Integration

SQLDown is designed for both human and AI use:

**For Developers:**
- Simple CLI with sensible defaults
- Watch mode for development workflows
- Smart change detection saves time
- Direct sqlite3 access for queries

**For AI Assistants:**
- Efficient token usage via SQL queries
- Progressive disclosure pattern
- Query metadata first, read files only when needed
- Structured data extraction from markdown

## Contributing

Contributions welcome! Please check out the [issues](https://github.com/mbailey/sqldown/issues) on GitHub.

## License

MIT

## Changelog

### v0.1.0 (2025-01-14)

**Initial PyPI Release** 🎉

- Full bidirectional markdown ↔ SQLite conversion
- Dynamic schema generation from YAML frontmatter
- Intelligent column limit protection (SQLite 2000 column limit)
- Top-N section extraction for diverse document collections
- Watch mode for automatic file sync
- Smart change detection on export
- Comprehensive CLI with `load`, `dump`, and `info` commands
- Python 3.8+ support

### Development History

See [SPECIFICATION.md](SPECIFICATION.md) for the complete design.
See [REVIEW.md](REVIEW.md) for architectural decisions and trade-offs.

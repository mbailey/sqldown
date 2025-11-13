---
name: sqldown
description: Bidirectional markdown ↔ SQLite conversion with column limit protection and smart section extraction. Import with Python, query with sqlite3.
---

# SQLDown Skill

## Core Concept

**Import with Python. Query with sqlite3. Dump when needed.**

This skill handles bidirectional markdown ↔ SQLite conversion with intelligent column limit protection. For queries, use `sqlite3` directly - it's already perfect.

## When to Use

- Need to query across many markdown files efficiently
- Want SQL-powered filtering, aggregation, sorting
- Working with structured markdown (YAML frontmatter + H2 sections)
- Need context-efficient progressive disclosure

## Commands

### Import: Create or Update Tables

Use `md-import` - a uv single-file script with inline dependencies.

**After metool installation:**
```bash
md-import --db cache.db --table TABLE --root PATH [OPTIONS]
```

**Before installation or for direct execution:**
```bash
/path/to/markdown-cache/bin/md-import --db cache.db --table TABLE --root PATH [OPTIONS]
```

**What it does:**
- Parses YAML frontmatter → database columns
- Extracts H2 sections → `section_*` columns
- Generates schema dynamically based on discovered fields
- Respects .gitignore automatically (disable with `--no-gitignore`)
- Upserts (idempotent - safe to run multiple times)

**Options:**
- `--db PATH` - Database file (default: cache.db)
- `--table NAME` - Table name (default: docs)
- `--root PATH` - Root directory with markdown files
- `--pattern GLOB` - File pattern (default: **/*.md)
- `--max-columns N` - Maximum allowed columns (default: 1800, SQLite limit: 2000)
- `--top-sections N` - Extract only top N most common sections (default: 20, 0=all)
- `--exclude PATTERN` - Additional exclusions beyond .gitignore (can use multiple times)
- `--no-gitignore` - Disable automatic .gitignore filtering
- `--watch, -w` - Watch for file changes and auto-update (stays running until Ctrl-C)
- `--verbose, -v` - Show detailed progress including column breakdown

**Examples (using command after metool install):**
```bash
# Import tasks (respects .gitignore automatically)
md-import --db ~/cache.db --table tasks --root ~/tasks

# Import notes
md-import --db ~/cache.db --table notes --root ~/notes

# Import skills with pattern
md-import --db ~/cache.db --table skills --root ~/.claude/skills --pattern "*/SKILL.md"

# Import without gitignore filtering
md-import --db ~/cache.db --table all_docs --root ~/docs --no-gitignore

# Additional exclusions
md-import --db ~/cache.db --table tasks --root ~/tasks --exclude '**/test/**'

# Watch mode: auto-update on file changes
md-import --db ~/cache.db --table tasks --root ~/tasks --watch

# Column limit protection - extract only top 20 sections (default)
md-import --db ~/cache.db --table tasks --root ~/tasks

# Extract top 10 sections (fewer columns)
md-import --db ~/cache.db --table tasks --root ~/tasks --top-sections 10

# Extract all sections (may hit 2000 column limit with diverse docs)
md-import --db ~/cache.db --table tasks --root ~/tasks --top-sections 0

# Check column breakdown before import
md-import --db ~/cache.db --table tasks --root ~/tasks --verbose
# Output shows: Base columns: 7, Frontmatter: 89, Sections: 20, Total: 116
```

**For direct execution before metool install:**
```bash
# Direct path to script
/path/to/markdown-cache/bin/md-import --db ~/cache.db --table tasks --root ~/tasks

# With watch mode
/path/to/markdown-cache/bin/md-import --db ~/cache.db --table tasks --root ~/tasks --watch
```

### Query: Use sqlite3 Directly

For ALL queries, use `sqlite3` command directly:

```bash
# List available tables
sqlite3 cache.db ".tables"

# Show table schema
sqlite3 cache.db ".schema tasks"

# Query
sqlite3 cache.db "SELECT title, status FROM tasks WHERE status='active'"

# Aggregate
sqlite3 cache.db "SELECT status, COUNT(*) FROM tasks GROUP BY status"

# Complex queries
sqlite3 cache.db "
  SELECT project, COUNT(*) as count,
         SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active
  FROM tasks
  GROUP BY project
  ORDER BY count DESC
"
```

## Dynamic Schema

**Core fields** (always present):
```sql
_id TEXT PRIMARY KEY        -- SHA1 of file path
_path TEXT                   -- Relative path
_sections TEXT               -- JSON array of H2 names
title TEXT                   -- H1 heading
body TEXT                    -- Full content
lead TEXT                    -- First paragraph
file_modified FLOAT          -- Timestamp
```

**Dynamic fields** (auto-generated):
- YAML frontmatter: `status`, `project`, `priority`, `tags`, etc.
- H2 sections: `section_objective`, `section_implementation_plan`, etc.

**Example:** 87 tasks with varied structure → 181 columns generated automatically.

## Column Limit Protection

SQLite has a hard limit of 2000 columns per table. The `--top-sections` flag prevents hitting this limit:

**How it works:**
1. Analyzes all documents to count section frequency
2. Extracts only the N most common sections as columns
3. All other sections remain in the `body` field

**Real-world example:**
- 5,225 tasks with diverse sections = 6,694 unique columns (exceeds limit!)
- With `--top-sections 20` (default) = 116 columns ✅

**Top extracted sections (from Mike's tasks):**
`overview`, `usage`, `objective`, `notes`, `next_steps`, `troubleshooting`, `installation`, `configuration`, `requirements`, `testing`, etc.

**When to adjust:**
- `--top-sections 10` - Fewer columns for very diverse collections
- `--top-sections 50` - More columns if you need more queryable sections
- `--top-sections 0` - Extract all (only for homogeneous collections)

**What about rare sections?**
- Still in `body` field - nothing is lost
- Use FTS5 or `LIKE '%text%'` to search across all content
- Only the top N become directly queryable columns

## Common Query Patterns

```bash
# Find active tasks
sqlite3 cache.db "SELECT title FROM tasks WHERE status='active'"

# Recent updates
sqlite3 cache.db "SELECT title, updated FROM tasks ORDER BY updated DESC LIMIT 10"

# Count by status
sqlite3 cache.db "SELECT status, COUNT(*) FROM tasks GROUP BY status"

# Search content
sqlite3 cache.db "SELECT title, _path FROM tasks WHERE body LIKE '%SQLite%'"

# High priority items
sqlite3 cache.db "SELECT title FROM tasks WHERE priority='high' AND status!='completed'"

# Project summary
sqlite3 cache.db "
  SELECT project,
         COUNT(*) as total,
         SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done
  FROM tasks
  GROUP BY project
"

# Find related documents
sqlite3 cache.db "
  SELECT title FROM tasks
  WHERE section_related_tasks LIKE '%AG-22%'
"
```

## Progressive Disclosure Pattern

1. **Query metadata first** (fast, context-efficient):
   ```bash
   sqlite3 cache.db "SELECT title, _path, status FROM tasks WHERE priority='high'"
   ```

2. **Read full markdown only when needed** (slower, more context):
   ```bash
   # After finding relevant tasks, read the actual files
   cat ~/tasks/AG-22_feat_add-configuration/README.md
   ```

This keeps context usage low while still finding what you need.

## Multiple Tables Strategy

Keep different document types in separate tables:

```bash
# Import each type
md-import --db ~/cache.db --table tasks --root ~/tasks
md-import --db ~/cache.db --table notes --root ~/notes
md-import --db ~/cache.db --table skills --root ~/.claude/skills

# Query across them
sqlite3 ~/cache.db "
  SELECT 'task' as type, title FROM tasks WHERE body LIKE '%cache%'
  UNION ALL
  SELECT 'note' as type, title FROM notes WHERE body LIKE '%cache%'
"
```

## Refresh Strategy

**One-time import (manual refresh):**

Import is idempotent - run after file changes:

```bash
md-import --db ~/cache.db --table tasks --root ~/tasks --verbose
```

**Watch mode (automatic refresh):**

Use `--watch` to automatically update when files change:

```bash
# Starts watching - runs until Ctrl-C
md-import --db ~/cache.db --table tasks --root ~/tasks --watch

# Output shows real-time updates:
# [2025-01-15 10:23:45] Updated: AG-22_feat_add-configuration/README.md
# [2025-01-15 10:24:12] Added: AG-31_feat_new-feature/README.md
# [2025-01-15 10:25:03] Deleted: AG-19_feat_old-feature/README.md
```

Watch mode is ideal for development workflows where you want the cache to stay in sync as you edit files.

## Why sqlite3 Instead of Python Wrappers?

**sqlite3 gives you:**
- Full SQL power (no wrapper limitations)
- Standard tool (no custom command syntax to learn)
- Better output formats (`.mode csv`, `.mode json`, `.mode column`)
- Interactive shell with history and tab completion
- Better performance (no Python startup overhead)

**uv script (md-import) gives you:**
- Markdown + YAML frontmatter parsing
- Dynamic schema generation
- H2 section extraction
- Automatic .gitignore filtering
- Inline dependencies (no pip install needed)

This division of responsibility keeps tools simple and powerful.

## Workflow Guidelines

1. **Start with schema inspection:**
   ```bash
   sqlite3 cache.db ".schema tasks"
   ```
   Shows what columns are available (critical for dynamic schemas).

2. **Use simple queries first:**
   ```bash
   sqlite3 cache.db "SELECT title, status FROM tasks LIMIT 5"
   ```

3. **Build up complexity:**
   ```bash
   sqlite3 cache.db "SELECT status, COUNT(*) FROM tasks GROUP BY status"
   ```

4. **Read full files last:**
   Only after identifying relevant documents via SQL.

5. **Trust .gitignore filtering:**
   By default, md-import respects .gitignore. Use `--no-gitignore` only when explicitly needed.

## Requirements

**Prerequisites:**
- Python 3.7+ (includes sqlite3 module - standard library)
- sqlite3 CLI (built-in on macOS 10.4+ and most Linux distributions)
- [uv](https://github.com/astral-sh/uv) - Python package installer and runner

**Dependencies (handled automatically by uv):**

The `md-import` script uses uv's inline dependency specification. Dependencies are automatically installed on first run and cached for subsequent runs:
- sqlite-utils >= 3.30 (dynamic schema generation)
- click >= 8.0 (CLI interface)
- PyYAML >= 6.0 (YAML frontmatter parsing)
- pathspec >= 0.11.0 (gitignore filtering)

No manual pip install or virtual environment setup needed!

## Limitations

- Manual refresh (no auto file-watching)
- Best for <100K documents
- SQLite column limit: 2000 columns max (md-import detects and reports)
- No built-in full-text search (though SQLite FTS5 could be added)

## Future Ideas

- Auto-refresh on file changes
- FTS5 full-text search indexes
- Graph queries for linked documents
- Embedding-based semantic search

## Technical Details

**uv Single-File Script:**
- `md-import` uses uv's inline dependency specification
- Dependencies declared in script header (sqlite-utils, click, pyyaml, pathspec)
- No separate requirements.txt or virtual environment needed
- First run: uv automatically installs dependencies
- Subsequent runs: cached dependencies load instantly

**Automatic .gitignore Support:**
- Reads .gitignore from root directory by default
- Uses pathspec library for gitignore pattern matching
- Filters files before import to avoid unwanted content
- Override with `--no-gitignore` when needed

## Related Files

- `bin/md-import` - uv single-file script (the import tool)
- `README.md` - Human-facing documentation

# SQLDown

**Bidirectional markdown ↔ SQLite conversion** - Load, query, and dump with ease.

## Status

✅ **MVP Features Implemented:**
- ✅ Column limit validation with `--max-columns` flag
- ✅ Top-N section extraction with `--top-sections` flag
- ✅ Import with dynamic schema generation
- ✅ Watch mode for auto-refresh
- 🚧 Dump command (planned)
- 🚧 Info command (planned)

See [SPECIFICATION.md](SPECIFICATION.md) for the complete v0.1 design.
See [REVIEW.md](REVIEW.md) for Papa Bear's detailed design review.

## Philosophy

- **Bidirectional**: Load markdown → SQLite, dump SQLite → markdown
- **Simple**: Use sqlite3 for queries, Python for parsing
- **Smart**: Dynamic schema, path-aware dumps, change detection
- **Database as authority**: Enforces schema consistency

## Quick Start (Future v0.1)

```bash
# Load markdown files into database
sqldown load ~/tasks

# Query with sqlite3
sqlite3 sqldown.db "SELECT * FROM docs WHERE status='active'"

# Dump back to markdown
sqldown dump -d sqldown.db -o ~/restored

# Get info
sqldown info -d sqldown.db
```

## Import Command

```bash
python3 bin/import.py --db DATABASE --table TABLE --root PATH [OPTIONS]
```

**What it does:**
- Scans markdown files recursively
- Parses YAML frontmatter → columns
- Extracts H2 sections → `section_*` columns
- **Creates schema dynamically** based on discovered fields
- Upserts into SQLite (idempotent - run multiple times safely)

**Options:**
- `--db PATH` - Database file (creates if doesn't exist)
- `--table NAME` - Table name (default: `docs`)
- `--root PATH` - Directory containing markdown files
- `--pattern GLOB` - File pattern (default: `**/*.md`)
- `--max-columns N` - Maximum allowed columns (default: 1800, SQLite limit: 2000)
- `--top-sections N` - Extract only top N most common sections (default: 20, 0=all)
- `--watch, -w` - Watch for file changes and auto-update
- `--verbose, -v` - Show progress

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
python3 bin/import.py --db cache.db --root ~/tasks --top-sections 20

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
python3 bin/import.py --db test.db --root ~/docs --verbose

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
python3 bin/import.py --db cache.db --table tasks --root ~/tasks
python3 bin/import.py --db cache.db --table notes --root ~/notes
python3 bin/import.py --db cache.db --table skills --root ~/.claude/skills

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
python3 bin/import.py --db cache.db --table tasks --root ~/tasks
```

**Watch mode (auto-refresh):**

Use the `--watch` / `-w` flag to automatically update the cache when files change:

```bash
# Watch mode: import once, then auto-update on file changes
md-import --db cache.db --table tasks --root ~/tasks --watch

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

## Why Not Use query.py?

You could! But `sqlite3` gives you:
- Full SQL power (no wrapper limitations)
- Standard tool everyone knows
- CSV export, JSON mode, etc.
- Interactive shell with history
- Better performance (no Python overhead)

The import tool adds value (markdown parsing). Query wrappers don't.

## Requirements

**Prerequisites:**
- Python 3.7+ (includes sqlite3 module - standard library)
- sqlite3 CLI (built-in on macOS 10.4+ and most Linux distributions)
- [uv](https://github.com/astral-sh/uv) - Python package installer and runner

**Dependencies (handled automatically by uv):**

The `md-import` script uses uv's inline dependency specification, so dependencies are automatically installed on first run:
- sqlite-utils >= 3.30
- click >= 8.0
- PyYAML >= 6.0
- pathspec >= 0.11.0

No manual pip install or virtual environment setup needed!

## Claude Code Integration

The SKILL.md file teaches Claude to:
1. Use `bin/import.py` to create/refresh caches
2. Use `sqlite3` for all queries
3. Start with simple queries, then get complex if needed
4. Read full markdown files only when necessary (progressive disclosure)

## License

MIT

---

## Development Log

### 2025-01-13 - Design Session: Python Package Specification

**Session Goals:**
- Design conversion from uv single-file script to proper Python package
- Plan bidirectional markdown ↔ SQLite workflow
- Define CLI interface and conventions

**Key Decisions:**

1. **Package Structure:**
   - PyPI name: `sqldown`
   - CLI commands: `load`, `dump`, `info`
   - Modern packaging with `pyproject.toml` and `src/` layout

2. **Command Design:**
   - `sqldown load` - markdown → database (with `--where` for simple filtering)
   - `sqldown dump` - database → markdown (with full SQL `--filter`)
   - `sqldown info` - database stats and table summaries
   - All commands support `--dry-run`

3. **Smart Features:**
   - Path-aware dumping (only dump files under target directory)
   - Change detection (only write files if content differs)
   - Frontmatter filtering during load (simple key=value in v0.1)
   - Automatic gitignore respect
   - Watch mode for file changes

4. **Configuration:**
   - Default database: `./sqldown.db`
   - Environment variable: `SQLDOWN_DB`
   - Tab completion for bash/zsh/fish

5. **Conventions:**
   - Recommended frontmatter field: `doctype` (for document type classification)
   - Short flags: -d (db), -t (table), -o (output), -w (watch), -v (verbose)
   - Database as schema authority

**Testing:**
- Imported 686 tasks from ~/tasks into test database
- Hit SQLite's 2000 column limit (1927 section columns, 72 frontmatter fields)
- Confirmed round-trip capability (body field contains full markdown)

**Artifacts:**
- [SPECIFICATION.md](SPECIFICATION.md) - Complete v0.1 design (627 lines)
- [REVIEW.md](REVIEW.md) - Papa Bear's design review and recommendations
- Test database analysis showing column distribution

**Future Enhancements (v0.2+):**
- Full SQL WHERE during load (currently simple key=value)
- Bidirectional watch mode (database changes → file updates)
- JSON overflow columns for >2000 column scenarios
- FTS5 full-text search
- Configuration file support (.sqldown.toml)

**Critical Items from Review:**
- Address 2000 column limit with JSON overflow in v0.1 (not deferred)
- Add comprehensive error handling and recovery
- Implement transaction batching for performance
- Add SQL injection protection in filter clauses
- Validate path traversal security in dump

**Next Steps:**
- Phase 0: Address critical review items (column overflow, error handling)
- Phase 1: Rename markdown-cache → sqldown throughout codebase
- Phase 2: Create package structure (src/sqldown/, pyproject.toml)
- Phase 3: Implement core load/dump functions
- Phase 4: Implement CLI with Click
- Phase 5: Add tests (>80% coverage)
- Phase 6: Update documentation

### 2025-01-13 - Column Limit Protection Implemented

**Session Goals:**
- Address Papa Bear's critical review finding: SQLite 2000 column limit
- Implement MVP column limit validation
- Add top-N section extraction feature

**Implemented Features:**

1. **Column Limit Validation:**
   - Added `--max-columns` flag (default: 1800, leaving safety margin)
   - Pre-import validation scans all documents and counts unique columns
   - Shows detailed breakdown: base/frontmatter/section columns
   - Warning at 90% threshold
   - Stops import with error if limit exceeded (prevents database corruption)

2. **Top-N Section Extraction:**
   - Added `--top-sections` flag (default: 20, 0=extract all)
   - Analyzes section frequency across entire document collection
   - Extracts only the N most common sections as queryable columns
   - All other sections preserved in `body` field
   - Reduces column count from 6,694 → 116 for real-world task collection

**Testing Results:**
- 5,225 task documents successfully imported
- Without top-sections: Would create 6,694 columns (exceeds 2000 limit)
- With top-20 sections: Creates 116 columns (well within limit)
- Top extracted sections: overview, usage, objective, notes, next_steps, troubleshooting, installation, etc.

**Validation:**
- ✅ Correctly stops import when limit exceeded
- ✅ Shows warning when approaching limit (90% threshold)
- ✅ Proper error codes (exit 1 on failure, 0 on success)
- ✅ Detailed column breakdown in verbose mode
- ✅ All content preserved in body field

**Documentation Updated:**
- README.md: Added column limit protection section
- IDEAS.md: Added section whitelisting and body sync concepts
- Commit messages document rationale and implementation

**Next Steps:**
- Update SPECIFICATION.md to reflect implemented features
- Update SKILL.md with new CLI flags and patterns
- Create taskmaster tasks for ongoing sqldown development
- Consider: section whitelisting (explicit list vs. frequency-based)

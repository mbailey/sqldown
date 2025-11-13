# SQLDown Python Package Specification

## Overview

Convert the current `markdown-cache` project into a proper Python package named `sqldown` that can be installed via pip/uv and used both as a CLI tool and as a Python library.

## Package Name

- **PyPI name**: `sqldown`
- **Import name**: `sqldown`
- **CLI command**: `sqldown`

## Design Philosophy

Keep it simple and maintainable:
- **Bidirectional**: Load markdown → SQLite, dump SQLite → markdown
- Use Click for CLI (already in use)
- Minimal dependencies
- Clear separation between CLI and library code
- Follow standard Python packaging practices
- Database as schema authority: enforces consistency when creating new files

## Directory Structure

```
sqldown/
├── pyproject.toml          # Modern Python packaging (PEP 621)
├── README.md               # PyPI description
├── SKILL.md               # AI agent skill documentation
├── LICENSE                # MIT license
├── .gitignore
│
├── src/
│   └── sqldown/
│       ├── __init__.py           # Package exports
│       ├── __main__.py           # Enable `python -m sqldown`
│       ├── cli.py                # Click CLI commands
│       ├── core.py               # Core markdown processing logic
│       ├── watcher.py            # File watching functionality
│       └── utils.py              # Helper functions
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_core.py
    ├── test_cli.py
    └── test_integration.py
```

## CLI Interface

### Subcommands

The CLI uses subcommands for different operations:

#### `sqldown load` - Load markdown files into database

```bash
sqldown load ROOT_PATH [OPTIONS]
```

**Arguments:**
- `ROOT_PATH` - Directory containing markdown files (required)

**Options:**
- `-d, --db PATH` - Database file (default: `sqldown.db`)
- `-t, --table NAME` - Table name (default: `docs`)
- `-p, --pattern GLOB` - File pattern (default: `**/*.md`)
- `-e, --exclude PATTERN` - Exclude patterns (multiple allowed)
- `--no-gitignore` - Disable .gitignore filtering
- `--where KEY=VALUE` - Filter by frontmatter field (simple equality, multiple allowed)
- `--max-columns N` - Maximum allowed columns (default: 1800, SQLite limit: 2000)
- `--top-sections N` - Extract only top N most common sections (default: 20, 0=all)
- `-w, --watch` - Watch for file changes and auto-update
- `--dry-run` - Show what would be loaded without actually loading
- `-v, --verbose` - Verbose output

**Examples:**
```bash
# Basic load
sqldown load ~/tasks

# Custom database and table
sqldown load ~/notes -d notes.db -t my_notes

# Filter by frontmatter field
sqldown load ~/docs --where doctype=task
sqldown load ~/docs --where status=active --where priority=high

# Watch mode
sqldown load ~/tasks -w

# Exclude patterns
sqldown load ~/docs -e '**/drafts/**' -e '**/temp/**'

# Combined filtering
sqldown load ~/tasks -d tasks.db --where doctype=task --where status!=archived

# Dry run - see what would be loaded
sqldown load ~/docs --dry-run --where doctype=task
# Output: Would load 42 files from ~/docs

# Column limit protection - extract only top 20 sections
sqldown load ~/tasks --top-sections 20
# Analyzes all documents, extracts 20 most common sections

# Extract all sections (may hit column limit with diverse docs)
sqldown load ~/tasks --top-sections 0

# Increase column limit (up to SQLite max of 2000)
sqldown load ~/tasks --max-columns 2000

# Verbose mode shows column breakdown
sqldown load ~/tasks --verbose
# Output:
# 📊 Column breakdown:
#   - Base columns: 7
#   - Frontmatter columns: 89
#   - Section columns: 20
#   - Total: 116 (limit: 1800)
```

#### `sqldown dump` - Export database rows to markdown files

```bash
sqldown dump [OPTIONS]
```

**Options:**
- `-d, --db PATH` - Database file (required)
- `-t, --table NAME` - Table name (default: `docs`)
- `-o, --output DIR` - Output directory (required)
- `-f, --filter QUERY` - WHERE clause to filter rows (optional)
- `--force` - Always write files, even if unchanged
- `--dry-run` - Show what would be dumped without actually writing files
- `-v, --verbose` - Verbose output

**Behavior:**
- Only writes files if content differs from existing file (unless `--force`)
- Path-aware: only dumps files under the output directory tree
- Preserves directory structure from `_path` field
- Skips rows where `_path` would escape the output directory

**Examples:**
```bash
# Dump all rows (writes to paths relative to output dir)
sqldown dump --db cache.db --table tasks --output ~/restored-tasks

# Dump only files under projects/agents/
sqldown dump --db cache.db --table tasks --output ~/tasks/projects/agents
# Only dumps rows where _path starts with "projects/agents/"

# Dump filtered rows
sqldown dump --db cache.db --table tasks --output ~/active \
  --filter "status='active'"

# Force write all (even unchanged files)
sqldown dump --db cache.db --table docs --output ~/export --force

# Dump to current directory
sqldown dump --db cache.db --table docs --output .

# Dry run - see what would be dumped
sqldown dump -d cache.db -o ~/export --dry-run
# Output: Would dump 686 files to ~/export
```

#### `sqldown info` - Show database information

```bash
sqldown info [OPTIONS]
```

**Options:**
- `-d, --db PATH` - Database file (required)
- `-t, --table NAME` - Show details for specific table (optional)

**Output:**
- Database file path and size
- List of tables with row and column counts
- Last modified timestamp
- If table specified: detailed column list and value distributions

**Examples:**
```bash
# Show database overview
sqldown info -d cache.db

# Output:
# Database: cache.db (15.2 MB)
# Modified: 2025-01-15 10:23:45
#
# Tables:
#   tasks       686 rows, 1999 columns
#   notes       234 rows,   45 columns
#   docs        102 rows,   23 columns

# Show table details
sqldown info -d cache.db -t tasks

# Output:
# Table: tasks
# Rows: 686
# Columns: 1999
#
# Common field values:
#   status: active (22), pending (129), completed (34)
#   project: agents (45), taskmaster (23), voicemode (15)
#   priority: high (12), normal (45), low (8)
```

### Global Options

These work with all subcommands:
- `--version` - Show version and exit
- `-h, --help` - Show help message

### Configuration

**Database Location:**
- Default: `sqldown.db` in current directory
- Override with `--db PATH` option
- Environment variable: `SQLDOWN_DB` (if set, used as default)

**Precedence (highest to lowest):**
1. Command-line `--db` flag
2. `SQLDOWN_DB` environment variable
3. Default: `./sqldown.db`

**Examples:**
```bash
# Use default (./sqldown.db)
sqldown load ~/tasks

# Specify database explicitly
sqldown load ~/tasks --db ~/cache/tasks.db

# Use environment variable
export SQLDOWN_DB=~/cache/default.db
sqldown load ~/tasks  # Uses ~/cache/default.db
```

### Tab Completion

Click provides built-in shell completion. To enable:

**Bash:**
```bash
eval "$(_SQLDOWN_COMPLETE=bash_source sqldown)"
# Add to ~/.bashrc for persistence
```

**Zsh:**
```zsh
eval "$(_SQLDOWN_COMPLETE=zsh_source sqldown)"
# Add to ~/.zshrc for persistence
```

**Fish:**
```fish
_SQLDOWN_COMPLETE=fish_source sqldown | source
# Add to ~/.config/fish/config.fish for persistence
```

## Library Interface

The package should also be importable for programmatic use:

```python
from sqldown import load_markdown, dump_markdown, watch_markdown

# Load markdown files into database
load_markdown(
    root_path="~/tasks",
    db_path="cache.db",
    table="tasks",
    pattern="**/*.md",
    exclude_patterns=[],
    respect_gitignore=True,
    verbose=False
)

# Dump database to markdown files
dump_markdown(
    db_path="cache.db",
    table="tasks",
    output_dir="~/restored-tasks",
    filter_where="status='active'",
    force=False,
    verbose=False
)

# Watch mode - auto-update database on file changes
watch_markdown(
    root_path="~/tasks",
    db_path="cache.db",
    table="tasks",
    on_change=lambda event: print(f"Changed: {event}"),
    verbose=True
)
```

## Dependencies

Minimal and well-justified:

- `click >= 8.0` - CLI interface (already in use)
- `sqlite-utils >= 3.30` - SQLite operations (already in use)
- `pyyaml >= 6.0` - YAML frontmatter parsing (already in use)
- `pathspec >= 0.11` - .gitignore pattern matching (already in use)
- `watchdog >= 3.0` - File watching (already in use)

**Development dependencies:**
- `pytest >= 7.0`
- `pytest-cov`

## pyproject.toml Structure

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sqldown"
version = "0.1.0"
description = "Import markdown files with YAML frontmatter into SQLite"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Mike Bailey", email = "mike@bailey.net.au"}
]
keywords = ["markdown", "sqlite", "yaml", "cache", "frontmatter"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
requires-python = ">=3.8"
dependencies = [
    "click>=8.0",
    "sqlite-utils>=3.30",
    "pyyaml>=6.0",
    "pathspec>=0.11",
    "watchdog>=3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[project.scripts]
sqldown = "sqldown.cli:main"

[project.urls]
Homepage = "https://github.com/mbailey/sqldown"
Repository = "https://github.com/mbailey/sqldown"

[tool.hatch.build.targets.wheel]
packages = ["src/sqldown"]
```

## Migration Plan

### Phase 1: Rename and Reorganize (1-2 hours)

1. **Update documentation**
   - Replace all `markdown-cache` → `sqldown`
   - Replace all `md-import` → `sqldown`
   - Replace all `md-cache` → `sqldown`
   - Update SKILL.md
   - Update README.md
   - Update IDEAS.md

2. **Reorganize code**
   - Create `src/sqldown/` directory
   - Move `lib/md_cache.py` → `src/sqldown/core.py`
   - Extract watcher logic from `bin/sqldown` → `src/sqldown/watcher.py`
   - Create `src/sqldown/cli.py` with Click commands
   - Create `src/sqldown/__init__.py` with public API
   - Create `src/sqldown/__main__.py` for `python -m sqldown`
   - Create `src/sqldown/utils.py` for helpers

3. **Update tests**
   - Update test imports
   - Update test references to script paths

### Phase 2: Package Setup (30 min)

1. Create `pyproject.toml`
2. Update `.gitignore` for Python packaging
3. Remove old `requirements.txt` (dependencies now in pyproject.toml)

### Phase 3: Testing (30 min)

1. Test local installation: `pip install -e .`
2. Test CLI: `sqldown --help`
3. Test import: `sqldown ~/tasks --db /tmp/test.db`
4. Test watch mode: `sqldown ~/tasks --watch`
5. Run test suite: `pytest`

### Phase 4: Documentation (30 min)

1. Update README.md with installation instructions
2. Update SKILL.md with new command names
3. Add Python library usage examples
4. Update all code examples

## Click Best Practices

The CLI should follow these Click best practices:

1. **Short and long options**
   ```python
   @click.option('-v', '--verbose', is_flag=True, help='Verbose output')
   @click.option('-w', '--watch', is_flag=True, help='Watch for changes')
   ```

2. **Type hints**
   ```python
   @click.option('--db', type=click.Path(), default='sqldown.db')
   ```

3. **Required vs optional**
   ```python
   @click.argument('root_path', type=click.Path(exists=True))
   ```

4. **Help text**
   - Clear, concise descriptions
   - Include examples in command docstring
   - Use Click's auto-formatting

5. **Exit codes**
   - 0 for success
   - 1 for errors
   - Proper exception handling

6. **Output formatting**
   - Use `click.echo()` for output
   - Use `click.secho()` for colored output
   - Use `err=True` for error messages

## API Design

### Public API (`src/sqldown/__init__.py`)

```python
"""SQLDown - Bidirectional markdown ↔ SQLite conversion.

Public API:
    load_markdown() - Load markdown files into database
    dump_markdown() - Dump database rows to markdown files
    watch_markdown() - Watch and auto-update on changes
    process_file() - Process a single markdown file
"""

from .core import process_file, load_markdown, dump_markdown
from .watcher import watch_markdown

__version__ = "0.1.0"
__all__ = [
    'load_markdown',
    'dump_markdown',
    'watch_markdown',
    'process_file',
]
```

### Core Functions

```python
def process_file(file_path: Path, root_path: Path) -> dict:
    """Process a single markdown file and return document dict.

    Args:
        file_path: Path to markdown file
        root_path: Root directory for relative path calculation

    Returns:
        Dictionary with all fields for database insertion
    """
    pass

def load_markdown(
    root_path: str | Path,
    db_path: str | Path = "sqldown.db",
    table: str = "docs",
    pattern: str = "**/*.md",
    exclude_patterns: list[str] | None = None,
    respect_gitignore: bool = True,
    verbose: bool = False
) -> int:
    """Load markdown files into SQLite database.

    Args:
        root_path: Directory containing markdown files
        db_path: Database file path
        table: Table name
        pattern: Glob pattern for markdown files
        exclude_patterns: Patterns to exclude
        respect_gitignore: Whether to filter by .gitignore
        verbose: Show detailed progress

    Returns:
        Number of documents successfully loaded
    """
    pass

def dump_markdown(
    db_path: str | Path,
    table: str,
    output_dir: str | Path,
    filter_where: str | None = None,
    force: bool = False,
    verbose: bool = False
) -> int:
    """Dump database rows to markdown files.

    Reconstructs markdown files from database rows using the 'body' field
    and writes them to output_dir using the '_path' field.

    Path-aware behavior:
    - Determines which rows to dump based on output_dir
    - Only dumps rows where _path falls under output_dir tree
    - Writes files relative to output_dir preserving structure
    - Prevents path traversal attacks (../ in _path)

    Smart writing:
    - Compares existing file content to avoid unnecessary writes
    - Only writes if content differs (unless force=True)
    - Preserves timestamps when no changes needed

    Args:
        db_path: Database file path
        table: Table name
        output_dir: Output directory for markdown files
        filter_where: SQL WHERE clause to filter rows
        force: Always write files, even if content unchanged
        verbose: Show detailed progress

    Returns:
        Number of files successfully written

    Example:
        # Dump only files under projects/agents/
        dump_markdown(
            db_path="cache.db",
            table="tasks",
            output_dir="~/tasks/projects/agents"
        )
        # Only dumps rows where _path starts with "projects/agents/"
    """
    pass

def reconstruct_markdown(row: dict) -> str:
    """Reconstruct markdown content from database row.

    Args:
        row: Database row as dictionary

    Returns:
        Full markdown content with YAML frontmatter
    """
    pass
```

## Backwards Compatibility

To maintain compatibility during transition:

1. Keep old `bin/sqldown` as a wrapper script
2. Add deprecation warnings if needed
3. Update metool package symlinks

## Testing Requirements

1. **Unit tests**
   - Test markdown parsing
   - Test YAML frontmatter extraction
   - Test H2 section extraction
   - Test gitignore filtering
   - Test markdown reconstruction from database rows
   - Test dump validation

2. **Integration tests**
   - Test full load workflow
   - Test full dump workflow
   - Test load → dump → load round-trip
   - Test watch mode
   - Test CLI commands (load, dump, validate)
   - Test database operations

3. **Coverage target**: >80%

## Success Criteria

- [ ] Package installs with `pip install sqldown`
- [ ] CLI commands work: `sqldown load`, `sqldown dump`, `sqldown validate`
- [ ] Can run as module: `python -m sqldown`
- [ ] All tests pass (>80% coverage)
- [ ] Documentation updated
- [ ] Backwards compatible with metool usage
- [ ] Clean imports: `from sqldown import load_markdown, dump_markdown`
- [ ] Round-trip test passes: load → dump → load produces identical database
- [x] Column limit validation prevents exceeding SQLite 2000 column limit
- [x] Top-N section extraction reduces column count for diverse documents
- [x] Verbose mode shows column breakdown before import

## Future Enhancements (Not in v0.1)

- Publish to PyPI
- Full SQL WHERE clause support during `load` (currently only simple key=value)
- Bidirectional watch mode (database changes → file updates)
- Add `sqldown query` subcommand (though sqlite3 is still preferred)
- Add `sqldown schema` subcommand for schema analysis
- Add FTS5 full-text search support
- Add configuration file support (`.sqldown.toml`)
- Section whitelisting (explicit list vs. frequency-based top-N)

## Recommended Frontmatter Conventions

While sqldown is agnostic about frontmatter fields, we recommend these conventions for better organization:

### Document Type Field

**Recommended field name:** `doctype`

**Purpose:** Classify documents by type for easy filtering during load/dump

**Example values:**
- `task` - Task or ticket documentation
- `spec` - Technical specifications
- `design` - Design documents
- `note` - General notes or documentation
- `reference` - Reference documentation
- `guide` - How-to guides
- `blog` - Blog posts

**Usage:**
```yaml
---
doctype: task
title: Implement user authentication
status: active
---
```

**Filtering during load (v0.1 - simple equality):**
```bash
# Only load task documents
sqldown load ~/docs -d tasks.db --where doctype=task

# Multiple filters (AND logic)
sqldown load ~/docs --where doctype=spec --where status=draft
```

**Filtering during dump (full SQL WHERE):**
```bash
# Full SQL WHERE clause support
sqldown dump -d docs.db -o ~/export --filter "doctype IN ('spec', 'design')"
sqldown dump -d docs.db -o ~/tasks --filter "doctype='task' AND status='active'"
```

### Why "doctype" instead of "type"?

- **"type"** is commonly used for other purposes (e.g., task types: feat/fix/docs)
- **"doctype"** is self-explanatory and unlikely to conflict
- Users can still use any field name they prefer - this is just a recommendation

### Alternative Conventions

Different tools use different conventions - sqldown supports them all:

- **Jekyll/Hugo:** Use `type` or `layout`
- **Kubernetes:** Uses `kind`
- **Your custom:** Use whatever makes sense for your docs

The key is consistency within your document collection.

## Notes

- Keep the philosophy: "Load with Python, query with sqlite3, dump when needed"
- Maintain simplicity - don't add features just because we can
- The CLI should be the primary interface, library use is secondary
- Follow semantic versioning
- Keep dependencies minimal
- The `body` field contains the full markdown, making dump trivial
- Database as schema authority: use it to validate new files before writing

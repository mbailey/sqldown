# Future Ideas for markdown-cache

## md-frontmatter tool

Add a companion tool for manipulating YAML frontmatter.

**Use cases:**
- Add frontmatter to existing markdown files
- Update frontmatter fields in bulk
- Set frontmatter based on SQL queries

**Examples:**
```bash
# Add frontmatter to a file
md-frontmatter add status=active project=foo file.md

# Bulk update from SQL query
md-frontmatter update --db cache.db --table tasks \
  --where "status IS NULL" \
  --set status=pending

# Add metadata from filename patterns
md-frontmatter auto-tag --pattern "PROJECT-*/*.md" \
  --set project=PROJECT
```

**Benefits:**
- Bidirectional workflow (cache ↔ markdown)
- Maintain source files as source of truth
- Easy bulk metadata operations

## File Watching with --watch flag

Add automatic cache refresh when markdown files change using watchdog.

**Implementation:**
- Add `--watch` / `-w` flag to md-import
- Use watchdog library for cross-platform file monitoring (inotify/FSEvents/etc)
- Debounce events to avoid thrashing on rapid changes
- Run initial import, then watch for changes
- Log updates as they happen

**Example:**
```bash
# Watch mode: import once, then auto-update on file changes
md-import --db cache.db --table tasks --root ~/tasks --watch

# Output:
# Initial import: 87 documents imported
# Watching ~/tasks for changes... (Ctrl-C to stop)
# [2025-01-15 10:23:45] Updated: tasks/AG-22_feat_add-configuration/README.md
# [2025-01-15 10:24:12] Added: tasks/AG-31_feat_new-feature/README.md
```

**Dependencies:**
- Add `watchdog>=3.0` to inline dependency list
- Keep as optional import for backward compatibility

**Use Cases:**
- Development: auto-update cache while editing task files
- CI/CD: watch mode for long-running documentation servers
- Local dev servers with live reload

## Section Whitelisting

Allow users to specify which H2 sections to extract as columns, rather than extracting all sections.

**Use cases:**
- Reduce column count by only extracting relevant sections
- Standardize schema across document types
- Avoid schema bloat from one-off section names

**Implementation options:**
```bash
# Option 1: Whitelist specific sections
sqldown load ~/tasks --sections "status,next_actions,notes"

# Option 2: Config file
# .sqldown.toml
[sections]
whitelist = ["status", "next_actions", "notes", "context"]
```

**Notes:**
- The `body` field already contains the full markdown, so non-extracted sections aren't lost
- Could still search full text via the body field
- Reduces schema evolution and column limit issues

## Body Field Synchronization

Consider how to handle the `body` field when updating individual sections.

**Current behavior:**
- `body` contains the full markdown content
- Sections are extracted into separate columns

**Questions:**
- When a section column is updated, should `body` be regenerated?
- Should updates go through `body` as source of truth, with sections derived?
- Or are section columns independent once extracted?

**Possible approaches:**
1. **Body as source of truth**: Always regenerate sections from body
2. **Sections as source of truth**: Regenerate body when sections change (via dump)
3. **Independent**: Body and sections can diverge (current behavior)

## Other Ideas

- FTS5 full-text search indexes
- Graph queries for linked documents
- Embedding-based semantic search
- Export to different formats (JSON, CSV)

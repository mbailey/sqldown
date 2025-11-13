"""Command-line interface for sqldown using Click."""

import sys
import click
from pathlib import Path
from sqlite_utils import Database

from .core import (
    analyze_section_frequency,
    process_markdown_file,
    reconstruct_markdown,
    validate_column_count,
)
from .utils import (
    find_git_root,
    get_default_database_path,
    infer_table_name,
    load_cascading_env,
    get_config_value,
)


@click.group()
@click.version_option(version="0.1.0")
@click.help_option('-h', '--help')
def main():
    """SQLDown - Bidirectional markdown ↔ SQLite conversion.

    Load markdown files into SQLite, query with sqlite3, dump when needed.
    """
    pass


@main.command()
@click.argument('root_path', type=click.Path(exists=True, path_type=Path))
@click.option('-d', '--db', type=click.Path(path_type=Path), default=None,
              help='Database file (default: .sqldown.db in project root)')
@click.option('-t', '--table', default=None,
              help='Table name (default: inferred from directory name)')
@click.option('-p', '--pattern', default='**/*.md', help='File pattern (default: **/*.md)')
@click.option('-m', '--max-columns', type=int, default=None,
              help='Maximum allowed columns (default: 1800, SQLite limit: 2000)')
@click.option('-n', '--top-sections', type=int, default=None,
              help='Extract only top N most common sections (default: 20, 0=all)')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
@click.help_option('-h', '--help')
def load(root_path, db, table, pattern, max_columns, top_sections, verbose):
    """Load markdown files into database.

    Examples:
      sqldown load ~/tasks
      sqldown load ~/notes -d notes.db -t my_notes
      sqldown load ~/tasks --top-sections 10
    """
    # Load cascading configuration
    config = load_cascading_env(root_path)

    # Apply smart defaults
    if db is None:
        # Check config, then use smart default
        db_path = get_config_value(config, 'DB', None)
        if db_path:
            db = Path(db_path)
        else:
            db = get_default_database_path(root_path)

    if table is None:
        # Check config for table name or prefix
        table_prefix = get_config_value(config, 'TABLE_PREFIX', '')
        table = get_config_value(config, 'TABLE', None)
        if not table:
            table = table_prefix + infer_table_name(root_path)

    # Apply config defaults for other options
    if max_columns is None:
        max_columns = get_config_value(config, 'MAX_COLUMNS', 1800)

    if top_sections is None:
        top_sections = get_config_value(config, 'TOP_SECTIONS', 20)

    # Check for verbose in config
    if not verbose:
        verbose = get_config_value(config, 'VERBOSE', False)

    if verbose:
        click.echo(f"📂 Scanning {root_path} for {pattern}")
        click.echo(f"💾 Database: {db}")
        click.echo(f"📊 Table: {table}")
        click.echo()

    # Find all markdown files
    md_files = list(root_path.glob(pattern))

    if not md_files:
        click.echo(f"❌ No markdown files found matching {pattern} in {root_path}", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Found {len(md_files)} files")
        click.echo()

    # Analyze section frequency if top-sections is enabled
    allowed_sections = None
    if top_sections > 0:
        if verbose:
            click.echo(f"🔍 Analyzing section frequency across {len(md_files)} files...")
        allowed_sections = analyze_section_frequency(md_files, top_sections)
        if verbose and allowed_sections:
            click.echo(f"📊 Extracting top {len(allowed_sections)} sections:")
            for section in sorted(allowed_sections):
                click.echo(f"  - {section}")
            click.echo()

    # Process all files
    docs = []
    for md_file in md_files:
        if verbose:
            click.echo(f"📄 {md_file.relative_to(root_path)}")

        try:
            doc = process_markdown_file(md_file, root_path, allowed_sections)
            docs.append(doc)
        except Exception as e:
            click.echo(f"⚠️  Error processing {md_file}: {e}", err=True)
            continue

    # Validate column count before importing
    if verbose:
        click.echo("\n🔍 Validating schema...")

    is_valid, total_cols, breakdown = validate_column_count(docs, max_columns)

    if verbose:
        click.echo(f"📊 Column breakdown:")
        click.echo(f"  - Base columns: {breakdown['base']}")
        click.echo(f"  - Frontmatter columns: {breakdown['frontmatter']}")
        click.echo(f"  - Section columns: {breakdown['sections']}")
        click.echo(f"  - Total: {breakdown['total']} (limit: {max_columns})")
        click.echo()

    # Show warning if approaching limit (within 10% of max)
    warning_threshold = int(max_columns * 0.9)
    if total_cols >= warning_threshold and total_cols <= max_columns:
        click.echo(f"⚠️  Warning: Approaching column limit ({total_cols}/{max_columns})", err=True)
        click.echo(f"   Consider reducing document diversity or increasing --max-columns", err=True)
        click.echo()

    if not is_valid:
        click.echo(f"❌ Column limit exceeded: {total_cols} columns > {max_columns} limit", err=True)
        click.echo(f"   Base columns: {breakdown['base']}", err=True)
        click.echo(f"   Frontmatter columns: {breakdown['frontmatter']}", err=True)
        click.echo(f"   Section columns: {breakdown['sections']}", err=True)
        click.echo(f"\n💡 Options:", err=True)
        click.echo(f"   1. Reduce document diversity (fewer unique H2 sections/frontmatter fields)", err=True)
        click.echo(f"   2. Increase limit with --max-columns (SQLite max: 2000)", err=True)
        click.echo(f"   3. Split into multiple databases by document type", err=True)
        sys.exit(1)

    # Check if database/table exists before import
    db_existed = db.exists()
    database = Database(str(db))
    table_existed = table in database.table_names() if db_existed else False

    # Get existing IDs to track updates vs inserts
    existing_ids = set()
    if table_existed:
        existing_ids = {row['_id'] for row in database[table].rows_where(select='_id')}

    # Import to database with dynamic schema
    added = 0
    updated = 0
    errors = 0

    for doc in docs:
        try:
            doc_id = doc.get('_id')
            if doc_id in existing_ids:
                updated += 1
            else:
                added += 1
            database[table].upsert(doc, pk='_id', alter=True)
        except Exception as e:
            errors += 1
            if verbose:
                click.echo(f"⚠️  Error upserting {doc.get('_path', 'unknown')}: {e}", err=True)

    # Build concise output message
    action = "Created" if not db_existed else "Updated"
    db_path = db.resolve()

    # Make path relative if it's under current directory
    try:
        rel_path = db_path.relative_to(Path.cwd())
        db_display = str(rel_path)
    except ValueError:
        # Not under current directory, show absolute
        db_display = str(db_path)

    # Build statistics part
    stats_parts = []
    if added > 0:
        stats_parts.append(f"{added} added")
    if updated > 0:
        stats_parts.append(f"{updated} modified")

    processed = added + updated
    total_found = len(md_files)

    # Single line output
    stats = ", ".join(stats_parts) if stats_parts else "no changes"
    click.echo(f"{action} {db_display}: {stats} ({processed}/{total_found} files processed)")

    if errors > 0:
        click.echo(f"⚠️  {errors} files failed to import", err=True)


@main.command()
@click.option('-d', '--db', type=click.Path(path_type=Path), default=None,
              help='Database file (default: .sqldown.db in project root)')
@click.option('-t', '--table', default='docs', help='Table name (default: docs)')
@click.option('-o', '--output', required=True, type=click.Path(path_type=Path),
              help='Output directory (required)')
@click.option('-f', '--filter', 'filter_where', help='SQL WHERE clause to filter rows')
@click.option('--force', is_flag=True, help='Always write files, even if unchanged')
@click.option('-n', '--dry-run', is_flag=True, help='Show what would be dumped without writing')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
@click.help_option('-h', '--help')
def dump(db, table, output, filter_where, force, dry_run, verbose):
    """Export database rows to markdown files.

    Examples:
      sqldown dump -o ~/restored                     # Uses .sqldown.db in project root
      sqldown dump -d cache.db -o ~/restored
      sqldown dump -t tasks -o ~/active --filter "status='active'"
      sqldown dump -o ~/export --dry-run
    """
    # Load configuration
    config = load_cascading_env()

    # Apply smart defaults for database
    if db is None:
        # Check config, then use smart default
        db_path = get_config_value(config, 'DB', None)
        if db_path:
            db = Path(db_path)
        else:
            # Try to find database in project root
            db = get_default_database_path()

            # If it doesn't exist, also try sqldown.db in current directory
            if not db.exists():
                alt_db = Path('sqldown.db')
                if alt_db.exists():
                    db = alt_db
                else:
                    click.echo(f"❌ No database found. Tried:", err=True)
                    click.echo(f"   - {db}", err=True)
                    click.echo(f"   - {alt_db}", err=True)
                    click.echo(f"   Use -d to specify a database file", err=True)
                    sys.exit(1)

    # Check database exists
    if not db.exists():
        click.echo(f"❌ Database not found: {db}", err=True)
        sys.exit(1)

    # Apply config defaults for other options
    if not force:
        force = get_config_value(config, 'DUMP_FORCE', False)

    if not dry_run:
        dry_run = get_config_value(config, 'DUMP_DRY_RUN', False)

    if not verbose:
        verbose = get_config_value(config, 'VERBOSE', False)

    database = Database(str(db))

    # Check table exists
    if table not in database.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"📂 Exporting from {db}:{table}")
        click.echo(f"💾 Output directory: {output}")
        if filter_where:
            click.echo(f"🔍 Filter: {filter_where}")
        if dry_run:
            click.echo("🔎 DRY RUN - no files will be written")
        click.echo()

    # Query rows
    tbl = database[table]
    if filter_where:
        rows = tbl.rows_where(filter_where)
    else:
        rows = tbl.rows

    # Process each row
    written = 0
    skipped = 0
    errors = 0

    for row in rows:
        row_dict = dict(row)
        path_str = row_dict.get('_path')

        if not path_str:
            if verbose:
                click.echo(f"⚠️  Row {row_dict.get('_id', 'unknown')} has no _path, skipping", err=True)
            skipped += 1
            continue

        # Reconstruct markdown
        try:
            markdown_content = reconstruct_markdown(row_dict)
        except Exception as e:
            click.echo(f"❌ Error reconstructing {path_str}: {e}", err=True)
            errors += 1
            continue

        # Determine output path
        output_file = output / path_str

        if verbose:
            status = "would write" if dry_run else "writing"
            click.echo(f"📄 {status}: {output_file.relative_to(output) if output_file.is_relative_to(output) else output_file}")

        if dry_run:
            written += 1
            continue

        # Check if file exists and content is unchanged (unless --force)
        if not force and output_file.exists():
            existing_content = output_file.read_text()
            if existing_content == markdown_content:
                if verbose:
                    click.echo(f"  ⏭️  unchanged, skipping")
                skipped += 1
                continue

        # Write file
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown_content)
            written += 1
        except Exception as e:
            click.echo(f"❌ Error writing {output_file}: {e}", err=True)
            errors += 1

    # Summary
    if verbose:
        click.echo()

    if dry_run:
        click.echo(f"🔎 Dry run: would write {written} files")
    else:
        click.echo(f"✅ Exported {written} files to {output}")

    if skipped > 0:
        click.echo(f"⏭️  Skipped {skipped} files")

    if errors > 0:
        click.echo(f"❌ {errors} errors occurred", err=True)
        sys.exit(1)


@main.command()
@click.option('-d', '--db', type=click.Path(path_type=Path), default=None,
              help='Database file (default: .sqldown.db in project root)')
@click.option('-t', '--table', help='Show details for specific table')
@click.help_option('-h', '--help')
def info(db, table):
    """Show database information.

    Examples:
      sqldown info                  # Uses .sqldown.db in project root
      sqldown info -d cache.db
      sqldown info -t tasks          # Shows specific table details
    """
    # Load configuration
    config = load_cascading_env()

    # Apply smart defaults for database
    if db is None:
        # Check config, then use smart default
        db_path = get_config_value(config, 'DB', None)
        if db_path:
            db = Path(db_path)
        else:
            # Try to find database in project root
            db = get_default_database_path()

            # If it doesn't exist, also try sqldown.db in current directory
            if not db.exists():
                alt_db = Path('sqldown.db')
                if alt_db.exists():
                    db = alt_db
                else:
                    click.echo(f"❌ No database found. Tried:", err=True)
                    click.echo(f"   - {db}", err=True)
                    click.echo(f"   - {alt_db}", err=True)
                    click.echo(f"   Use -d to specify a database file", err=True)
                    sys.exit(1)

    # Check database exists
    if not db.exists():
        click.echo(f"❌ Database not found: {db}", err=True)
        sys.exit(1)

    database = Database(str(db))

    if table:
        # Show table details
        if table not in database.table_names():
            click.echo(f"❌ Table '{table}' not found in database", err=True)
            sys.exit(1)

        tbl = database[table]
        columns = list(tbl.columns)
        count = tbl.count

        # Categorize columns
        core_columns = ['_id', '_path', '_sections', 'title', 'body', 'lead', 'file_modified']
        frontmatter_columns = []
        section_columns = []

        for col in columns:
            col_name = col.name
            if col_name in core_columns:
                continue
            elif col_name.startswith('section_'):
                section_columns.append(col_name)
            else:
                frontmatter_columns.append(col_name)

        # Display table info
        click.echo(f"\n📊 Table: {table}")
        click.echo(f"{'─' * 40}")
        click.echo(f"📝 Documents: {count:,}")
        click.echo(f"📋 Total columns: {len(columns)}")
        click.echo()

        # Column breakdown
        click.echo(f"Column breakdown:")
        click.echo(f"  • Core fields: {len(core_columns)}")
        click.echo(f"  • Frontmatter fields: {len(frontmatter_columns)}")
        click.echo(f"  • Section fields: {len(section_columns)}")

        # Show sample frontmatter fields
        if frontmatter_columns:
            click.echo()
            click.echo(f"Frontmatter fields ({len(frontmatter_columns)}):")
            sample = frontmatter_columns[:10]
            for field in sorted(sample):
                click.echo(f"  - {field}")
            if len(frontmatter_columns) > 10:
                click.echo(f"  ... and {len(frontmatter_columns) - 10} more")

        # Show sample sections
        if section_columns:
            click.echo()
            click.echo(f"Document sections ({len(section_columns)}):")
            # Clean up section names for display
            section_names = [col.replace('section_', '').replace('_', ' ').title()
                           for col in section_columns]
            sample = section_names[:10]
            for section in sorted(sample):
                click.echo(f"  - {section}")
            if len(section_names) > 10:
                click.echo(f"  ... and {len(section_names) - 10} more")

    else:
        # Show database overview
        db_path = Path(db)
        size_mb = db_path.stat().st_size / (1024 * 1024)

        tables = database.table_names()

        click.echo(f"\n💾 Database: {db_path.name}")
        click.echo(f"{'─' * 40}")
        click.echo(f"📁 Location: {db_path.absolute()}")
        click.echo(f"💿 Size: {size_mb:.1f} MB")
        click.echo(f"📊 Tables: {len(tables)}")
        click.echo()

        if tables:
            click.echo("Tables:")
            total_rows = 0
            for table_name in tables:
                tbl = database[table_name]
                count = tbl.count
                total_rows += count
                col_count = len(list(tbl.columns))

                # Count column types
                columns = list(tbl.columns)
                frontmatter = sum(1 for c in columns if not c.name.startswith('section_')
                                and c.name not in ['_id', '_path', '_sections', 'title',
                                                  'body', 'lead', 'file_modified'])
                sections = sum(1 for c in columns if c.name.startswith('section_'))

                click.echo(f"  📋 {table_name}")
                click.echo(f"     • {count:,} documents")
                click.echo(f"     • {col_count} columns ({frontmatter} frontmatter, {sections} sections)")

            if len(tables) > 1:
                click.echo()
                click.echo(f"Total: {total_rows:,} documents across all tables")
        else:
            click.echo("  (no tables)")

        click.echo()
        click.echo("💡 Tips:")
        click.echo(f"  • Query with: sqlite3 {db_path.name} \"SELECT * FROM table LIMIT 5\"")
        click.echo(f"  • Show schema: sqlite3 {db_path.name} \".schema table\"")
        click.echo(f"  • Table details: sqldown info -t <table>")


if __name__ == '__main__':
    main()
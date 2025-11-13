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


@click.group()
@click.version_option(version="0.1.0")
def main():
    """SQLDown - Bidirectional markdown ↔ SQLite conversion.

    Load markdown files into SQLite, query with sqlite3, dump when needed.
    """
    pass


@main.command()
@click.argument('root_path', type=click.Path(exists=True, path_type=Path))
@click.option('-d', '--db', default='sqldown.db', type=click.Path(path_type=Path),
              help='Database file (default: sqldown.db)')
@click.option('-t', '--table', default='docs', help='Table name (default: docs)')
@click.option('-p', '--pattern', default='**/*.md', help='File pattern (default: **/*.md)')
@click.option('--max-columns', default=1800, type=int,
              help='Maximum allowed columns (default: 1800, SQLite limit: 2000)')
@click.option('--top-sections', default=20, type=int,
              help='Extract only top N most common sections (default: 20, 0=all)')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def load(root_path, db, table, pattern, max_columns, top_sections, verbose):
    """Load markdown files into database.

    Examples:
      sqldown load ~/tasks
      sqldown load ~/notes -d notes.db -t my_notes
      sqldown load ~/tasks --top-sections 10
    """
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

    # Import to database with dynamic schema
    database = Database(str(db))
    imported = 0
    for doc in docs:
        try:
            database[table].upsert(doc, pk='_id', alter=True)
            imported += 1
        except Exception as e:
            click.echo(f"⚠️  Error upserting {doc.get('_path', 'unknown')}: {e}", err=True)

    if verbose:
        click.echo()
    click.echo(f"✅ Imported {imported} of {len(docs)} documents into {db}:{table}")

    # Show schema info
    columns = database[table].columns
    click.echo(f"📋 Schema has {len(columns)} columns")


@main.command()
@click.option('-d', '--db', required=True, type=click.Path(exists=True, path_type=Path),
              help='Database file (required)')
@click.option('-t', '--table', default='docs', help='Table name (default: docs)')
@click.option('-o', '--output', required=True, type=click.Path(path_type=Path),
              help='Output directory (required)')
@click.option('-f', '--filter', 'filter_where', help='SQL WHERE clause to filter rows')
@click.option('--force', is_flag=True, help='Always write files, even if unchanged')
@click.option('--dry-run', is_flag=True, help='Show what would be dumped without writing')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def dump(db, table, output, filter_where, force, dry_run, verbose):
    """Export database rows to markdown files.

    Examples:
      sqldown dump -d cache.db -o ~/restored
      sqldown dump -d cache.db -t tasks -o ~/active --filter "status='active'"
      sqldown dump -d cache.db -o ~/export --dry-run
    """
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
@click.option('-d', '--db', required=True, type=click.Path(exists=True, path_type=Path),
              help='Database file (required)')
@click.option('-t', '--table', help='Show details for specific table')
def info(db, table):
    """Show database information.

    Examples:
      sqldown info -d cache.db
      sqldown info -d cache.db -t tasks
    """
    database = Database(str(db))

    if table:
        # Show table details
        if table not in database.table_names():
            click.echo(f"❌ Table '{table}' not found in database", err=True)
            sys.exit(1)

        tbl = database[table]
        columns = list(tbl.columns)
        count = tbl.count

        click.echo(f"Table: {table}")
        click.echo(f"Rows: {count:,}")
        click.echo(f"Columns: {len(columns)}")
        click.echo()
        click.echo("Columns:")
        for col in columns:
            click.echo(f"  - {col.name} ({col.type})")
    else:
        # Show database overview
        db_path = Path(db)
        size_mb = db_path.stat().st_size / (1024 * 1024)

        click.echo(f"Database: {db_path} ({size_mb:.1f} MB)")
        click.echo()
        click.echo("Tables:")

        for table_name in database.table_names():
            tbl = database[table_name]
            count = tbl.count
            col_count = len(list(tbl.columns))
            click.echo(f"  {table_name:20s} {count:6,} rows, {col_count:4,} columns")


if __name__ == '__main__':
    main()

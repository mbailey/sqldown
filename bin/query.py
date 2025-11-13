#!/usr/bin/env python3
"""
Query tool for markdown SQLite cache with dynamic schema.

Works with databases created by import.py regardless of schema.
"""

import click
from pathlib import Path
from sqlite_utils import Database
from typing import Optional, List


@click.group()
@click.option('--db', default='cache.db', help='Database file path', required=False)
@click.option('--table', default='docs', help='Table name', required=False)
@click.pass_context
def cli(ctx, db, table):
    """Query markdown cache database."""
    ctx.ensure_object(dict)
    ctx.obj['db_path'] = db
    ctx.obj['table'] = table


@cli.command()
@click.option('--limit', default=50, help='Maximum results')
@click.option('--offset', default=0, help='Results offset')
@click.option('--where', help='SQL WHERE clause')
@click.option('--order', default='_path', help='Order by column')
@click.option('--desc', is_flag=True, help='Descending order')
@click.pass_context
def list_docs(ctx, limit, offset, where, order, desc):
    """List documents from the cache."""
    db = Database(ctx.obj['db_path'])
    table = ctx.obj['table']

    if table not in db.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        return 1

    # Build query using direct SQL to avoid sqlite-utils issues with large result sets
    order_clause = f'"{order}" DESC' if desc else f'"{order}"'

    if where:
        sql = f'SELECT * FROM "{table}" WHERE {where} ORDER BY {order_clause} LIMIT ? OFFSET ?'
        params = [limit, offset]
    else:
        sql = f'SELECT * FROM "{table}" ORDER BY {order_clause} LIMIT ? OFFSET ?'
        params = [limit, offset]

    results = [row for row in db.execute(sql, params).fetchall()]

    if not results:
        click.echo("No results found")
        return

    # Get column names
    columns = [col.name for col in db[table].columns]

    click.echo(f"Found {len(results)} documents:\n")

    for row_tuple in results:
        # Convert tuple to dict
        row = dict(zip(columns, row_tuple))

        # Show key fields
        title = row.get('title', row.get('_path', 'Untitled'))
        path = row.get('_path', '')

        click.echo(f"📄 {title}")
        if path and path != title:
            click.echo(f"   Path: {path}")

        # Show other interesting fields
        for key in ['status', 'project', 'type', 'tags', 'created', 'updated']:
            if key in row and row[key]:
                click.echo(f"   {key.title()}: {row[key]}")

        click.echo()


@cli.command()
@click.argument('keyword')
@click.option('--limit', default=20, help='Maximum results')
@click.option('--in-field', help='Search only in specific field')
@click.pass_context
def search(ctx, keyword, limit, in_field):
    """Search for keyword in documents."""
    db = Database(ctx.obj['db_path'])
    table = ctx.obj['table']

    if table not in db.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        return 1

    # Get text columns for searching
    text_columns = [col.name for col in db[table].columns if col.type == 'TEXT']

    if in_field:
        if in_field not in text_columns:
            click.echo(f"❌ Field '{in_field}' not found or not searchable", err=True)
            return 1
        search_fields = [in_field]
    else:
        search_fields = text_columns

    # Build search query with quoted column names (to handle SQL keywords)
    conditions = [f'"{field}" LIKE ?' for field in search_fields]
    where_clause = " OR ".join(conditions)
    params = [f"%{keyword}%" for _ in search_fields]

    results = [row for row in db.execute(
        f'SELECT * FROM "{table}" WHERE {where_clause} LIMIT ?',
        params + [limit]
    ).fetchall()]

    if not results:
        click.echo(f"No documents found matching '{keyword}'")
        return

    click.echo(f"Found {len(results)} documents matching '{keyword}':\n")

    columns = [col.name for col in db[table].columns]
    for row_tuple in results:
        row = dict(zip(columns, row_tuple))
        title = row.get('title', row.get('_path', 'Untitled'))
        path = row.get('_path', '')

        click.echo(f"📄 {title}")
        if path and path != title:
            click.echo(f"   Path: {path}")
        click.echo()


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    db = Database(ctx.obj['db_path'])
    table = ctx.obj['table']

    if table not in db.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        return 1

    click.echo("📊 Cache Statistics")
    click.echo("=" * 50)

    # Total count
    total = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    click.echo(f"Total documents: {total}\n")

    # Show schema
    columns = db[table].columns
    click.echo(f"Schema: {len(columns)} columns")
    for col in columns:
        click.echo(f"  - {col.name} ({col.type})")
    click.echo()

    # Aggregate by common fields
    for field in ['status', 'project', 'type', 'tags']:
        try:
            results = db.execute(
                f"SELECT {field}, COUNT(*) as count FROM {table} WHERE {field} IS NOT NULL GROUP BY {field} ORDER BY count DESC LIMIT 10"
            ).fetchall()

            if results:
                click.echo(f"By {field}:")
                for value, count in results:
                    bar = '█' * min(40, int(count * 40 / total)) if total > 0 else ''
                    click.echo(f"  {str(value)[:20]:20} {count:4} {bar}")
                click.echo()
        except:
            # Field doesn't exist, skip it
            pass


@cli.command()
@click.argument('document_id')
@click.pass_context
def get(ctx, document_id):
    """Get full details of a document by ID or path."""
    db = Database(ctx.obj['db_path'])
    table = ctx.obj['table']

    if table not in db.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        return 1

    # Try by ID first
    row = db[table].get(document_id)

    # If not found, try by path
    if not row:
        results = [r for r in db[table].rows_where("_path = ?", [document_id])]
        if results:
            row = results[0]

    # If still not found, try partial path match
    if not row:
        results = [r for r in db[table].rows_where("_path LIKE ?", [f"%{document_id}%"])]
        if results:
            if len(results) == 1:
                row = results[0]
            else:
                click.echo(f"Multiple documents match '{document_id}':")
                for r in results:
                    click.echo(f"  - {r['_path']}")
                return

    if not row:
        click.echo(f"❌ Document not found: {document_id}", err=True)
        return 1

    # Display document
    click.echo("📄 Document Details")
    click.echo("=" * 50)

    for key, value in row.items():
        if key == 'body':
            # Show truncated body
            if value:
                body_preview = value[:500] + '...' if len(value) > 500 else value
                click.echo(f"\n{key}:\n{body_preview}")
        elif value:
            click.echo(f"{key}: {value}")


@cli.command()
@click.argument('sql_query')
@click.pass_context
def sql(ctx, sql_query):
    """Execute custom SQL query (SELECT only)."""
    db = Database(ctx.obj['db_path'])

    # Safety check
    if not sql_query.strip().upper().startswith('SELECT'):
        click.echo("❌ Only SELECT queries are allowed", err=True)
        return 1

    try:
        results = db.execute(sql_query).fetchall()

        if not results:
            click.echo("No results")
            return

        # Get column names from cursor description
        columns = [desc[0] for desc in db.execute(sql_query).description]

        # Display as table
        click.echo(" | ".join(columns))
        click.echo("-" * (len(columns) * 15))

        for row in results:
            values = []
            for value in row:
                str_value = str(value) if value is not None else ''
                if len(str_value) > 30:
                    str_value = str_value[:27] + '...'
                values.append(str_value)
            click.echo(" | ".join(values))

    except Exception as e:
        click.echo(f"❌ SQL error: {e}", err=True)
        return 1


@cli.command()
@click.pass_context
def schema(ctx):
    """Show database schema information."""
    db = Database(ctx.obj['db_path'])
    table = ctx.obj['table']

    if table not in db.table_names():
        click.echo(f"❌ Table '{table}' not found in database", err=True)
        click.echo(f"\nAvailable tables: {', '.join(db.table_names())}")
        return 1

    click.echo(f"📋 Schema for table '{table}'")
    click.echo("=" * 50)

    columns = db[table].columns
    click.echo(f"\nColumns ({len(columns)}):")
    for col in columns:
        click.echo(f"  {col.name:30} {col.type:10}")

    # Show indexes
    indexes = db.execute(
        f"SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND name NOT LIKE 'sqlite_%'",
        [table]
    ).fetchall()

    if indexes:
        click.echo(f"\nIndexes ({len(indexes)}):")
        for name, sql in indexes:
            click.echo(f"  {name}")


if __name__ == '__main__':
    cli()

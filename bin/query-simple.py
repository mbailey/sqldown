#!/usr/bin/env python3
"""
Simple query tool for markdown cache - works with any dynamic schema.
"""

import click
import sqlite3
import json
from pathlib import Path


@click.group()
@click.option('--db', default='cache.db', help='Database file path')
@click.option('--table', default='docs', help='Table name')
@click.pass_context
def cli(ctx, db, table):
    """Query markdown cache database."""
    ctx.ensure_object(dict)
    ctx.obj['db'] = db
    ctx.obj['table'] = table


@cli.command()
@click.option('--limit', default=10, help='Maximum results')
@click.pass_context
def list_docs(ctx, limit):
    """List documents."""
    conn = sqlite3.connect(ctx.obj['db'])
    conn.row_factory = sqlite3.Row

    sql = f'SELECT _path, title, status, project FROM {ctx.obj["table"]} LIMIT ?'

    for row in conn.execute(sql, [limit]):
        click.echo(f"📄 {row['title'] or row['_path']}")
        if row['status']:
            click.echo(f"   Status: {row['status']}")
        if row['project']:
            click.echo(f"   Project: {row['project']}")
        click.echo()

    conn.close()


@cli.command()
@click.argument('keyword')
@click.option('--limit', default=10, help='Maximum results')
@click.pass_context
def search(ctx, keyword, limit):
    """Search for keyword."""
    conn = sqlite3.connect(ctx.obj['db'])
    conn.row_factory = sqlite3.Row

    sql = f'SELECT _path, title FROM {ctx.obj["table"]} WHERE body LIKE ? OR title LIKE ? LIMIT ?'

    results = [row for row in conn.execute(sql, [f'%{keyword}%', f'%{keyword}%', limit])]

    if not results:
        click.echo(f"No results for '{keyword}'")
        return

    click.echo(f"Found {len(results)} results:\n")
    for row in results:
        click.echo(f"📄 {row['title'] or row['_path']}")

    conn.close()


@cli.command()
@click.pass_context
def stats(ctx):
    """Show statistics."""
    conn = sqlite3.connect(ctx.obj['db'])

    total = conn.execute(f'SELECT COUNT(*) FROM {ctx.obj["table"]}').fetchone()[0]
    click.echo(f"Total documents: {total}\n")

    # Show status breakdown
    try:
        results = conn.execute(
            f'SELECT status, COUNT(*) as count FROM {ctx.obj["table"]} WHERE status IS NOT NULL GROUP BY status'
        ).fetchall()

        if results:
            click.echo("By status:")
            for status, count in results:
                click.echo(f"  {status}: {count}")
    except:
        pass

    conn.close()


if __name__ == '__main__':
    cli()

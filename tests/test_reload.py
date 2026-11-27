"""Tests for reloading markdown into an existing database.

A reload must leave each row matching its file as it is now, not merged
with what the file used to contain.
"""
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlite_utils import Database

from sqldown.cli import main
from sqldown.core import load_markdown


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rows_by_path(db_path: Path, table: str = "docs") -> dict:
    return {row["_path"]: row for row in Database(str(db_path))[table].rows}


def cli_load(root: Path, db_path: Path, *extra: str):
    result = CliRunner().invoke(
        main, ["load", str(root), "-d", str(db_path), "-t", "docs", *extra]
    )
    assert result.exit_code == 0, result.output
    return result


def api_load(root: Path, db_path: Path, **kwargs):
    return load_markdown(root, db_path, table="docs", **kwargs)


LOADERS = [
    pytest.param(cli_load, id="cli"),
    pytest.param(lambda root, db, *a: api_load(root, db), id="api"),
]


@pytest.mark.parametrize("load", LOADERS)
def test_removed_frontmatter_field_is_cleared(tmp_path, load):
    root = tmp_path / "docs"
    db_path = tmp_path / "index.db"
    write(root / "a.md", "---\nstatus: open\ndue: '2026-10-23'\n---\n# A\n")

    load(root, db_path)
    assert rows_by_path(db_path)["a.md"]["due"] == "2026-10-23"

    write(root / "a.md", "---\nstatus: open\n---\n# A\n")
    load(root, db_path)

    row = rows_by_path(db_path)["a.md"]
    assert row["due"] is None
    assert row["status"] == "open"


@pytest.mark.parametrize("load", LOADERS)
def test_removed_section_is_cleared(tmp_path, load):
    root = tmp_path / "docs"
    db_path = tmp_path / "index.db"
    write(root / "a.md", "# A\n\n## Notes\n\nold notes\n\n## Plan\n\nthe plan\n")

    load(root, db_path)
    assert rows_by_path(db_path)["a.md"]["section_notes"] == "old notes"

    write(root / "a.md", "# A\n\n## Plan\n\nthe plan\n")
    load(root, db_path)

    row = rows_by_path(db_path)["a.md"]
    assert row["section_notes"] is None
    assert row["section_plan"] == "the plan"

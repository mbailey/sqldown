"""Integration tests using real markdown files."""
import pytest
import sqlite3
from pathlib import Path
from sqlite_utils import Database
import subprocess
import tempfile
import os


class TestRealDataImport:
    """Test importing real markdown files."""

    @pytest.fixture
    def sqldown_command(self):
        """Command to run sqldown CLI."""
        # Run sqldown module directly using python -m
        import sys
        return [sys.executable, '-m', 'sqldown.cli', 'load']

    @pytest.fixture
    def test_db(self):
        """Create temporary test database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def tasks_dir(self):
        """Path to user's tasks directory."""
        tasks_path = Path.home() / 'tasks'
        if not tasks_path.exists():
            pytest.skip("Tasks directory not found")
        return tasks_path

    def test_import_single_task(self, sqldown_command, test_db, tasks_dir):
        """Import a single task and verify schema."""
        # Find a single task
        task_files = list(tasks_dir.glob('AG-*/README.md'))
        if not task_files:
            pytest.skip("No task files found")

        task_file = task_files[0]
        task_dir = task_file.parent

        # Run import
        result = subprocess.run(
            sqldown_command + [str(task_dir), '--db', test_db, '--table', 'tasks'],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Import failed: {result.stderr}"

        # Verify database
        db = Database(test_db)
        assert 'tasks' in db.table_names()

        # Check row count
        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == 1

        # Check core fields exist
        columns = {col.name for col in db['tasks'].columns}
        assert '_id' in columns
        assert '_path' in columns
        assert '_sections' in columns
        assert 'title' in columns
        assert 'body' in columns
        assert 'lead' in columns
        assert 'file_modified' in columns

    def test_import_multiple_tasks(self, sqldown_command, test_db, tasks_dir):
        """Import multiple tasks and verify dynamic schema."""
        # Import first 5 tasks
        task_files = list(tasks_dir.glob('AG-*/README.md'))[:5]
        if len(task_files) < 2:
            pytest.skip("Not enough task files for test")

        # Create temp directory with subset of tasks
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, task_file in enumerate(task_files):
                dest = Path(tmpdir) / f"task-{i}.md"
                dest.write_text(task_file.read_text())

            # Run import
            result = subprocess.run(
                sqldown_command + [str(tmpdir), '--db', test_db, '--table', 'tasks'],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, f"Import failed: {result.stderr}"

        # Verify database
        db = Database(test_db)
        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == len(task_files)

        # Verify dynamic schema includes common fields
        columns = {col.name for col in db['tasks'].columns}

        # Should have frontmatter fields if tasks use them
        # (status, project, type are common in tasks)
        # But don't assert specific fields since schema is dynamic

        # Should have at least core fields + some dynamic ones
        assert len(columns) > 10  # Core fields + some dynamic fields

    @pytest.mark.skip(reason="CLI doesn't support gitignore filtering yet")
    def test_gitignore_filtering(self, sqldown_command, test_db):
        """Test that .gitignore filtering works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create gitignore
            (tmpdir / '.gitignore').write_text('ignored/\n*.tmp.md\n')

            # Create files
            (tmpdir / 'included.md').write_text('# Included\n\nContent.')
            (tmpdir / 'test.tmp.md').write_text('# Ignored\n\nContent.')

            ignored_dir = tmpdir / 'ignored'
            ignored_dir.mkdir()
            (ignored_dir / 'file.md').write_text('# Also Ignored\n\nContent.')

            # Run import
            result = subprocess.run(
                sqldown_command + [str(tmpdir), '--db', test_db, '--table', 'docs'],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Should only have 1 file
            db = Database(test_db)
            count = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            assert count == 1

            # Verify it's the right file
            row = db.execute("SELECT _path FROM docs").fetchone()
            assert 'included.md' in row[0]

    @pytest.mark.skip(reason="CLI doesn't support gitignore filtering yet")
    def test_no_gitignore_flag(self, sqldown_command, test_db):
        """Test --no-gitignore flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create gitignore
            (tmpdir / '.gitignore').write_text('*.md\n')

            # Create file that would be ignored
            (tmpdir / 'test.md').write_text('# Test\n\nContent.')

            # Run import with --no-gitignore
            result = subprocess.run(
                sqldown_command + [str(tmpdir), '--db', test_db, '--table', 'docs',
                 '--no-gitignore'],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Should have 1 file (gitignore was disabled)
            db = Database(test_db)
            count = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            assert count == 1

    def test_idempotent_import(self, sqldown_command, test_db):
        """Test that re-importing is idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / 'test.md'
            test_file.write_text('# Test\n\nContent.')

            # Import twice
            for _ in range(2):
                result = subprocess.run(
                    sqldown_command + [str(tmpdir), '--db', test_db, '--table', 'docs'],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0

            # Should still have only 1 row
            db = Database(test_db)
            count = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            assert count == 1

    def test_column_limit_detection(self, sqldown_command, test_db):
        """Test that column limit is detected (won't hit it with small test)."""
        # This test just verifies the import runs without crashing
        # The actual column limit detection would require 2000+ unique fields
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a file with many sections
            sections = '\n\n'.join([f'## Section {i}\n\nContent {i}.' for i in range(50)])
            test_file = tmpdir / 'test.md'
            test_file.write_text(f'# Test\n\n{sections}')

            result = subprocess.run(
                sqldown_command + [str(tmpdir), '--db', test_db, '--table', 'docs',
                                   '--top-sections', '0'],  # Extract all sections
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Verify it imported
            db = Database(test_db)
            count = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            assert count == 1

            # Verify sections were created
            columns = {col.name for col in db['docs'].columns}
            section_columns = [c for c in columns if c.startswith('section_')]
            assert len(section_columns) == 50

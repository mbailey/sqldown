"""Utility functions for sqldown."""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv, dotenv_values


def find_git_root(start_path: Path) -> Optional[Path]:
    """Find the git repository root by looking for .git directory.

    Args:
        start_path: Path to start searching from

    Returns:
        Path to git root directory, or None if not in a git repo
    """
    current = start_path.resolve()

    while current != current.parent:
        git_dir = current / '.git'
        if git_dir.exists():
            return current
        current = current.parent

    return None


def infer_table_name(path: Path) -> str:
    """Infer a table name from a directory path.

    Args:
        path: Directory path to infer table name from

    Returns:
        Sanitized table name suitable for SQL
    """
    # Get the last component of the path
    name = path.resolve().name

    # Handle special cases
    if not name or name == '/':
        name = 'docs'

    # Sanitize for SQL: keep only alphanumeric and underscores
    # Replace other characters with underscores
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # Ensure it starts with a letter (SQL requirement)
    if name and name[0].isdigit():
        name = 'table_' + name

    # Default if empty
    if not name:
        name = 'docs'

    return name.lower()


def get_default_database_path(working_dir: Path = None) -> Path:
    """Get the default database path using smart defaults.

    Looks for git root and places database there, otherwise uses current directory.

    Args:
        working_dir: Working directory to start from (defaults to cwd)

    Returns:
        Path to the default database file
    """
    if working_dir is None:
        working_dir = Path.cwd()

    # Try to find git root
    git_root = find_git_root(working_dir)

    if git_root:
        return git_root / '.sqldown.db'
    else:
        return working_dir / 'sqldown.db'  # Not hidden if not in git repo


def load_cascading_env(markdown_path: Path = None) -> Dict[str, Any]:
    """Load environment variables from cascading .sqldown.env files.

    Loads in order (each overrides previous):
    1. Project root .sqldown.env (if in git repo)
    2. Current working directory .sqldown.env
    3. Markdown directory .sqldown.env (if provided)
    4. System environment variables (SQLDOWN_* only)

    Args:
        markdown_path: Path to markdown directory being processed

    Returns:
        Dictionary of configuration values
    """
    config = {}
    cwd = Path.cwd()

    # 1. Load from project root (if in git repo)
    git_root = find_git_root(cwd)
    if git_root:
        env_file = git_root / '.sqldown.env'
        if env_file.exists():
            config.update(dotenv_values(env_file))

    # 2. Load from current working directory
    cwd_env = cwd / '.sqldown.env'
    if cwd_env.exists() and cwd_env != (git_root / '.sqldown.env' if git_root else None):
        config.update(dotenv_values(cwd_env))

    # 3. Load from markdown directory (if provided and different)
    if markdown_path:
        md_path = markdown_path.resolve()
        md_env = md_path / '.sqldown.env'
        if md_env.exists() and md_env not in [cwd_env, git_root / '.sqldown.env' if git_root else None]:
            config.update(dotenv_values(md_env))

    # 4. Override with system environment variables (SQLDOWN_* only)
    for key, value in os.environ.items():
        if key.startswith('SQLDOWN_'):
            config[key] = value

    return config


def parse_bool_env(value: str) -> bool:
    """Parse a boolean environment variable value.

    Args:
        value: String value to parse

    Returns:
        Boolean interpretation of the value
    """
    if not value:
        return False
    return value.lower() in ('true', '1', 'yes', 'on')


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a configuration value with type conversion.

    Args:
        config: Configuration dictionary
        key: Configuration key (without SQLDOWN_ prefix)
        default: Default value if not found

    Returns:
        Configuration value with appropriate type
    """
    # Try with SQLDOWN_ prefix first
    value = config.get(f'SQLDOWN_{key}', config.get(key, default))

    if value is None:
        return default

    # Type conversion based on default value type
    if isinstance(default, bool):
        return parse_bool_env(str(value))
    elif isinstance(default, int):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    elif isinstance(default, float):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    else:
        return value
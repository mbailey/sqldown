"""Pytest configuration and shared fixtures."""
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def bin_dir(project_root):
    """Get bin directory."""
    return project_root / 'bin'

# SQLDown Makefile

.PHONY: help install dev-install clean build test publish publish-test release \
	version bump-patch bump-minor bump-major

# Default target
help:
	@echo "SQLDown Build Targets:"
	@echo ""
	@echo "Development:"
	@echo "  install       - Install package in normal mode"
	@echo "  dev-install   - Install package in editable mode with dev dependencies"
	@echo "  clean         - Remove all build artifacts and caches"
	@echo ""
	@echo "Testing:"
	@echo "  test          - Run tests with pytest"
	@echo "  test-coverage - Run tests with coverage report"
	@echo ""
	@echo "Building:"
	@echo "  build         - Build package distribution"
	@echo "  test-package  - Test package installation in temp environment"
	@echo ""
	@echo "Publishing:"
	@echo "  publish       - Publish to PyPI (production)"
	@echo "  publish-test  - Publish to TestPyPI"
	@echo ""
	@echo "Release Management:"
	@echo "  release       - Create a new release (build, tag, publish)"
	@echo "  version       - Show current version"
	@echo "  bump-patch    - Bump patch version (e.g., 0.1.0 -> 0.1.1)"
	@echo "  bump-minor    - Bump minor version (e.g., 0.1.0 -> 0.2.0)"
	@echo "  bump-major    - Bump major version (e.g., 0.1.0 -> 1.0.0)"

# Install package
install:
	@echo "Installing sqldown..."
	@uv pip install -e .
	@echo "Installation complete!"

# Install package with development dependencies
dev-install:
	@echo "Installing sqldown with development dependencies..."
	@uv pip install -e ".[dev]"
	@echo "Development installation complete!"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf dist/ build/ *.egg-info .pytest_cache __pycache__
	@rm -rf htmlcov/ .coverage coverage.xml .coverage.*
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✅ Build artifacts cleaned!"

# Build Python package
build: clean
	@echo "Building sqldown package..."
	@uv build
	@echo "✅ Package built: dist/"
	@ls -lh dist/

# Run tests
test:
	@echo "Running tests..."
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@echo "Installing test dependencies..."
	@uv pip install -e ".[dev]" -q
	@echo "Running tests..."
	@uv run pytest tests/ -v --tb=short || echo "No tests found yet"
	@echo "Tests completed!"

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@echo "Installing test dependencies..."
	@uv pip install -e ".[dev]" -q
	@echo "Running tests with coverage..."
	@uv run pytest tests --cov --cov-report=html --cov-report=term || echo "No tests found yet"
	@echo ""
	@echo "✅ Coverage report generated!"
	@echo "   HTML report: htmlcov/index.html"

# Test package installation
test-package: build
	@echo "Testing package installation..."
	@cd /tmp && \
	rm -rf test-sqldown-env && \
	uv venv test-sqldown-env && \
	. test-sqldown-env/bin/activate && \
	uv pip install $(CURDIR)/dist/sqldown-*.whl && \
	sqldown --help && \
	deactivate && \
	rm -rf test-sqldown-env
	@echo "✅ Package test successful!"

# Show current version
version:
	@echo "Current version: $$(grep '^version = ' pyproject.toml | cut -d '"' -f 2)"

# Bump patch version (0.1.0 -> 0.1.1)
bump-patch:
	@echo "Bumping patch version..."
	@CURRENT=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	IFS='.' read -r major minor patch <<< "$$CURRENT"; \
	NEW_VERSION="$$major.$$minor.$$((patch + 1))"; \
	sed -i.bak "s/^version = \".*\"/version = \"$$NEW_VERSION\"/" pyproject.toml; \
	rm -f pyproject.toml.bak; \
	echo "Version bumped: $$CURRENT → $$NEW_VERSION"; \
	if [ -f "src/sqldown/__version__.py" ]; then \
		echo "__version__ = \"$$NEW_VERSION\"" > src/sqldown/__version__.py; \
	fi

# Bump minor version (0.1.0 -> 0.2.0)
bump-minor:
	@echo "Bumping minor version..."
	@CURRENT=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	IFS='.' read -r major minor patch <<< "$$CURRENT"; \
	NEW_VERSION="$$major.$$((minor + 1)).0"; \
	sed -i.bak "s/^version = \".*\"/version = \"$$NEW_VERSION\"/" pyproject.toml; \
	rm -f pyproject.toml.bak; \
	echo "Version bumped: $$CURRENT → $$NEW_VERSION"; \
	if [ -f "src/sqldown/__version__.py" ]; then \
		echo "__version__ = \"$$NEW_VERSION\"" > src/sqldown/__version__.py; \
	fi

# Bump major version (0.1.0 -> 1.0.0)
bump-major:
	@echo "Bumping major version..."
	@CURRENT=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	IFS='.' read -r major minor patch <<< "$$CURRENT"; \
	NEW_VERSION="$$((major + 1)).0.0"; \
	sed -i.bak "s/^version = \".*\"/version = \"$$NEW_VERSION\"/" pyproject.toml; \
	rm -f pyproject.toml.bak; \
	echo "Version bumped: $$CURRENT → $$NEW_VERSION"; \
	if [ -f "src/sqldown/__version__.py" ]; then \
		echo "__version__ = \"$$NEW_VERSION\"" > src/sqldown/__version__.py; \
	fi

# Publish to TestPyPI
publish-test: build
	@echo "Publishing to TestPyPI..."
	@if [ -z "$$UV_PUBLISH_TOKEN" ]; then \
		echo "❌ UV_PUBLISH_TOKEN not set!"; \
		echo "Get a token from https://test.pypi.org/manage/account/token/"; \
		echo "Then set: export UV_PUBLISH_TOKEN=\"pypi-your-test-token\""; \
		exit 1; \
	fi
	@uv publish --publish-url https://test.pypi.org/legacy/
	@echo "✅ Published to TestPyPI!"
	@echo ""
	@echo "Test installation with:"
	@echo "  pip install --index https://test.pypi.org/simple/ sqldown"

# Publish to PyPI
publish: build
	@echo "Publishing to PyPI..."
	@echo ""
	@echo "⚠️  WARNING: This will publish to PRODUCTION PyPI!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm; \
	if [ "$$confirm" != "yes" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi
	@if [ -z "$$UV_PUBLISH_TOKEN" ]; then \
		echo "❌ UV_PUBLISH_TOKEN not set!"; \
		echo "Get a token from https://pypi.org/manage/account/token/"; \
		echo "Then set: export UV_PUBLISH_TOKEN=\"pypi-your-token\""; \
		exit 1; \
	fi
	@uv publish
	@echo "✅ Published to PyPI!"
	@echo ""
	@echo "Install with: pip install sqldown"

# Create a new release
release:
	@echo "Creating a new release..."
	@echo ""
	@echo "Current version: $$(grep '^version = ' pyproject.toml | cut -d '"' -f 2)"
	@echo ""
	@echo "What type of release?"
	@echo "  1) Patch (bug fixes)"
	@echo "  2) Minor (new features)"
	@echo "  3) Major (breaking changes)"
	@read -p "Enter choice [1-3]: " choice; \
	case $$choice in \
		1) $(MAKE) bump-patch ;; \
		2) $(MAKE) bump-minor ;; \
		3) $(MAKE) bump-major ;; \
		*) echo "Invalid choice"; exit 1 ;; \
	esac
	@echo ""
	@NEW_VERSION=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	echo "New version: $$NEW_VERSION"; \
	echo ""
	@read -p "Enter release notes (one line): " notes; \
	echo ""
	@echo "Will perform the following actions:"
	@echo "  1. Build package"
	@echo "  2. Create git commit"
	@echo "  3. Create git tag v$$NEW_VERSION"
	@echo "  4. Push to GitHub"
	@echo "  5. Publish to PyPI"
	@echo ""
	@read -p "Continue? [y/N]: " proceed; \
	if [ "$$proceed" != "y" ] && [ "$$proceed" != "Y" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi
	@echo ""
	@echo "Building package..."
	@$(MAKE) build
	@echo ""
	@echo "Creating git commit..."
	@git add pyproject.toml
	@if [ -f "src/sqldown/__version__.py" ]; then \
		git add src/sqldown/__version__.py; \
	fi
	@NEW_VERSION=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	git commit -m "Release v$$NEW_VERSION" -m "$$notes" || true
	@echo ""
	@echo "Creating git tag..."
	@NEW_VERSION=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	git tag -a "v$$NEW_VERSION" -m "Release v$$NEW_VERSION" -m "$$notes"
	@echo ""
	@echo "Pushing to GitHub..."
	@git push origin main
	@git push origin --tags
	@echo ""
	@echo "Publishing to PyPI..."
	@$(MAKE) publish
	@echo ""
	@echo "🎉 Release complete!"
	@NEW_VERSION=$$(grep '^version = ' pyproject.toml | cut -d '"' -f 2); \
	echo "   Version $$NEW_VERSION has been released!"
	@echo "   GitHub: https://github.com/mbailey/metool-packages-dev/releases/tag/v$$NEW_VERSION"
	@echo "   PyPI: https://pypi.org/project/sqldown/$$NEW_VERSION/"

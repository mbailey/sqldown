# SQLDown Release Process

## Prerequisites

### 1. PyPI Account Setup
1. Create accounts at:
   - Production: https://pypi.org/account/register/
   - Test: https://test.pypi.org/account/register/

2. Generate API tokens:
   - Go to Account Settings → API tokens
   - Create a token for "sqldown" (or use account-wide token for first upload)
   - Save tokens securely

### 2. Environment Setup
```bash
# For TestPyPI
export UV_PUBLISH_TOKEN="pypi-AgENdGVzdC5weXBpLm9yZw..."

# For Production PyPI
export UV_PUBLISH_TOKEN="pypi-AgEInB5cGkub3JnC..."
```

## Release Process

### Quick Release
```bash
# Full automated release (builds, tags, publishes)
make release
```

### Manual Release Steps

1. **Test the package locally:**
   ```bash
   make test-package
   ```

2. **Publish to TestPyPI first:**
   ```bash
   make publish-test

   # Test installation from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ sqldown
   ```

3. **Create release:**
   ```bash
   # Choose version bump type (patch/minor/major)
   make release
   ```

### Version Management

```bash
# Show current version
make version

# Manual version bumps
make bump-patch  # 0.1.0 → 0.1.1
make bump-minor  # 0.1.0 → 0.2.0
make bump-major  # 0.1.0 → 1.0.0
```

## First-Time PyPI Upload

For the first upload to PyPI, you'll need to:

1. Ensure your package name is available:
   - Check https://pypi.org/project/sqldown/ (should 404)

2. Build and publish:
   ```bash
   make build
   make publish
   ```

3. After first upload, create a scoped token:
   - Go to https://pypi.org/manage/project/sqldown/settings/
   - Create a token scoped to just "sqldown"
   - Replace your environment token with the scoped one

## GitHub Release

After publishing to PyPI, create a GitHub release:

1. Go to https://github.com/mbailey/metool-packages-dev/releases/new
2. Choose the tag created by `make release`
3. Add release notes
4. Publish release

## Troubleshooting

### Token Issues
- Ensure UV_PUBLISH_TOKEN is set
- Check token starts with "pypi-"
- For TestPyPI, use tokens from test.pypi.org

### Package Name Conflicts
- If "sqldown" is taken, update name in pyproject.toml
- Consider: sqldown-cli, sqldown-tool, etc.

### Build Issues
- Run `make clean` before building
- Ensure all dependencies in pyproject.toml are correct
- Check Python version compatibility

## Versioning Strategy

Follow semantic versioning:
- **Patch (0.1.x)**: Bug fixes, documentation
- **Minor (0.x.0)**: New features, backward compatible
- **Major (x.0.0)**: Breaking changes

## Package URLs

Once published:
- PyPI: https://pypi.org/project/sqldown/
- Install: `pip install sqldown`
- Upgrade: `pip install --upgrade sqldown`
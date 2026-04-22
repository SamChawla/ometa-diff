# Pre-Commit & Quality Checks

Before considering ANY task complete, run this checklist:

## After Every File Edit

1. `ruff check src/ tests/ --fix` — fix lint errors
2. `ruff format src/ tests/` — format code

## After Every New Feature

1. Write or update tests FIRST — before marking feature done
2. `pytest tests/ -v` — all tests must pass
3. Check that all public functions have type hints and docstrings
4. Verify no `print()` statements leaked in (use Rich console or logging)

## Before Any Commit

1. `ruff check src/ tests/` — must exit 0
2. `ruff format --check src/ tests/` — must exit 0
3. `pytest tests/ -v` — must exit 0
4. Verify `pyproject.toml` is valid: `python -m build --no-isolation 2>&1 | head -5`
5. Check no secrets/tokens in committed files

## Before Publishing to PyPI

1. ALL of the above
2. Version in `pyproject.toml` updated
3. Version in `src/ometa_diff/__init__.py` matches
4. README.md has current usage examples
5. `pip install -e .` works in clean venv
6. `ometa-diff --help` runs without error
7. `pip install -e ".[mcp]"` works
8. `ometa-diff serve --help` runs without error

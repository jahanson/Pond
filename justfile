# List available commands
default:
    @just --list

# Install dependencies
install:
    uv pip install -e .

# Install all dependencies including dev tools
dev:
    uv pip install -e ".[test,dev]"
    uv run python -m spacy download en_core_web_lg

# Run linting checks
lint:
    uv run ruff check src tests

# Format code
format:
    uv run ruff format src tests

# Run type checking
type-check:
    uv run pyright

# Run tests
test:
    uv run pytest

# Run tests with verbose output
test-verbose:
    uv run pytest -vv

# Run all checks (lint, type-check, test)
check: lint type-check test

# Clean up generated files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    rm -rf .pytest_cache .coverage .ruff_cache

# Run the development server
server:
    uv run python -m pond.server

# Run a specific test file
test-file file:
    uv run pytest {{file}} -vv
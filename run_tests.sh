#!/usr/bin/env bash
# Run the poet-it unit test suite.
# Usage: ./run_tests.sh [pytest options]
#   ./run_tests.sh -v          verbose output
#   ./run_tests.sh -k spelling  run only tests matching "spelling"
#   ./run_tests.sh --tb=short   compact tracebacks

set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python &>/dev/null; then
    echo "Error: python not found on PATH." >&2
    exit 1
fi

if ! python -c "import pytest" &>/dev/null; then
    echo "Error: pytest is not installed. Run: pip install pytest" >&2
    exit 1
fi

python -m pytest tests/ "$@"

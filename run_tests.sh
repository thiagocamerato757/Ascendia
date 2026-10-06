#!/bin/bash

# Runs the full test suite across all apps.

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found (.venv). Aborting."
    exit 1
fi

echo "Running test suite..."

python manage.py test --verbosity=1

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "All tests passed."
else
    echo "Some tests failed."
fi

exit $exit_code

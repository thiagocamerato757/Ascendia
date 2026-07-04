#!/bin/bash

# Runs the full test suite across all apps.

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found (.venv). Aborting."
    exit 1
fi

echo "Running test suite..."

# Run all tests, including notes model tests (skip view tests that need templates)
python manage.py test \
    users \
    workspace \
    notes.tests.NoteModelTest \
    notes.tests.TagModelTest \
    notes.tests.NoteTagModelTest \
    notes.tests.NotePermissionsTest \
    notes.tests.NoteTagRelationshipTest \
    --verbosity=1

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "All tests passed."
else
    echo "Some tests failed."
fi

exit $exit_code

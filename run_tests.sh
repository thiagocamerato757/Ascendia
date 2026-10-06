#!/bin/bash

# Runs the full test suite across all apps.

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found (.venv). Aborting."
    exit 1
fi

# The project uses Postgres and reads configuration from .env (loaded by Django via
# python-dotenv). A .env must exist and Postgres must be reachable, e.g.:
#   cp .env.example .env   # fill DJANGO_SECRET_KEY, set POSTGRES_HOST=localhost
#   docker compose up db   # or any local Postgres on POSTGRES_HOST:POSTGRES_PORT
if [ ! -f .env ]; then
    echo "No .env found. Copy .env.example to .env and fill it in. Aborting."
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

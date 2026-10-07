"""Background tasks run by the worker (``manage.py db_worker``)."""
from __future__ import annotations

from django.db import transaction
from django_tasks import task

from . import ingestion


@task()
def ingest_source(source_id: int) -> None:
    ingestion.ingest(source_id)


def enqueue_ingestion(source_id: int) -> None:
    """Queue ingestion once the current transaction commits (the worker must see the row)."""
    transaction.on_commit(lambda: ingest_source.enqueue(source_id))

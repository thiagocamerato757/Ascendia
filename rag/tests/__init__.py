"""Fixtures for RAG tests: a notebook whose sources are ingested with the fake provider."""
from sources import ingestion
from sources.models import Source
from sources.tests import SourcesTestCase


class RagTestCase(SourcesTestCase):
    """Answers are generated inline (no threads, same transaction) and followed with a fast poll."""

    def setUp(self):
        super().setUp()
        from django.test import override_settings

        from rag import answer

        self._inline = override_settings(ASCENDIA_ANSWER_THREADS=0)
        self._inline.enable()
        self._poll, answer.POLL_SECONDS = answer.POLL_SECONDS, 0.01

    def tearDown(self):
        from rag import answer

        answer.POLL_SECONDS = self._poll
        self._inline.disable()
        super().tearDown()

    def add_text(self, title: str, text: str, notebook=None) -> Source:
        source = Source.objects.create(
            notebook=notebook or self.notebook, kind=Source.KIND_TEXT, title=title, text=text,
            content_hash=ingestion.content_hash(f'{title}:{text}'),
        )
        ingestion.ingest(source.pk)
        source.refresh_from_db()
        assert source.status == Source.STATUS_READY, source.error
        return source


def collect(async_iterable) -> list[str]:
    """Consume an async generator from sync test code (ORM calls stay on this thread)."""
    from asgiref.sync import async_to_sync

    async def run():
        return [chunk async for chunk in async_iterable]

    return async_to_sync(run)()


def events(chunks) -> list[tuple[str, dict]]:
    import json

    out = []
    for raw in chunks:
        if raw.startswith(':'):
            continue  # keepalive comment
        lines = dict(line.split(': ', 1) for line in raw.strip().split('\n'))
        out.append((lines['event'], json.loads(lines['data'])))
    return out


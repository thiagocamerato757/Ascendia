"""Fixtures for RAG tests: a notebook whose sources are ingested with the fake provider."""
from sources import ingestion
from sources.models import Source
from sources.tests import SourcesTestCase


class RagTestCase(SourcesTestCase):
    def add_text(self, title: str, text: str, notebook=None) -> Source:
        source = Source.objects.create(
            notebook=notebook or self.notebook, kind=Source.KIND_TEXT, title=title, text=text,
            content_hash=ingestion.content_hash(f'{title}:{text}'),
        )
        ingestion.ingest(source.pk)
        source.refresh_from_db()
        assert source.status == Source.STATUS_READY, source.error
        return source

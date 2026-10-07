"""Source ingestion: parse → chunk → embed → index (spec §7.1).

Runs in the background worker (``sources.tasks``). Idempotent: a run replaces
the source's chunks in one transaction, so retrying never leaves duplicates.
Reindexing (new embedding model or language) is simply another run: the
original file stays in private storage. A failure marks only that source as failed, with a safe message.
Source text is never logged (spec §11).
"""
from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import override

from llm import client
from llm import constants as c
from llm.models import NotebookSettings
from llm.providers import ProviderError

from .chunking import chunk_pages
from .models import Chunk, Source
from .parsing import SourceParseError, extract_pdf, extract_text

logger = logging.getLogger('ascendia.sources')

#: Postgres text search configuration for each answer language (spec §7.2).
SEARCH_CONFIG_BY_LANGUAGE = {
    c.LANGUAGE_PT_BR: 'portuguese',
    c.LANGUAGE_EN: 'english',
    c.LANGUAGE_ES: 'spanish',
}


def content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def search_config_for(nb_settings: NotebookSettings) -> str:
    return SEARCH_CONFIG_BY_LANGUAGE.get(nb_settings.language, 'simple')


def _notebook_settings(source: Source) -> NotebookSettings:
    nb_settings, _created = NotebookSettings.objects.get_or_create(notebook=source.notebook)
    return nb_settings


def _fail(source: Source, message: str) -> None:
    Source.objects.filter(pk=source.pk).update(status=Source.STATUS_FAILED, error=message[:500])


def _read_pages(source: Source):
    if source.kind == Source.KIND_TEXT:
        return extract_text(source.text)
    with source.file.open('rb') as fh:
        return extract_pdf(fh.read())


def _store_chunks(source: Source, drafts, vectors, model: str, config: str) -> None:
    with transaction.atomic():
        Chunk.objects.filter(source=source).delete()
        Chunk.objects.bulk_create([
            Chunk(
                source=source, notebook_id=source.notebook_id, order=i, text=d.text, page=d.page,
                section=d.section, embedding=vec, embedding_model=model, embedding_dim=len(vec),
                search_config=config,
            )
            for i, (d, vec) in enumerate(zip(drafts, vectors))
        ])
        # One config per source; SearchVector needs it as a literal.
        Chunk.objects.filter(source=source).update(search_vector=SearchVector('text', config=config))


def ingest(source_id: int) -> None:
    """Parse, chunk, embed and index one source. Never raises for expected failures."""
    source = Source.objects.select_related('notebook__user').filter(pk=source_id).first()
    if source is None:
        return  # deleted before the worker got to it
    Source.objects.filter(pk=source.pk).update(status=Source.STATUS_PROCESSING, error='')
    nb_settings = _notebook_settings(source)
    # Messages stored for the user follow the site's default language.
    with override(settings.LANGUAGE_CODE):
        try:
            pages = _read_pages(source)
            drafts = chunk_pages(pages, size=settings.ASCENDIA_CHUNK_SIZE, overlap=settings.ASCENDIA_CHUNK_OVERLAP)
            if not drafts:
                _fail(source, _('No text was found in this source. Scanned PDFs need OCR first.'))
                return
            result = client.embed(nb_settings, [d.text for d in drafts], purpose='passage')
            if len(result.vectors) != len(drafts):
                raise ProviderError(_('The embedding provider returned an unexpected number of vectors.'))
            _store_chunks(source, drafts, result.vectors, nb_settings.embedding_model, search_config_for(nb_settings))
        except SourceParseError as exc:
            _fail(source, str(exc))
            return
        except ProviderError as exc:
            _fail(source, exc.user_message)
            return
        except Exception:  # noqa: BLE001 - unexpected: log type/trace without content, fail safely
            logger.exception('Ingestion failed for source %s', source.pk)
            _fail(source, _('Something went wrong while processing this source. Try again.'))
            return

    page_count = sum(1 for p in pages if p.page is not None)
    Source.objects.filter(pk=source.pk).update(
        status=Source.STATUS_READY, error='', page_count=page_count,
        embedding_model=nb_settings.embedding_model,
    )


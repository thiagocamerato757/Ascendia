"""Parsing, chunking and ingestion against real Postgres + pgvector."""
from django.test import SimpleTestCase, override_settings
from django.utils.translation import gettext

from llm.providers import FAKE_EMBEDDING_DIM, ProviderError
from sources import ingestion
from sources.chunking import chunk_pages
from sources.models import Chunk, Source
from sources.parsing import PageText, SourceParseError, extract_pdf, validate_pdf

from . import SourcesTestCase, make_pdf


class ParsingTests(SimpleTestCase):
    def test_extracts_text_per_page_with_toc_sections(self):
        data = make_pdf(['Introducao a celula.', 'A mitocondria produz energia.', 'Fim.'],
                        toc=[[1, 'Celula', 1], [1, 'Organelas', 2]])
        pages = extract_pdf(data)
        self.assertEqual([p.page for p in pages], [1, 2, 3])
        self.assertIn('mitocondria', pages[1].text)
        self.assertEqual([p.section for p in pages], ['Celula', 'Organelas', 'Organelas'])

    def test_rejects_non_pdf_content_even_with_pdf_name(self):
        with self.assertRaises(SourceParseError):
            validate_pdf(b'<html>not a pdf</html>', max_pages=10)

    def test_rejects_damaged_pdf(self):
        with self.assertRaises(SourceParseError):
            validate_pdf(b'%PDF-1.7 garbage that is not a document', max_pages=10)

    def test_enforces_page_limit(self):
        with self.assertRaises(SourceParseError):
            validate_pdf(make_pdf(['a', 'b', 'c']), max_pages=2)


class ChunkingTests(SimpleTestCase):
    def test_never_crosses_pages_and_respects_size(self):
        pages = [PageText(1, 'A', 'p1 ' * 300), PageText(2, 'B', 'p2 ' * 300)]
        chunks = chunk_pages(pages, size=200, overlap=40)
        self.assertTrue(all(len(c.text) <= 200 for c in chunks))
        self.assertEqual({c.page for c in chunks if 'p1' in c.text}, {1})
        self.assertEqual({c.section for c in chunks if c.page == 2}, {'B'})

    def test_overlap_repeats_the_end_of_the_previous_chunk(self):
        text = '\n\n'.join(f'Paragrafo numero {i} com algumas palavras.' for i in range(30))
        chunks = chunk_pages([PageText(1, '', text)], size=150, overlap=50)
        self.assertGreater(len(chunks), 2)
        first_tail = chunks[0].text.split()[-1]
        self.assertIn(first_tail, chunks[1].text.split()[:12])

    def test_joins_hard_wrapped_lines_and_hyphenation(self):
        chunks = chunk_pages([PageText(1, '', 'foto-\nssintese ocorre\nnas folhas.')], size=500, overlap=0)
        self.assertEqual(chunks[0].text, 'fotossintese ocorre nas folhas.')

    def test_empty_text_gives_no_chunks(self):
        self.assertEqual(chunk_pages([PageText(1, '', '   \n\n ')], size=100, overlap=10), [])


class IngestionTests(SourcesTestCase):
    def _pdf_source(self, pages, **kw):
        from django.core.files.base import ContentFile

        data = make_pdf(pages, **kw)
        source = Source(notebook=self.notebook, kind=Source.KIND_PDF, title='bio.pdf',
                        content_hash=ingestion.content_hash(data))
        source.file.save('bio.pdf', ContentFile(data), save=True)
        return source

    def test_pdf_becomes_ready_chunks_with_page_vector_and_fulltext(self):
        source = self._pdf_source(['A fotossintese ocorre nos cloroplastos.', 'A mitocondria produz ATP.'])
        ingestion.ingest(source.pk)
        source.refresh_from_db()
        self.assertEqual(source.status, Source.STATUS_READY)
        self.assertEqual(source.page_count, 2)
        self.assertEqual(source.embedding_model, self.nb_settings.embedding_model)
        chunks = list(Chunk.objects.filter(source=source))
        self.assertEqual([c.page for c in chunks], [1, 2])
        self.assertTrue(all(c.embedding_dim == FAKE_EMBEDDING_DIM for c in chunks))
        self.assertEqual({c.search_config for c in chunks}, {'portuguese'})
        from django.contrib.postgres.search import SearchQuery

        hits = Chunk.objects.filter(source=source, search_vector=SearchQuery('mitocondria', config='portuguese'))
        self.assertEqual([c.page for c in hits], [2])
        self.assertEqual(self.fake.last_embed_call['input_type'], None)  # OpenAI: no input_type

    def test_rerun_is_idempotent(self):
        source = self._pdf_source(['Um texto qualquer.'])
        ingestion.ingest(source.pk)
        ingestion.ingest(source.pk)
        self.assertEqual(Chunk.objects.filter(source=source).count(), 1)

    def test_text_source_has_no_page(self):
        source = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='notas',
                                       text='Revisao de genetica mendeliana.', content_hash='x')
        ingestion.ingest(source.pk)
        chunk = Chunk.objects.get(source=source)
        self.assertIsNone(chunk.page)
        source.refresh_from_db()
        self.assertEqual(source.page_count, 0)

    def test_provider_failure_marks_only_that_source_failed(self):
        ok = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='ok', text='a',
                                   content_hash='1')
        ingestion.ingest(ok.pk)
        self.fake.fail_with = 'A chave de API do provedor é inválida ou foi recusada.'
        bad = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='bad', text='b',
                                    content_hash='2')
        ingestion.ingest(bad.pk)
        ok.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(ok.status, Source.STATUS_READY)
        self.assertEqual(bad.status, Source.STATUS_FAILED)
        self.assertIn('chave', bad.error)
        self.assertFalse(Chunk.objects.filter(source=bad).exists())

    def test_pdf_without_text_fails_with_guidance(self):
        source = self._pdf_source([''])
        ingestion.ingest(source.pk)
        source.refresh_from_db()
        self.assertEqual(source.status, Source.STATUS_FAILED)
        self.assertEqual(source.error, gettext('No text was found in this source. Scanned PDFs need OCR first.'))

    def test_language_picks_fulltext_config(self):
        self.nb_settings.language = 'en'
        self.nb_settings.save()
        source = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='t',
                                       text='Photosynthesis happens in leaves.', content_hash='en')
        ingestion.ingest(source.pk)
        self.assertEqual(Chunk.objects.get(source=source).search_config, 'english')

    def test_unexpected_error_does_not_leak_details(self):
        source = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='t', text='x',
                                       content_hash='boom')
        with self.assertLogs('ascendia.sources', level='ERROR'):
            with override_settings(ASCENDIA_CHUNK_SIZE=0):  # forces ValueError inside chunking
                ingestion.ingest(source.pk)
        source.refresh_from_db()
        self.assertEqual(source.status, Source.STATUS_FAILED)
        self.assertNotIn('size', source.error)

    def test_deleting_a_source_removes_its_file(self):
        source = self._pdf_source(['texto'])
        path = source.file.path
        source.delete()
        import os
        self.assertFalse(os.path.exists(path))


class ProviderErrorSafety(SourcesTestCase):
    def test_vector_count_mismatch_is_a_safe_failure(self):
        class Short(type(self.fake)):
            def embed(self, model, texts, **kw):
                res = super().embed(model, texts, **kw)
                res.vectors = res.vectors[:-1]
                return res

        from llm import client

        client.set_provider_override(Short())
        source = Source.objects.create(notebook=self.notebook, kind=Source.KIND_TEXT, title='t', text='a b c',
                                       content_hash='mm')
        ingestion.ingest(source.pk)
        source.refresh_from_db()
        self.assertEqual(source.status, Source.STATUS_FAILED)
        self.assertTrue(source.error)
        self.assertIsInstance(ProviderError('x'), Exception)

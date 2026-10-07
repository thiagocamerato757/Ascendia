from django.test import SimpleTestCase

from rag.fusion import reciprocal_rank_fusion
from rag.retrieval import _base_queryset, fulltext_ids, retrieve
from sources.models import Chunk, Source

from . import RagTestCase


class RRFTests(SimpleTestCase):
    def test_item_high_in_both_lists_wins(self):
        fused = reciprocal_rank_fusion([['a', 'b', 'c'], ['b', 'a', 'd']], k=60)
        self.assertEqual([i for i, _ in fused][:2], ['a', 'b'])  # tie on score -> first seen
        self.assertEqual({i for i, _ in fused}, {'a', 'b', 'c', 'd'})

    def test_scores_follow_the_formula(self):
        fused = dict(reciprocal_rank_fusion([['x'], ['y', 'x']], k=10))
        self.assertAlmostEqual(fused['x'], 1 / 11 + 1 / 12)
        self.assertAlmostEqual(fused['y'], 1 / 11)

    def test_weights_and_duplicates(self):
        fused = dict(reciprocal_rank_fusion([['a', 'a'], ['b']], k=0, weights=[1.0, 3.0]))
        self.assertAlmostEqual(fused['a'], 1.0)  # the duplicate in the same list counts once
        self.assertAlmostEqual(fused['b'], 3.0)

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([['a']], weights=[1, 2])
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([['a']], k=-1)


class RetrievalTests(RagTestCase):
    def setUp(self):
        super().setUp()
        self.cell = self.add_text('Celula', 'A mitocondria produz energia na forma de ATP.')
        self.plant = self.add_text('Plantas', 'A fotossintese ocorre nos cloroplastos das folhas.')
        self.history = self.add_text('Historia', 'A Revolucao Francesa comecou em 1789 com a queda da Bastilha.')

    def test_best_chunk_comes_first_with_both_signals(self):
        results = retrieve(self.nb_settings, 'mitocondria energia')
        self.assertEqual(results[0].chunk.source, self.cell)
        self.assertEqual((results[0].fulltext_rank, results[0].vector_rank), (1, 1))
        self.assertEqual(self.fake.last_embed_call['texts'], ['mitocondria energia'])

    def test_vector_search_finds_what_fulltext_misses(self):
        # websearch_to_tsquery ANDs the terms: "celular" is in no chunk, so full-text finds nothing.
        results = retrieve(self.nb_settings, 'mitocondria energia celular')
        self.assertEqual(results[0].chunk.source, self.cell)
        self.assertIsNone(results[0].fulltext_rank)
        self.assertEqual(results[0].vector_rank, 1)

    def test_only_current_embedding_model(self):
        Chunk.objects.filter(source=self.cell).update(embedding_model='old-model')
        sources = {r.chunk.source_id for r in retrieve(self.nb_settings, 'mitocondria energia')}
        self.assertNotIn(self.cell.id, sources)

    def test_only_ready_sources(self):
        Source.objects.filter(pk=self.cell.pk).update(status=Source.STATUS_PROCESSING)
        sources = {r.chunk.source_id for r in retrieve(self.nb_settings, 'mitocondria energia')}
        self.assertNotIn(self.cell.id, sources)

    def test_selected_sources_only(self):
        results = retrieve(self.nb_settings, 'mitocondria energia', source_ids=[self.plant.id])
        self.assertEqual({r.chunk.source_id for r in results}, {self.plant.id})

    def test_never_returns_other_notebooks(self):
        from workspace.models import Notebook

        other_nb = Notebook.objects.create(user=self.other, title='Outro')
        from llm.models import NotebookSettings
        NotebookSettings.objects.create(notebook=other_nb)
        self.add_text('Segredo', 'A mitocondria do vizinho produz energia secreta.', notebook=other_nb)
        sources = {r.chunk.source.notebook_id for r in retrieve(self.nb_settings, 'mitocondria energia')}
        self.assertEqual(sources, {self.notebook.id})

    def test_fulltext_lists_each_chunk_once(self):
        # Regression: DISTINCT over search_config used to include Meta.ordering
        # columns, running the search once per chunk and repeating ids.
        ids = fulltext_ids(_base_queryset(self.nb_settings), 'mitocondria energia', 40)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [self.cell.chunks.get().id])

    def test_top_k(self):
        self.assertEqual(len(retrieve(self.nb_settings, 'a', top_k=2)), 2)

    def test_nothing_to_search_skips_the_embedding_call(self):
        Source.objects.all().delete()
        self.fake.embed_calls.clear()
        self.assertEqual(retrieve(self.nb_settings, 'qualquer coisa'), [])
        self.assertEqual(retrieve(self.nb_settings, '   '), [])
        self.assertEqual(self.fake.embed_calls, [])

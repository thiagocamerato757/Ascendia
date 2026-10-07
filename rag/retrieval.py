"""Hybrid retrieval: Postgres full-text + pgvector, fused with RRF (spec §7.2).

Both searches run over the same filtered set of chunks:

* only the owner's notebook (the caller passes its settings);
* only sources that are ``ready``;
* only chunks embedded with the notebook's **current** embedding model, so
  vectors of different models are never compared (spec D5);
* optionally, only the sources the user selected.

The vector search is exact (no ANN index): personal corpora are small and an
HNSW index needs a fixed dimension. Phase 4 measures before adding one (D10).
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance

from llm import client
from sources.models import Chunk, Source

from .fusion import reciprocal_rank_fusion


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float  # fused RRF score
    fulltext_rank: int | None  # 1-based position in the full-text list, if present
    vector_rank: int | None  # 1-based position in the vector list, if present


def _base_queryset(nb_settings, source_ids=None):
    qs = Chunk.objects.filter(
        notebook_id=nb_settings.notebook_id,
        embedding_model=nb_settings.embedding_model,
        source__status=Source.STATUS_READY,
    )
    if source_ids is not None:
        qs = qs.filter(source_id__in=list(source_ids))
    return qs


def fulltext_ids(qs, question: str, limit: int) -> list[int]:
    """Chunk ids matching ``question``, best first, each with its own language config."""
    scored: list[tuple[float, int]] = []
    # order_by() clears Chunk.Meta.ordering; otherwise DISTINCT would also
    # cover the ordering columns and repeat each config once per chunk.
    for config in qs.order_by().values_list('search_config', flat=True).distinct():
        query = SearchQuery(question, search_type='websearch', config=config)
        rows = (
            qs.filter(search_config=config, search_vector=query)
            .annotate(rank=SearchRank('search_vector', query, cover_density=True))
            .order_by('-rank', 'id')
            .values_list('rank', 'id')[:limit]
        )
        scored.extend(rows)
    scored.sort(key=lambda r: (-r[0], r[1]))
    return list(dict.fromkeys(chunk_id for _rank, chunk_id in scored))[:limit]


def vector_ids(qs, query_vector: list[float], limit: int) -> list[int]:
    """Chunk ids nearest to ``query_vector`` by cosine distance."""
    return list(
        qs.filter(embedding_dim=len(query_vector))
        .annotate(distance=CosineDistance('embedding', query_vector))
        .order_by('distance', 'id')
        .values_list('id', flat=True)[:limit]
    )


def retrieve(nb_settings, question: str, *, source_ids=None, top_k: int | None = None) -> list[RetrievedChunk]:
    """The best ``top_k`` chunks for ``question``. Raises ProviderError if embedding fails."""
    question = (question or '').strip()
    if not question:
        return []
    qs = _base_queryset(nb_settings, source_ids)
    if not qs.exists():
        return []

    candidates = settings.ASCENDIA_RAG_CANDIDATES
    top_k = top_k or settings.ASCENDIA_RAG_TOP_K
    text_ranking = fulltext_ids(qs, question, candidates)
    query_vector = client.embed(nb_settings, [question], purpose='query').vectors[0]
    vector_ranking = vector_ids(qs, query_vector, candidates)

    fused = reciprocal_rank_fusion([text_ranking, vector_ranking], k=settings.ASCENDIA_RAG_RRF_K)[:top_k]
    text_pos = {cid: i for i, cid in enumerate(text_ranking, start=1)}
    vec_pos = {cid: i for i, cid in enumerate(vector_ranking, start=1)}
    chunks = Chunk.objects.select_related('source').in_bulk([cid for cid, _score in fused])
    return [
        RetrievedChunk(chunk=chunks[cid], score=score, fulltext_rank=text_pos.get(cid), vector_rank=vec_pos.get(cid))
        for cid, score in fused
        if cid in chunks
    ]

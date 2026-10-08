"""Sources added to a notebook and the chunks they are split into (spec §4, §7.1)."""
from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField

from .storage import get_source_storage, source_upload_to


class Source(models.Model):
    """A PDF or pasted text in a notebook, plus its ingestion status."""

    KIND_PDF = 'pdf'
    KIND_TEXT = 'text'
    KIND_MARKDOWN = 'markdown'
    KIND_CHOICES = [(KIND_PDF, _('PDF')), (KIND_TEXT, _('Text')), (KIND_MARKDOWN, _('Markdown'))]
    #: Kinds whose original file is kept in private storage (re-read on reindex).
    FILE_KINDS = (KIND_PDF, KIND_MARKDOWN)

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_PROCESSING, _('Processing')),
        (STATUS_READY, _('Ready')),
        (STATUS_FAILED, _('Failed')),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_PROCESSING)

    notebook = models.ForeignKey('workspace.Notebook', on_delete=models.CASCADE, related_name='sources')
    kind = models.CharField(_('Type'), max_length=10, choices=KIND_CHOICES)
    title = models.CharField(_('Title'), max_length=255)
    file = models.FileField(storage=get_source_storage, upload_to=source_upload_to, blank=True)
    text = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    #: User-facing, safe message (never a stack trace or provider payload).
    error = models.CharField(max_length=500, blank=True, default='')
    page_count = models.PositiveIntegerField(default=0)
    #: SHA-256 of the content; the same content is not added twice to a notebook.
    content_hash = models.CharField(max_length=64)
    #: Embedding model the current chunks were indexed with (spec D5).
    embedding_model = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['notebook', 'content_hash'], name='source_unique_content_per_notebook'),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES


class Chunk(models.Model):
    """A passage of a source, with its page, embedding and full-text vector.

    ``embedding`` is a ``vector`` column without a fixed dimension: notebooks
    use different embedding models. Every query filters on ``embedding_model``
    so vectors of different models are never compared (spec D5).
    """

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='chunks')
    #: Denormalized for owner/notebook filtering without a join.
    notebook = models.ForeignKey('workspace.Notebook', on_delete=models.CASCADE, related_name='chunks')
    order = models.PositiveIntegerField()
    text = models.TextField()
    page = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=255, blank=True, default='')
    embedding = VectorField(null=True, blank=True)
    embedding_model = models.CharField(max_length=120, blank=True, default='')
    embedding_dim = models.PositiveIntegerField(default=0)
    search_vector = SearchVectorField(null=True)
    #: Postgres text search configuration used for search_vector (e.g. 'portuguese').
    search_config = models.CharField(max_length=20, default='simple')

    class Meta:
        ordering = ['source_id', 'order']
        indexes = [
            models.Index(fields=['notebook', 'embedding_model'], name='chunk_notebook_model_idx'),
            GinIndex(fields=['search_vector'], name='chunk_search_vector_gin'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['source', 'order'], name='chunk_unique_order_per_source'),
        ]

    def __str__(self) -> str:
        return f'{self.source} #{self.order}'

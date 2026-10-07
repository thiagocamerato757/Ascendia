"""Conversation, messages and their citations (spec §4)."""
from __future__ import annotations

from django.db import models


class Conversation(models.Model):
    """The chat of a notebook. One per notebook for now; the FK allows more later."""

    notebook = models.ForeignKey('workspace.Notebook', on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'Conversation {self.pk} ({self.notebook})'

    @classmethod
    def for_notebook(cls, notebook) -> Conversation:
        conversation = cls.objects.filter(notebook=notebook).first()
        return conversation or cls.objects.create(notebook=notebook)


class Message(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [(ROLE_USER, 'user'), (ROLE_ASSISTANT, 'assistant')]

    STATUS_PENDING = 'pending'
    STATUS_STREAMING = 'streaming'
    STATUS_COMPLETE = 'complete'
    STATUS_STOPPED = 'stopped'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [(s, s) for s in (STATUS_PENDING, STATUS_STREAMING, STATUS_COMPLETE, STATUS_STOPPED,
                                       STATUS_ERROR)]
    OPEN_STATUSES = (STATUS_PENDING, STATUS_STREAMING)

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    #: Final text with only validated [n] markers (assistant) or the question (user).
    content = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_COMPLETE)
    #: Safe, user-facing error message (assistant only).
    error = models.CharField(max_length=500, blank=True, default='')
    #: Sources the user restricted the search to (None = all ready sources).
    source_filter = models.JSONField(null=True, blank=True)
    #: True when the answer is the standard "not found in the sources" message.
    not_found = models.BooleanField(default=False)
    # Usage (spec §5): what the answer cost to produce.
    provider = models.CharField(max_length=20, blank=True, default='')
    model = models.CharField(max_length=120, blank=True, default='')
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    cost_usd = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self) -> str:
        return f'{self.role} message {self.pk}'

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES


class MessageCitation(models.Model):
    """A passage given to the model as ``[n]`` for an answer.

    Stores a snapshot (text, title, page): reindexing recreates chunks, and an
    old answer's citations must keep pointing at what the model actually saw.
    """

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='citations')
    n = models.PositiveSmallIntegerField()
    chunk = models.ForeignKey('sources.Chunk', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    source = models.ForeignKey('sources.Source', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    source_title = models.CharField(max_length=255)
    page = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=255, blank=True, default='')
    text = models.TextField()
    #: Whether the final answer actually cites this passage.
    cited = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)

    class Meta:
        ordering = ['n']
        constraints = [models.UniqueConstraint(fields=['message', 'n'], name='citation_unique_n_per_message')]

    def __str__(self) -> str:
        return f'[{self.n}] {self.source_title}'

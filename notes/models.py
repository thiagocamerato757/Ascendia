from django.db import models
from django.contrib.auth.models import User
from workspace.models import Notebook


class Note(models.Model):
    """Individual note within a notebook"""
    notebook = models.ForeignKey(Notebook, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['-is_pinned', 'order', '-updated_at']

    def __str__(self):
        return self.title


class Tag(models.Model):
    """Tags for organizing notes"""
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tags')
    color = models.CharField(max_length=7, default='#06b6d4')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['name', 'user']
        ordering = ['name']

    def __str__(self):
        return self.name


class NoteTag(models.Model):
    """Many-to-many relationship between notes and tags"""
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='note_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='note_tags')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['note', 'tag']

    def __str__(self):
        return f"{self.note.title} - {self.tag.name}"

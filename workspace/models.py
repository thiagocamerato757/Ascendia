from django.db import models
from django.contrib.auth.models import User


class Notebook(models.Model):
    """Virtual notebook similar to NotebookLM"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notebooks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#06b6d4')  # Aurora cyan default
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_favorite = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Source


@receiver(post_delete, sender=Source)
def remove_source_file(sender, instance: Source, **kwargs) -> None:
    """Delete the stored file with its source (also on notebook cascade)."""
    if instance.file:
        instance.file.delete(save=False)

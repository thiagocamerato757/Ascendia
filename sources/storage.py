"""Private storage for uploaded source files (spec §11).

Files live under ``settings.ASCENDIA_SOURCES_ROOT``, outside MEDIA_ROOT, and the
storage has no base URL: nothing here is ever served directly. Stored names are
random (UUID) so user-supplied file names never reach the file system.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.utils.functional import LazyObject, empty


class _SourceStorage(LazyObject):
    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.ASCENDIA_SOURCES_ROOT, base_url=None)


source_storage = _SourceStorage()


@receiver(setting_changed)
def _reset_storage(*, setting, **kwargs) -> None:
    """Follow ASCENDIA_SOURCES_ROOT overrides (tests use a temporary directory)."""
    if setting == 'ASCENDIA_SOURCES_ROOT':
        source_storage._wrapped = empty


def get_source_storage():
    """Callable for FileField(storage=...) so migrations don't capture a path."""
    return source_storage


#: Stored extension per source kind (never taken from the user's file name).
_EXTENSIONS = {'pdf': 'pdf', 'markdown': 'md'}


def source_upload_to(instance, filename: str) -> str:
    """``<notebook id>/<uuid>.<pdf|md>`` — the original name is kept only in the DB."""
    return f'{instance.notebook_id}/{uuid.uuid4().hex}.{_EXTENSIONS.get(instance.kind, "bin")}'

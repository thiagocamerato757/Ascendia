"""Private storage for uploaded source files (spec §11).

Files live under ``settings.ASCENDIA_SOURCES_ROOT``, outside MEDIA_ROOT, and the
storage has no base URL: nothing here is ever served directly. Stored names are
random (UUID) so user-supplied file names never reach the file system.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import LazyObject


class _SourceStorage(LazyObject):
    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.ASCENDIA_SOURCES_ROOT, base_url=None)


source_storage = _SourceStorage()


def get_source_storage():
    """Callable for FileField(storage=...) so migrations don't capture a path."""
    return source_storage


def source_upload_to(instance, filename: str) -> str:
    """``<notebook id>/<uuid>.pdf`` — the original name is kept only in the DB."""
    return f'{instance.notebook_id}/{uuid.uuid4().hex}.pdf'

"""Sources panel of the notebook page: add, list, retry, delete and reindex sources.

Every view is scoped to the notebook's owner (spec §11). The panel is one
partial (``sources/_panel.html``) that HTMX swaps in place after each action;
while a source is pending or processing, the list polls for status.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from core.ratelimit import rate_limited
from llm.models import NotebookSettings
from workspace.models import Notebook

from .forms import PdfUploadForm, TextSourceForm
from .ingestion import content_hash
from .models import Source
from .tasks import enqueue_ingestion


def _notebook(request, notebook_id: int) -> Notebook:
    return get_object_or_404(Notebook, id=notebook_id, user=request.user)


def _source(request, source_id: int) -> Source:
    return get_object_or_404(Source.objects.select_related('notebook'), id=source_id, notebook__user=request.user)


def panel_context(notebook: Notebook, *, notice: dict | None = None, text_form=None) -> dict:
    """Everything the sources panel needs (also used by the notebook page)."""
    sources = list(notebook.sources.all())
    nb_settings = NotebookSettings.objects.filter(notebook=notebook).first()
    current_model = nb_settings.embedding_model if nb_settings else ''
    stale = [s for s in sources if s.status == Source.STATUS_READY and s.embedding_model != current_model]
    return {
        'notebook': notebook,
        'sources': sources,
        'any_active': any(s.is_active for s in sources),
        'has_ready': any(s.status == Source.STATUS_READY for s in sources),
        'stale_count': len(stale),
        'notice': notice,
        'text_form': text_form or TextSourceForm(),
    }


def _panel(request, notebook: Notebook, **kwargs):
    return render(request, 'sources/_panel.html', panel_context(notebook, **kwargs))


def _create(notebook: Notebook, **fields) -> Source | None:
    """Create a source and queue it; None when the same content is already there."""
    try:
        with transaction.atomic():
            source = Source.objects.create(notebook=notebook, **fields)
    except IntegrityError:
        return None
    enqueue_ingestion(source.pk)
    return source


@login_required
@require_GET
def panel(request, notebook_id: int):
    return _panel(request, _notebook(request, notebook_id))


@login_required
@require_POST
@rate_limited('upload', 'ASCENDIA_RATE_UPLOAD_PER_MIN')
def upload_pdf(request, notebook_id: int):
    notebook = _notebook(request, notebook_id)
    form = PdfUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        message = form.errors['file'][0] if 'file' in form.errors else _('Choose a PDF file.')
        return _panel(request, notebook, notice={'variant': 'danger', 'title': _("Couldn't add the PDF"),
                                                  'message': message})
    upload = form.cleaned_data['file']
    title = upload.name.rsplit('/', 1)[-1][:255]
    source = _create(notebook, kind=Source.KIND_PDF, title=title, file=upload,
                     content_hash=content_hash(form.data_bytes), page_count=form.page_count)
    if source is None:
        return _panel(request, notebook, notice={'variant': 'warning', 'title': _('Already added'),
                                                  'message': _('This PDF is already in the notebook.')})
    return _panel(request, notebook)


@login_required
@require_POST
@rate_limited('upload', 'ASCENDIA_RATE_UPLOAD_PER_MIN')
def add_text(request, notebook_id: int):
    notebook = _notebook(request, notebook_id)
    form = TextSourceForm(request.POST)
    if not form.is_valid():
        return _panel(request, notebook, text_form=form)
    text = form.cleaned_data['text']
    source = _create(notebook, kind=Source.KIND_TEXT, title=form.cleaned_data['title'], text=text,
                     content_hash=content_hash(text))
    if source is None:
        return _panel(request, notebook, notice={'variant': 'warning', 'title': _('Already added'),
                                                  'message': _('This text is already in the notebook.')})
    return _panel(request, notebook)


@login_required
@require_POST
def delete_source(request, source_id: int):
    source = _source(request, source_id)
    notebook = source.notebook
    source.delete()  # the file is removed by the post_delete handler
    return _panel(request, notebook)


@login_required
@require_POST
def retry_source(request, source_id: int):
    source = _source(request, source_id)
    if not source.is_active:
        Source.objects.filter(pk=source.pk).update(status=Source.STATUS_PENDING, error='')
        enqueue_ingestion(source.pk)
    return _panel(request, source.notebook)


@login_required
@require_POST
def reindex(request, notebook_id: int):
    """Re-ingest ready sources indexed with another embedding model (spec §5, D5)."""
    notebook = _notebook(request, notebook_id)
    nb_settings, _created = NotebookSettings.objects.get_or_create(notebook=notebook)
    stale = notebook.sources.filter(status=Source.STATUS_READY).exclude(embedding_model=nb_settings.embedding_model)
    ids = list(stale.values_list('pk', flat=True))
    Source.objects.filter(pk__in=ids).update(status=Source.STATUS_PENDING, error='')
    for pk in ids:
        enqueue_ingestion(pk)
    return _panel(request, notebook)

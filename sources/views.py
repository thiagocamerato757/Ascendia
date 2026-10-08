"""Sources panel of the notebook page: add, list, retry, delete and reindex sources.

Every view is scoped to the notebook's owner (spec §11). The panel is one
partial (``sources/_panel.html``) that HTMX swaps in place after each action;
while a source is pending or processing, the list polls for status.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_GET, require_POST

from core.ratelimit import rate_limited
from llm.models import NotebookSettings
from workspace.models import Notebook

from .forms import TextSourceForm, kind_for_filename, validate_markdown_upload, validate_pdf_upload
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
        'max_mb': settings.ASCENDIA_SOURCE_MAX_MB,
        'max_files': settings.ASCENDIA_UPLOAD_MAX_FILES,
    }


def _panel(request, notebook: Notebook, **kwargs):
    response = render(request, 'sources/_panel.html', panel_context(notebook, **kwargs))
    # Lets the conversation refresh its empty state ("add a source" -> "ask") when sources change.
    response['HX-Trigger'] = 'sources-updated'
    return response


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
    """Add one or more files (PDF or Markdown). Each file is checked and added on its
    own: a bad file never blocks the good ones, and the notice lists what was left
    out and why."""
    notebook = _notebook(request, notebook_id)
    uploads = request.FILES.getlist('file')
    limit = settings.ASCENDIA_UPLOAD_MAX_FILES
    if not uploads:
        return _panel(request, notebook, notice={'variant': 'danger', 'title': _("Couldn't add the files"),
                                                  'message': _('Choose a PDF or Markdown file.')})
    if len(uploads) > limit:
        return _panel(request, notebook, notice={
            'variant': 'danger', 'title': _("Couldn't add the files"),
            'message': _('Send at most %(n)s files at a time.') % {'n': limit},
        })

    added, rejected, duplicates = 0, [], 0
    for upload in uploads:
        name = upload.name.rsplit('/', 1)[-1][:255]
        kind = kind_for_filename(name)
        try:
            if kind == Source.KIND_PDF:
                data, pages = validate_pdf_upload(upload)
            elif kind == Source.KIND_MARKDOWN:
                data, _text = validate_markdown_upload(upload)
                pages = 0
            else:
                raise ValidationError(_('Only PDF and Markdown (.md) files are accepted.'))
        except ValidationError as exc:
            rejected.append(f'{name}: {exc.messages[0]}')
            continue
        source = _create(notebook, kind=kind, title=name, file=upload,
                         content_hash=content_hash(data), page_count=pages)
        if source is None:
            duplicates += 1
            rejected.append(f'{name}: {_("already in this notebook")}')
        else:
            added += 1
    notice = _upload_notice(added, rejected, only_duplicates=duplicates == len(rejected))
    return _panel(request, notebook, notice=notice)


def _upload_notice(added: int, rejected: list[str], *, only_duplicates: bool = False) -> dict | None:
    if added and not rejected:
        if added == 1:
            return None  # the new item in the list is feedback enough
        return {'variant': 'success', 'title': ngettext('%(n)s file added', '%(n)s files added', added) % {'n': added},
                'message': _('They are being processed; answers can use them once they are ready.')}
    title = (ngettext('%(n)s file added', '%(n)s files added', added) % {'n': added} if added
             else _("Couldn't add the files"))
    # Something left out but nothing broken (some added, or only duplicates): warning.
    variant = 'warning' if added or only_duplicates else 'danger'
    return {'variant': variant, 'title': title,
            'message': ngettext('This file was left out:', 'These files were left out:', len(rejected)),
            'items': rejected}


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

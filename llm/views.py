from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from workspace.models import Notebook

from . import client, model_catalog
from . import constants as c
from .forms import BaseUrlForm, NotebookSettingsForm, ProviderCredentialForm
from .models import NotebookSettings, ProviderConfig, ProviderCredential
from .providers import ProviderError
from .style import compile_style


def _get_notebook(request, notebook_id: int) -> Notebook:
    """Owner-scoped notebook lookup (spec §11: no cross-user access)."""
    return get_object_or_404(Notebook, id=notebook_id, user=request.user)


# --- Account: API keys and local endpoints, one card per provider ----------

def _models_summary(provider: str, config: ProviderConfig | None) -> dict:
    """What the card says about the models notebooks can pick for a provider."""
    counts = model_catalog.counts(config.model_list) if config else {'chat': 0, 'embedding': 0}
    return {
        'chat': counts['chat'],
        'embedding': counts['embedding'],
        'updated_at': config.models_updated_at if config else None,
        'builtin_chat': len(c.PROVIDER_CHAT_MODELS.get(provider, [])),
    }


def _provider_row(value: str, label: str, credential, config) -> dict:
    is_local = value in c.LOCAL_PROVIDERS
    return {
        'value': value,
        'label': label,
        'is_local': is_local,
        'credential': credential,
        'base_url': config.effective_base_url if config else c.base_url_for(value),
        'default_base_url': c.default_base_url(value),
        'models': _models_summary(value, config),
        # Refresh and Test only make sense once a key / server URL is saved.
        'ready': bool(config and config.base_url) if is_local else credential is not None,
    }


class ApiKeysView(LoginRequiredMixin, View):
    template_name = 'llm/api_keys.html'

    def get(self, request):
        creds = {cr.provider: cr for cr in ProviderCredential.objects.filter(user=request.user)}
        configs = {cf.provider: cf for cf in ProviderConfig.objects.filter(user=request.user)}
        cloud, local = [], []
        for value, label in c.PROVIDER_CHOICES:
            row = _provider_row(value, label, creds.get(value), configs.get(value))
            (local if row['is_local'] else cloud).append(row)
        return render(request, self.template_name, {'cloud_rows': cloud, 'local_rows': local})


class CredentialSetView(LoginRequiredMixin, View):
    def post(self, request):
        form = ProviderCredentialForm(request.POST, user=request.user)
        if form.is_valid():
            credential = form.save()
            messages.success(
                request,
                _('Key for %(provider)s saved.') % {'provider': credential.get_provider_display()},
            )
        else:
            messages.error(request, _('Please correct the errors below.'))
        return redirect(reverse('llm:api_keys'))


class CredentialDeleteView(LoginRequiredMixin, View):
    def post(self, request, provider):
        qs = ProviderCredential.objects.filter(user=request.user, provider=provider)
        credential = qs.first()
        if credential:
            label = credential.get_provider_display()
            qs.delete()
            messages.success(request, _('Key for %(provider)s removed.') % {'provider': label})
        return redirect(reverse('llm:api_keys'))


class BaseUrlSetView(LoginRequiredMixin, View):
    def post(self, request):
        form = BaseUrlForm(request.POST)
        if form.is_valid():
            provider = form.cleaned_data['provider']
            config, _created = ProviderConfig.objects.get_or_create(user=request.user, provider=provider)
            config.base_url = form.cleaned_data['base_url']
            config.save(update_fields=['base_url'])
            messages.success(request, _('Base URL saved.'))
        else:
            messages.error(request, _('Please correct the errors below.'))
        return redirect(reverse('llm:api_keys'))


class RefreshModelsView(LoginRequiredMixin, View):
    """HTMX: fetch the live model list for a provider and cache it."""

    template_name = 'llm/_refresh_result.html'

    def post(self, request, provider):
        if provider not in dict(c.PROVIDER_CHOICES):
            raise Http404
        error = None
        counts = None
        try:
            counts = client.refresh_and_store(request.user, provider)
        except ProviderError as exc:
            error = exc
        config = ProviderConfig.objects.filter(user=request.user, provider=provider).first()
        return render(request, self.template_name, {
            'provider': provider,
            'counts': counts,
            'error': error,
            'models': _models_summary(provider, config),
        })


class TestProviderView(LoginRequiredMixin, View):
    """HTMX: test one provider (cloud: chat ping; local: endpoint reachability)."""

    template_name = 'llm/_test_result.html'

    def post(self, request, provider):
        if provider not in dict(c.PROVIDER_CHOICES):
            raise Http404
        message = None
        error = None
        try:
            message = client.test_provider(request.user, provider)
        except ProviderError as exc:
            error = exc
        return render(request, self.template_name, {'message': message, 'error': error})


class ModelOptionsView(LoginRequiredMixin, View):
    """HTMX partial: the model field for a chosen provider (dependent select)."""

    template_name = 'llm/_model_field.html'

    def get(self, request):
        kind = request.GET.get('kind', 'chat')
        provider = (
            request.GET.get(f'{kind}_provider')
            or request.GET.get('provider')
            or c.PROVIDER_OPENAI
        )
        models = client.available_models(request.user, provider, kind)
        return render(request, self.template_name, {
            'field_name': 'embedding_model' if kind == 'embedding' else 'chat_model',
            'models': models,
            'current': request.GET.get('current', ''),
            'free_text': provider in c.FREE_TEXT_MODEL_PROVIDERS and not models,
        })


# --- Per-notebook provider, model and answer style -------------------------

class NotebookSettingsView(LoginRequiredMixin, View):
    template_name = 'llm/notebook_settings.html'

    def _context(self, request, notebook, settings, form):
        return {
            'notebook': notebook,
            'settings': settings,
            'form': form,
            'compiled_style': compile_style(settings.style_spec),
        }

    def get(self, request, notebook_id):
        notebook = _get_notebook(request, notebook_id)
        settings, _created = NotebookSettings.objects.get_or_create(notebook=notebook)
        form = NotebookSettingsForm(instance=settings, user=request.user)
        return render(request, self.template_name, self._context(request, notebook, settings, form))

    def post(self, request, notebook_id):
        notebook = _get_notebook(request, notebook_id)
        settings, _created = NotebookSettings.objects.get_or_create(notebook=notebook)
        # Captured before the ModelForm writes to the instance (spec §5, D5).
        previous_embedding = (settings.embedding_provider, settings.embedding_model)
        form = NotebookSettingsForm(request.POST, instance=settings, user=request.user)
        if form.is_valid():
            settings = form.save()
            messages.success(request, _('Notebook settings saved.'))
            if (settings.embedding_provider, settings.embedding_model) != previous_embedding:
                messages.warning(request, _(
                    'The embedding model changed. The sources in this notebook must be '
                    're-indexed before they can be searched again.'
                ))
            return redirect(reverse('llm:notebook_settings', kwargs={'notebook_id': notebook.id}))
        messages.error(request, _('Please correct the errors below.'))
        return render(request, self.template_name, self._context(request, notebook, settings, form))

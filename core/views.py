from django.conf import settings
from django.http import Http404
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'homepage.html'


class StyleguideView(TemplateView):
    """Living style guide — only available when DEBUG is on (spec §10.7)."""
    template_name = 'styleguide.html'

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['colors'] = [
            ('surface', '--surface'),
            ('surface-raised', '--surface-raised'),
            ('surface-sunken', '--surface-sunken'),
            ('text', '--text'),
            ('text-muted', '--text-muted'),
            ('border', '--border'),
            ('accent', '--accent'),
            ('danger', '--danger'),
            ('success', '--success'),
            ('warning', '--warning'),
        ]
        context['toasts'] = [
            ('success', 'Success'),
            ('error', 'Error'),
            ('warning', 'Warning'),
            ('info', 'Information'),
        ]
        return context

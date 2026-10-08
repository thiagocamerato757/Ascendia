from django.conf import settings
from django.http import Http404
from django.utils.translation import gettext_lazy as _
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
            ('success', _('Success')),
            ('error', _('Error')),
            ('warning', _('Warning')),
            ('info', _('Information')),
        ]
        from rag.render import render_partial

        context['rich_sample'] = render_partial(
            'Dijkstra custa $O((V+E)\\log V)$ [1].\n\n'
            '$$d(v) = \\min_{u}\\,(d(u) + w(u, v))$$\n\n'
            '```python\ndef relax(d, u, v, w):\n    if d[u] + w < d[v]:\n        d[v] = d[u] + w\n```'
        )
        return context

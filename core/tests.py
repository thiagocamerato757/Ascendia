from django.http import Http404
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.views import StyleguideView


class HomeViewTests(TestCase):
    def test_home_renders(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'homepage.html')


class StyleguideViewTests(TestCase):
    """The living style guide is dev-only and renders every component (§10.7).

    The route is wired in core/urls.py only when DEBUG is on (evaluated at
    import time, so it is absent during the test run). We therefore drive the
    view directly to cover both the DEBUG guard and the template rendering.
    """

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    def test_renders_all_sections_with_debug(self):
        response = StyleguideView.as_view()(self.factory.get('/styleguide/'))
        response.render()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        # Sections the audit flagged as missing must now be present.
        for needle in ['c-select', 'c-modal', 'c-settings-panel']:
            self.assertIn(needle, html)

    @override_settings(DEBUG=False)
    def test_raises_404_without_debug(self):
        with self.assertRaises(Http404):
            StyleguideView.as_view()(self.factory.get('/styleguide/'))

    def test_route_absent_in_production(self):
        """With DEBUG off (suite default), /styleguide/ is not routed at all."""
        self.assertEqual(self.client.get('/styleguide/').status_code, 404)


class AssetTagTests(SimpleTestCase):
    """`{% asset %}` versions static URLs by content so browsers drop stale CSS."""

    def render(self, path):
        return Template("{% load assets %}{% asset '" + path + "' %}").render(Context())

    def test_appends_content_hash(self):
        url = self.render('css/tokens.css')
        self.assertRegex(url, r'^/static/css/tokens\.css\?v=[0-9a-f]{12}$')

    def test_hash_differs_between_files(self):
        self.assertNotEqual(self.render('css/tokens.css').split('?v=')[1],
                            self.render('css/base.css').split('?v=')[1])

    def test_unknown_file_falls_back_to_plain_static_url(self):
        self.assertEqual(self.render('css/missing.css'), '/static/css/missing.css')


class BrowserLanguageTests(TestCase):
    """The UI follows the browser's Accept-Language (LocaleMiddleware)."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('lang', password='pw')
        self.client.force_login(self.user)

    def get(self, url, lang):
        return self.client.get(url, HTTP_ACCEPT_LANGUAGE=lang)

    def test_english_browser_gets_english_ui(self):
        resp = self.get(reverse('workspace:home'), 'en-US,en;q=0.9')
        self.assertContains(resp, '<html lang="en">')
        self.assertContains(resp, 'Workspace')
        self.assertNotContains(resp, 'Espaço de Trabalho')

    def test_portuguese_browser_gets_portuguese_ui(self):
        resp = self.get(reverse('workspace:home'), 'pt-BR,pt;q=0.9')
        self.assertContains(resp, '<html lang="pt-br">')
        self.assertContains(resp, 'Espaço de Trabalho')

    def test_unsupported_language_falls_back_to_portuguese(self):
        resp = self.get(reverse('workspace:home'), 'de-DE')
        self.assertContains(resp, '<html lang="pt-br">')

    def test_provider_errors_follow_browser_language(self):
        url = reverse('llm:test_provider', kwargs={'provider': 'openai'})
        en = self.client.post(url, HTTP_ACCEPT_LANGUAGE='en')
        pt = self.client.post(url, HTTP_ACCEPT_LANGUAGE='pt-BR')
        self.assertContains(en, 'No API key saved for this provider.')
        self.assertContains(pt, 'Nenhuma chave de API salva para este provedor.')

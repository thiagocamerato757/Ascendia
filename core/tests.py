from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
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

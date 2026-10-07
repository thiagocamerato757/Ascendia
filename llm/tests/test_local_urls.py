from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext

from llm import client, providers
from llm import constants as c
from llm.local_urls import LocalURLError, validate_local_url
from llm.models import ProviderConfig
from llm.providers import ProviderError

from . import FernetTestCase

DEFAULT_HOSTS = ['localhost', '127.0.0.1', '::1', 'host.docker.internal']


@override_settings(ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS=DEFAULT_HOSTS)
class ValidateLocalURLTests(SimpleTestCase):
    def test_default_hosts_are_allowed_and_normalized(self):
        self.assertEqual(validate_local_url(' http://localhost:11434/ '), 'http://localhost:11434')
        self.assertEqual(validate_local_url('http://host.docker.internal:1234/v1'), 'http://host.docker.internal:1234/v1')
        self.assertEqual(validate_local_url('http://127.0.0.1:8080/v1'), 'http://127.0.0.1:8080/v1')
        self.assertEqual(validate_local_url('http://[::1]:11434'), 'http://[::1]:11434')

    def test_host_matching_ignores_case(self):
        self.assertEqual(validate_local_url('http://LocalHost:11434'), 'http://LocalHost:11434')

    def test_internal_services_are_refused(self):
        for url in ('http://db:5432', 'http://web:8000', 'http://10.0.0.5:11434', 'http://example.com'):
            with self.subTest(url=url), self.assertRaises(LocalURLError) as ctx:
                validate_local_url(url)
            self.assertIn('ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS', str(ctx.exception))

    def test_malformed_urls_are_refused(self):
        for url in (
            'ftp://localhost:21', 'localhost:11434', 'http://', 'http://localhost:99999',
            'http://user:pw@localhost:11434', 'http://localhost:11434/?x=1', 'http://localhost:11434/#f',
        ):
            with self.subTest(url=url), self.assertRaises(LocalURLError):
                validate_local_url(url)

    @override_settings(ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS=['*'])
    def test_metadata_address_refused_even_with_wildcard(self):
        for url in ('http://169.254.169.254/latest', 'http://[fe80::1]:80', 'http://0.0.0.0:11434'):
            with self.subTest(url=url), self.assertRaises(LocalURLError):
                validate_local_url(url)

    @override_settings(ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS=['*'])
    def test_wildcard_checks_what_a_name_resolves_to(self):
        link_local = [(2, 1, 6, '', ('169.254.169.254', 0))]
        with mock.patch('llm.local_urls.socket.getaddrinfo', return_value=link_local):
            with self.assertRaises(LocalURLError):
                validate_local_url('http://metadata.internal')
        lan = [(2, 1, 6, '', ('192.168.0.10', 0))]
        with mock.patch('llm.local_urls.socket.getaddrinfo', return_value=lan):
            self.assertEqual(validate_local_url('http://gpu-box:11434'), 'http://gpu-box:11434')

    @override_settings(ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS=[*DEFAULT_HOSTS, '192.168.0.10'])
    def test_operator_can_allow_a_lan_server(self):
        self.assertEqual(validate_local_url('http://192.168.0.10:11434'), 'http://192.168.0.10:11434')


@override_settings(ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS=DEFAULT_HOSTS)
class LocalURLFlowTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('lan', password='pw')
        self.client.force_login(self.user)

    def tearDown(self):
        providers.set_model_lister(None)
        super().tearDown()

    def test_saving_a_disallowed_url_explains_why(self):
        resp = self.client.post(reverse('llm:base_url_set'), {
            'provider': c.PROVIDER_OLLAMA, 'base_url': 'http://db:5432',
        }, follow=True)
        self.assertFalse(ProviderConfig.objects.filter(user=self.user, provider=c.PROVIDER_OLLAMA).exists())
        self.assertContains(resp, 'ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS')

    def test_url_saved_before_the_allowlist_changed_is_not_fetched(self):
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://10.0.0.5:11434')
        calls = []
        providers.set_model_lister(lambda p, *, api_key, base_url: calls.append(base_url) or ['x'])
        with self.assertRaises(ProviderError) as ctx:
            client.refresh_models(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(ctx.exception.level, 'warning')
        self.assertEqual(calls, [])


class LocalRedirectTests(SimpleTestCase):
    def _get(self, *, redirect):
        resp = mock.Mock(status_code=302 if redirect else 200, is_redirect=redirect)
        resp.json.return_value = {'models': [{'name': 'llama3.1'}]}
        resp.raise_for_status.return_value = None
        return mock.patch('requests.get', return_value=resp)

    def test_local_servers_do_not_follow_redirects(self):
        with self._get(redirect=False) as get:
            providers.list_models(c.PROVIDER_OLLAMA, api_key=None, base_url='http://localhost:11434', timeout=1)
        self.assertIs(get.call_args.kwargs['allow_redirects'], False)

    def test_redirect_answer_is_reported_clearly(self):
        with self._get(redirect=True), self.assertRaises(ProviderError) as ctx:
            providers.list_models(c.PROVIDER_OLLAMA, api_key=None, base_url='http://localhost:11434', timeout=1)
        expected = gettext('The server answered with a redirect. Enter its final address as the server URL.')
        self.assertEqual(ctx.exception.user_message, expected)

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django_tasks_db.models import DBTaskResult

from sources.models import Source

from . import SourcesTestCase, make_pdf


class SourceViewsTests(SourcesTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def _upload(self, data: bytes, name='aula.pdf', notebook=None):
        url = reverse('sources:upload', kwargs={'notebook_id': (notebook or self.notebook).id})
        return self.client.post(url, {'file': SimpleUploadedFile(name, data, content_type='application/pdf')},
                                HTTP_HX_REQUEST='true')

    def test_upload_creates_pending_source_and_queues_it_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            resp = self._upload(make_pdf(['Celulas e tecidos.']))
        self.assertEqual(resp.status_code, 200)
        source = Source.objects.get(notebook=self.notebook)
        self.assertEqual((source.kind, source.status, source.title, source.page_count),
                         ('pdf', 'pending', 'aula.pdf', 1))
        self.assertNotIn('aula', source.file.name)  # random stored name
        self.assertTrue(DBTaskResult.objects.filter(args_kwargs__args=[source.pk]).exists())
        self.assertContains(resp, 'hx-trigger="every 3s"')  # polling while pending

    def test_fake_pdf_is_rejected_with_reason(self):
        resp = self._upload(b'MZ\x90\x00 not a pdf', name='virus.pdf')
        self.assertFalse(Source.objects.exists())
        self.assertContains(resp, 'c-notice--danger')

    @override_settings(ASCENDIA_SOURCE_MAX_MB=0)
    def test_size_limit(self):
        self._upload(make_pdf(['x']))
        self.assertFalse(Source.objects.exists())

    def test_same_pdf_twice_is_not_duplicated(self):
        data = make_pdf(['Conteudo repetido.'])
        self._upload(data)
        resp = self._upload(data, name='copia.pdf')
        self.assertEqual(Source.objects.count(), 1)
        self.assertContains(resp, 'c-notice--warning')

    def test_add_text_and_validation(self):
        url = reverse('sources:add_text', kwargs={'notebook_id': self.notebook.id})
        resp = self.client.post(url, {'title': 'Resumo', 'text': '   '})
        self.assertFalse(Source.objects.exists())
        self.assertContains(resp, 'open')  # the disclosure stays open to show the error
        self.client.post(url, {'title': 'Resumo', 'text': 'Leis de Mendel.'})
        self.assertEqual(Source.objects.get().kind, Source.KIND_TEXT)

    def test_other_users_cannot_touch_sources(self):
        source = Source.objects.create(notebook=self.notebook, kind='text', title='t', text='x', content_hash='h')
        self.client.force_login(self.other)
        for url in (
            reverse('sources:panel', kwargs={'notebook_id': self.notebook.id}),
        ):
            self.assertEqual(self.client.get(url).status_code, 404)
        for url in (
            reverse('sources:upload', kwargs={'notebook_id': self.notebook.id}),
            reverse('sources:add_text', kwargs={'notebook_id': self.notebook.id}),
            reverse('sources:reindex', kwargs={'notebook_id': self.notebook.id}),
            reverse('sources:delete', kwargs={'source_id': source.id}),
            reverse('sources:retry', kwargs={'source_id': source.id}),
        ):
            self.assertEqual(self.client.post(url).status_code, 404, url)
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())

    def test_retry_requeues_failed_source(self):
        source = Source.objects.create(notebook=self.notebook, kind='text', title='t', text='x', content_hash='h',
                                       status=Source.STATUS_FAILED, error='falhou')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('sources:retry', kwargs={'source_id': source.id}))
        source.refresh_from_db()
        self.assertEqual((source.status, source.error), (Source.STATUS_PENDING, ''))

    def test_reindex_only_requeues_sources_from_another_model(self):
        current = self.nb_settings.embedding_model
        fresh = Source.objects.create(notebook=self.notebook, kind='text', title='a', text='a', content_hash='a',
                                      status='ready', embedding_model=current)
        stale = Source.objects.create(notebook=self.notebook, kind='text', title='b', text='b', content_hash='b',
                                      status='ready', embedding_model='old-model')
        panel = self.client.get(reverse('sources:panel', kwargs={'notebook_id': self.notebook.id}))
        self.assertContains(panel, reverse('sources:reindex', kwargs={'notebook_id': self.notebook.id}))
        self.client.post(reverse('sources:reindex', kwargs={'notebook_id': self.notebook.id}))
        fresh.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual((fresh.status, stale.status), ('ready', 'pending'))

    def test_delete(self):
        source = Source.objects.create(notebook=self.notebook, kind='text', title='t', text='x', content_hash='h')
        self.client.post(reverse('sources:delete', kwargs={'source_id': source.id}))
        self.assertFalse(Source.objects.exists())

    def test_no_polling_when_everything_is_settled(self):
        Source.objects.create(notebook=self.notebook, kind='text', title='t', text='x', content_hash='h',
                              status='ready')
        resp = self.client.get(reverse('sources:panel', kwargs={'notebook_id': self.notebook.id}))
        self.assertNotContains(resp, 'every 3s')

    @override_settings(ASCENDIA_RATE_UPLOAD_PER_MIN=2)
    def test_upload_rate_limit(self):
        url = reverse('sources:add_text', kwargs={'notebook_id': self.notebook.id})
        for i in range(2):
            self.client.post(url, {'title': f't{i}', 'text': f'texto {i}'}, HTTP_HX_REQUEST='true')
        resp = self.client.post(url, {'title': 't3', 'text': 'texto 3'}, HTTP_HX_REQUEST='true')
        self.assertEqual(Source.objects.count(), 2)
        self.assertContains(resp, 'c-notice--warning')
        self.assertEqual(resp['Retry-After'], '60')


class CsrfWithHtmxTests(SourcesTestCase):
    """Buttons outside forms (Remove, Try again, Clear conversation) must carry the CSRF token.

    The default test client skips CSRF checks, which hid this bug; this one enforces them.
    """

    def test_htmx_buttons_send_the_token_from_body_headers(self):
        import json
        import re

        from django.test import Client

        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        source = Source.objects.create(notebook=self.notebook, kind='text', title='t', text='x', content_hash='h',
                                       status=Source.STATUS_FAILED, error='falhou')
        page = browser.get(reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id}))
        headers = json.loads(re.search(r"<body hx-headers='([^']+)'", page.content.decode()).group(1))
        retry = reverse('sources:retry', kwargs={'source_id': source.id})
        self.assertEqual(browser.post(retry).status_code, 403)  # what happened before the fix
        self.assertEqual(browser.post(retry, HTTP_X_CSRFTOKEN=headers['X-CSRFToken']).status_code, 200)
        delete = reverse('sources:delete', kwargs={'source_id': source.id})
        self.assertEqual(browser.post(delete, HTTP_X_CSRFTOKEN=headers['X-CSRFToken']).status_code, 200)
        self.assertFalse(Source.objects.filter(pk=source.pk).exists())


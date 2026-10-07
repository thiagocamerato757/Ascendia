"""Shared fixtures: a notebook with the fake provider and a temporary file store."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import override_settings

from llm import client
from llm.models import NotebookSettings
from llm.providers import FakeProvider
from llm.tests import FernetTestCase
from workspace.models import Notebook


def make_pdf(pages: list[str], toc: list | None = None) -> bytes:
    """A real PDF with one text block per page (and an optional outline)."""
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    if toc:
        doc.set_toc(toc)
    data = doc.tobytes()
    doc.close()
    return data


class SourcesTestCase(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix='ascendia-sources-')
        self._storage = override_settings(ASCENDIA_SOURCES_ROOT=self.tmp)
        self._storage.enable()
        self.fake = FakeProvider()
        client.set_provider_override(self.fake)
        self.user = User.objects.create_user('owner', password='pw')
        self.other = User.objects.create_user('intruder', password='pw')
        self.notebook = Notebook.objects.create(user=self.user, title='Biologia')
        self.nb_settings = NotebookSettings.objects.create(notebook=self.notebook)

    def tearDown(self):
        client.set_provider_override(None)
        self._storage.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

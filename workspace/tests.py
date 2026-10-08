from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Notebook


class NotebookModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook',
            description='Test Description',
            color='#06b6d4',
            is_favorite=False
        )
    
    def test_notebook_creation(self):
        self.assertEqual(self.notebook.title, 'Test Notebook')
        self.assertEqual(self.notebook.description, 'Test Description')
        self.assertEqual(self.notebook.user, self.user)
        self.assertEqual(self.notebook.color, '#06b6d4')
        self.assertFalse(self.notebook.is_favorite)
    
    def test_notebook_str_method(self):
        self.assertEqual(str(self.notebook), 'Test Notebook')
    
    def test_notebook_ordering(self):
        notebook2 = Notebook.objects.create(
            user=self.user,
            title='Another Notebook',
            is_favorite=True
        )
        notebooks = Notebook.objects.filter(user=self.user).order_by('-is_favorite', '-updated_at')
        self.assertEqual(notebooks[0], notebook2)  # Favorite first
    
    def test_notebook_default_color(self):
        notebook = Notebook.objects.create(
            user=self.user,
            title='No Color Notebook'
        )
        self.assertEqual(notebook.color, '#06b6d4')


class WorkspaceViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook',
            description='Test Description'
        )
    
    def test_workspace_home_requires_login(self):
        response = self.client.get(reverse('workspace:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)
    
    def test_workspace_home_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('workspace:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'workspace/home.html')
        self.assertContains(response, 'Test Notebook')
    
    def test_workspace_home_shows_only_user_notebooks(self):
        Notebook.objects.create(
            user=self.other_user,
            title='Other User Notebook'
        )
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('workspace:home'))
        self.assertContains(response, 'Test Notebook')
        self.assertNotContains(response, 'Other User Notebook')
    
    def test_notebook_detail_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'workspace/notebook_detail.html')
        self.assertContains(response, 'Test Notebook')
    
    def test_notebook_detail_unauthorized(self):
        self.client.login(username='otheruser', password='otherpass123')
        response = self.client.get(
            reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 404)
    
    def test_notebook_create_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('workspace:notebook_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'workspace/notebook_create.html')
    
    def test_notebook_create_post(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'New Notebook',
            'description': 'New Description',
            'color': '#10b981',
            'is_favorite': True
        }
        response = self.client.post(reverse('workspace:notebook_create'), data)
        self.assertEqual(response.status_code, 302)
        
        notebook = Notebook.objects.get(title='New Notebook')
        self.assertEqual(notebook.user, self.user)
        self.assertEqual(notebook.description, 'New Description')
        self.assertEqual(notebook.color, '#10b981')
        self.assertTrue(notebook.is_favorite)
    
    def test_notebook_update_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('workspace:notebook_edit', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'workspace/notebook_create.html')
        self.assertContains(response, 'Test Notebook')
    
    def test_notebook_update_post(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'Updated Notebook',
            'description': 'Updated Description',
            'color': '#8b5cf6',
            'is_favorite': True
        }
        response = self.client.post(
            reverse('workspace:notebook_edit', kwargs={'notebook_id': self.notebook.id}),
            data
        )
        self.assertEqual(response.status_code, 302)
        
        self.notebook.refresh_from_db()
        self.assertEqual(self.notebook.title, 'Updated Notebook')
        self.assertEqual(self.notebook.description, 'Updated Description')
        self.assertTrue(self.notebook.is_favorite)
    
    def test_notebook_delete_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('workspace:notebook_delete', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'workspace/notebook_delete.html')
    
    def test_notebook_delete_post(self):
        self.client.login(username='testuser', password='testpass123')
        notebook_id = self.notebook.id
        response = self.client.post(
            reverse('workspace:notebook_delete', kwargs={'notebook_id': notebook_id})
        )
        self.assertEqual(response.status_code, 302)
        
        with self.assertRaises(Notebook.DoesNotExist):
            Notebook.objects.get(id=notebook_id)
    
    def test_notebook_toggle_favorite(self):
        self.client.login(username='testuser', password='testpass123')
        self.assertFalse(self.notebook.is_favorite)
        
        response = self.client.post(
            reverse('workspace:notebook_toggle_favorite', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 302)
        self.notebook.refresh_from_db()
        self.assertTrue(self.notebook.is_favorite)
        
        response = self.client.post(
            reverse('workspace:notebook_toggle_favorite', kwargs={'notebook_id': self.notebook.id})
        )
        self.notebook.refresh_from_db()
        self.assertFalse(self.notebook.is_favorite)


class NotebookPermissionsTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='pass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user1,
            title='User1 Notebook'
        )
        self.client = Client()
    
    def test_user_cannot_view_other_user_notebook(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.get(
            reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 404)
    
    def test_user_cannot_edit_other_user_notebook(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('workspace:notebook_edit', kwargs={'notebook_id': self.notebook.id}),
            {'title': 'Hacked'}
        )
        self.assertEqual(response.status_code, 404)
        self.notebook.refresh_from_db()
        self.assertEqual(self.notebook.title, 'User1 Notebook')
    
    def test_user_cannot_delete_other_user_notebook(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('workspace:notebook_delete', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Notebook.objects.filter(id=self.notebook.id).exists())


class NotebookWorkspaceLayoutTests(TestCase):
    """The notebook page is the three-panel workspace (spec §10.4)."""

    def test_sources_chat_and_notes_panels_with_tabs(self):
        user = User.objects.create_user('layout', password='pw')
        notebook = Notebook.objects.create(user=user, title='NB')
        self.client.force_login(user)
        resp = self.client.get(reverse('workspace:notebook_detail', kwargs={'notebook_id': notebook.id}))
        for marker in ('id="sources-panel"', 'id="chat-panel"', 'id="ask-form"', 'id="col-notes"',
                       'data-notebook-tabs', 'role="tablist"', 'js/chat.js', 'js/notebook.js'):
            self.assertContains(resp, marker)
        self.assertNotContains(resp, 'Upload file')  # old disabled placeholder is gone
        self.assertContains(resp, 'l-app--workspace')  # fixed-height workspace, columns scroll
        self.assertContains(resp, 'data-chat-jump')
        self.assertContains(resp, 'o-container--fluid')  # edge to edge
        self.assertContains(resp, 'c-notebook-bar')
        self.assertContains(resp, 'data-dropzone')
        self.assertNotContains(resp, 'class="l-footer"')


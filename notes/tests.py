from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from workspace.models import Notebook
from .models import Note, Tag, NoteTag


class NoteModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook'
        )
        self.note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Test Note',
            content='Test content',
            is_pinned=False
        )
    
    def test_note_creation(self):
        self.assertEqual(self.note.title, 'Test Note')
        self.assertEqual(self.note.content, 'Test content')
        self.assertEqual(self.note.user, self.user)
        self.assertEqual(self.note.notebook, self.notebook)
        self.assertFalse(self.note.is_pinned)
    
    def test_note_str_method(self):
        self.assertEqual(str(self.note), 'Test Note')
    
    def test_note_ordering(self):
        pinned_note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Pinned Note',
            is_pinned=True
        )
        notes = Note.objects.filter(notebook=self.notebook)
        self.assertEqual(notes[0], pinned_note)  # Pinned first


class TagModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.tag = Tag.objects.create(
            name='Python',
            user=self.user,
            color='#3b82f6'
        )
    
    def test_tag_creation(self):
        self.assertEqual(self.tag.name, 'Python')
        self.assertEqual(self.tag.user, self.user)
        self.assertEqual(self.tag.color, '#3b82f6')
    
    def test_tag_str_method(self):
        self.assertEqual(str(self.tag), 'Python')
    
    def test_tag_unique_per_user(self):
        with self.assertRaises(Exception):
            Tag.objects.create(
                name='Python',
                user=self.user,
                color='#10b981'
            )
    
    def test_different_users_can_have_same_tag_name(self):
        other_user = User.objects.create_user(
            username='otheruser',
            password='pass123'
        )
        other_tag = Tag.objects.create(
            name='Python',
            user=other_user,
            color='#10b981'
        )
        self.assertIsNotNone(other_tag)
        self.assertEqual(Tag.objects.filter(name='Python').count(), 2)


class NoteTagModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook'
        )
        self.note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Test Note'
        )
        self.tag = Tag.objects.create(
            name='Python',
            user=self.user
        )
    
    def test_note_tag_creation(self):
        note_tag = NoteTag.objects.create(
            note=self.note,
            tag=self.tag
        )
        self.assertEqual(note_tag.note, self.note)
        self.assertEqual(note_tag.tag, self.tag)
    
    def test_note_tag_str_method(self):
        note_tag = NoteTag.objects.create(
            note=self.note,
            tag=self.tag
        )
        self.assertEqual(str(note_tag), 'Test Note - Python')


class NoteViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook'
        )
        self.note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Test Note',
            content='Test content'
        )
    
    def test_note_create_requires_login(self):
        response = self.client.get(
            reverse('notes:note_create', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)
    
    def test_note_create_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_create', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/note_create.html')
    
    def test_note_create_post(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'New Note',
            'content': 'New content'
        }
        response = self.client.post(
            reverse('notes:note_create', kwargs={'notebook_id': self.notebook.id}),
            data
        )
        self.assertEqual(response.status_code, 302)
        
        note = Note.objects.get(title='New Note')
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.notebook, self.notebook)
        self.assertEqual(note.content, 'New content')
    
    def test_note_detail_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_detail', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/note_detail.html')
        self.assertContains(response, 'Test Note')
        self.assertContains(response, 'Test content')
    
    def test_note_update_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_edit', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Note')
    
    def test_note_update_post(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'Updated Note',
            'content': 'Updated content'
        }
        response = self.client.post(
            reverse('notes:note_edit', kwargs={'note_id': self.note.id}),
            data
        )
        self.assertEqual(response.status_code, 302)
        
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'Updated Note')
        self.assertEqual(self.note.content, 'Updated content')
    
    def test_note_delete_post(self):
        self.client.login(username='testuser', password='testpass123')
        note_id = self.note.id
        response = self.client.post(
            reverse('notes:note_delete', kwargs={'note_id': note_id})
        )
        self.assertEqual(response.status_code, 302)
        
        with self.assertRaises(Note.DoesNotExist):
            Note.objects.get(id=note_id)
    
    def test_note_toggle_pin(self):
        self.client.login(username='testuser', password='testpass123')
        self.assertFalse(self.note.is_pinned)
        
        response = self.client.post(
            reverse('notes:note_toggle_pin', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 302)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_pinned)
        
        response = self.client.post(
            reverse('notes:note_toggle_pin', kwargs={'note_id': self.note.id})
        )
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_pinned)


class TagViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.tag = Tag.objects.create(
            name='Python',
            user=self.user,
            color='#3b82f6'
        )
    
    def test_tag_list_requires_login(self):
        response = self.client.get(reverse('notes:tag_list'))
        self.assertEqual(response.status_code, 302)
    
    def test_tag_list_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('notes:tag_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/tag_list.html')
        self.assertContains(response, 'Python')
    
    def test_tag_create_post(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Django',
            'color': '#10b981'
        }
        response = self.client.post(reverse('notes:tag_create'), data)
        self.assertEqual(response.status_code, 302)
        
        tag = Tag.objects.get(name='Django')
        self.assertEqual(tag.user, self.user)
        self.assertEqual(tag.color, '#10b981')
    
    def test_tag_create_duplicate_name(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Python',  # Already exists
            'color': '#10b981'
        }
        response = self.client.post(reverse('notes:tag_create'), data)
        self.assertEqual(response.status_code, 302)
        
        # Should only have one Python tag
        self.assertEqual(Tag.objects.filter(name='Python', user=self.user).count(), 1)


class NoteTagRelationshipTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Test Notebook'
        )
        self.note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Test Note'
        )
        self.tag = Tag.objects.create(
            name='Python',
            user=self.user
        )
    
    def test_add_tag_to_note(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('notes:note_add_tag', kwargs={'note_id': self.note.id}),
            {'tag_id': self.tag.id}
        )
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(NoteTag.objects.filter(note=self.note, tag=self.tag).exists())
    
    def test_remove_tag_from_note(self):
        NoteTag.objects.create(note=self.note, tag=self.tag)
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('notes:note_remove_tag', kwargs={
                'note_id': self.note.id,
                'tag_id': self.tag.id
            })
        )
        self.assertEqual(response.status_code, 302)
        
        self.assertFalse(NoteTag.objects.filter(note=self.note, tag=self.tag).exists())


class NotePermissionsTest(TestCase):
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
        self.note = Note.objects.create(
            notebook=self.notebook,
            user=self.user1,
            title='User1 Note',
            content='Private content'
        )
        self.client = Client()
    
    def test_user_cannot_view_other_user_note(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.get(
            reverse('notes:note_detail', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 404)
    
    def test_user_cannot_edit_other_user_note(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('notes:note_edit', kwargs={'note_id': self.note.id}),
            {'title': 'Hacked', 'content': 'Hacked content'}
        )
        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'User1 Note')
    
    def test_user_cannot_delete_other_user_note(self):
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('notes:note_delete', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

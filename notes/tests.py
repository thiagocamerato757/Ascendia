"""
Test suite for notes app.

This module contains comprehensive tests for notes, tags,
and note-tag relationships functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from workspace.models import Notebook
from .models import Note, Tag, NoteTag


class NoteModelTest(TestCase):
    """Test cases for the Note model."""
    
    def setUp(self):
        """Set up test data before each test method."""
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
        """Test that a note can be created successfully."""
        self.assertEqual(self.note.title, 'Test Note')
        self.assertEqual(self.note.content, 'Test content')
        self.assertEqual(self.note.user, self.user)
        self.assertEqual(self.note.notebook, self.notebook)
        self.assertFalse(self.note.is_pinned)
    
    def test_note_str_method(self):
        """Test the string representation of note."""
        self.assertEqual(str(self.note), 'Test Note')
    
    def test_note_ordering(self):
        """Test that notes are ordered correctly."""
        pinned_note = Note.objects.create(
            notebook=self.notebook,
            user=self.user,
            title='Pinned Note',
            is_pinned=True
        )
        notes = Note.objects.filter(notebook=self.notebook)
        self.assertEqual(notes[0], pinned_note)  # Pinned first


class TagModelTest(TestCase):
    """Test cases for the Tag model."""
    
    def setUp(self):
        """Set up test data."""
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
        """Test that a tag can be created successfully."""
        self.assertEqual(self.tag.name, 'Python')
        self.assertEqual(self.tag.user, self.user)
        self.assertEqual(self.tag.color, '#3b82f6')
    
    def test_tag_str_method(self):
        """Test the string representation of tag."""
        self.assertEqual(str(self.tag), 'Python')
    
    def test_tag_unique_per_user(self):
        """Test that tag names must be unique per user."""
        with self.assertRaises(Exception):
            Tag.objects.create(
                name='Python',
                user=self.user,
                color='#10b981'
            )
    
    def test_different_users_can_have_same_tag_name(self):
        """Test that different users can have tags with the same name."""
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
    """Test cases for the NoteTag relationship model."""
    
    def setUp(self):
        """Set up test data."""
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
        """Test creating a note-tag relationship."""
        note_tag = NoteTag.objects.create(
            note=self.note,
            tag=self.tag
        )
        self.assertEqual(note_tag.note, self.note)
        self.assertEqual(note_tag.tag, self.tag)
    
    def test_note_tag_str_method(self):
        """Test string representation of note-tag relationship."""
        note_tag = NoteTag.objects.create(
            note=self.note,
            tag=self.tag
        )
        self.assertEqual(str(note_tag), 'Test Note - Python')


class NoteViewsTest(TestCase):
    """Test cases for note views."""
    
    def setUp(self):
        """Set up test client and data."""
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
        """Test that note creation requires authentication."""
        response = self.client.get(
            reverse('notes:note_create', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)
    
    def test_note_create_get(self):
        """Test GET request to note create view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_create', kwargs={'notebook_id': self.notebook.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/note_create.html')
    
    def test_note_create_post(self):
        """Test POST request to create a new note."""
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
        
        # Check note was created
        note = Note.objects.get(title='New Note')
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.notebook, self.notebook)
        self.assertEqual(note.content, 'New content')
    
    def test_note_detail_view(self):
        """Test note detail view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_detail', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/note_detail.html')
        self.assertContains(response, 'Test Note')
        self.assertContains(response, 'Test content')
    
    def test_note_update_get(self):
        """Test GET request to note update view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('notes:note_edit', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Note')
    
    def test_note_update_post(self):
        """Test POST request to update a note."""
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
        
        # Check note was updated
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'Updated Note')
        self.assertEqual(self.note.content, 'Updated content')
    
    def test_note_delete_post(self):
        """Test POST request to delete a note."""
        self.client.login(username='testuser', password='testpass123')
        note_id = self.note.id
        response = self.client.post(
            reverse('notes:note_delete', kwargs={'note_id': note_id})
        )
        self.assertEqual(response.status_code, 302)
        
        # Check note was deleted
        with self.assertRaises(Note.DoesNotExist):
            Note.objects.get(id=note_id)
    
    def test_note_toggle_pin(self):
        """Test toggling pin status of a note."""
        self.client.login(username='testuser', password='testpass123')
        self.assertFalse(self.note.is_pinned)
        
        # Toggle to pinned
        response = self.client.post(
            reverse('notes:note_toggle_pin', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 302)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_pinned)
        
        # Toggle back to unpinned
        response = self.client.post(
            reverse('notes:note_toggle_pin', kwargs={'note_id': self.note.id})
        )
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_pinned)


class TagViewsTest(TestCase):
    """Test cases for tag views."""
    
    def setUp(self):
        """Set up test client and data."""
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
        """Test that tag list requires authentication."""
        response = self.client.get(reverse('notes:tag_list'))
        self.assertEqual(response.status_code, 302)
    
    def test_tag_list_view(self):
        """Test tag list view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('notes:tag_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notes/tag_list.html')
        self.assertContains(response, 'Python')
    
    def test_tag_create_post(self):
        """Test POST request to create a new tag."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Django',
            'color': '#10b981'
        }
        response = self.client.post(reverse('notes:tag_create'), data)
        self.assertEqual(response.status_code, 302)
        
        # Check tag was created
        tag = Tag.objects.get(name='Django')
        self.assertEqual(tag.user, self.user)
        self.assertEqual(tag.color, '#10b981')
    
    def test_tag_create_duplicate_name(self):
        """Test creating tag with duplicate name."""
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
    """Test cases for note-tag relationship views."""
    
    def setUp(self):
        """Set up test data."""
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
        """Test adding a tag to a note."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('notes:note_add_tag', kwargs={'note_id': self.note.id}),
            {'tag_id': self.tag.id}
        )
        self.assertEqual(response.status_code, 302)
        
        # Check tag was added
        self.assertTrue(NoteTag.objects.filter(note=self.note, tag=self.tag).exists())
    
    def test_remove_tag_from_note(self):
        """Test removing a tag from a note."""
        # First add the tag
        NoteTag.objects.create(note=self.note, tag=self.tag)
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('notes:note_remove_tag', kwargs={
                'note_id': self.note.id,
                'tag_id': self.tag.id
            })
        )
        self.assertEqual(response.status_code, 302)
        
        # Check tag was removed
        self.assertFalse(NoteTag.objects.filter(note=self.note, tag=self.tag).exists())


class NotePermissionsTest(TestCase):
    """Test cases for note permissions and security."""
    
    def setUp(self):
        """Set up test users and notes."""
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
        """Test that users cannot view notes of other users."""
        self.client.login(username='user2', password='pass123')
        response = self.client.get(
            reverse('notes:note_detail', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 404)
    
    def test_user_cannot_edit_other_user_note(self):
        """Test that users cannot edit notes of other users."""
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('notes:note_edit', kwargs={'note_id': self.note.id}),
            {'title': 'Hacked', 'content': 'Hacked content'}
        )
        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'User1 Note')
    
    def test_user_cannot_delete_other_user_note(self):
        """Test that users cannot delete notes of other users."""
        self.client.login(username='user2', password='pass123')
        response = self.client.post(
            reverse('notes:note_delete', kwargs={'note_id': self.note.id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

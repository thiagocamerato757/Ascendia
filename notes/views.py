"""
Notes views module.

This module contains all class-based views for managing notes, tags,
and note-tag relationships. All views require user authentication.
"""

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from workspace.models import Notebook
from .models import Note, Tag, NoteTag


class NoteCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new note within a specific notebook.
    
    The note is automatically associated with the authenticated user
    and the notebook specified in the URL.
    
    Attributes:
        model: The Note model
        template_name: Path to the create/edit template
        fields: List of fields to include in the form
    """
    model = Note
    template_name = 'notes/note_create.html'
    fields = ['title', 'content']
    
    def dispatch(self, request, *args, **kwargs):
        """
        Load and validate notebook before processing request.
        
        Ensures the notebook exists and belongs to the current user.
        
        Args:
            request: The HTTP request object
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments including 'notebook_id'
            
        Returns:
            HttpResponse: The response from the parent dispatch method
            
        Raises:
            Http404: If notebook doesn't exist or doesn't belong to user
        """
        self.notebook = get_object_or_404(Notebook, id=kwargs['notebook_id'], user=request.user)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """
        Add notebook to the template context.
        
        Args:
            **kwargs: Base context data from parent class
            
        Returns:
            dict: Context data with 'notebook' key added
        """
        context = super().get_context_data(**kwargs)
        context['notebook'] = self.notebook
        return context
    
    def form_valid(self, form):
        """
        Associate note with notebook and user before saving.
        
        Args:
            form: The validated Note form instance
            
        Returns:
            HttpResponse: Redirect to notebook detail page with success message
        """
        form.instance.notebook = self.notebook
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Note "{self.object.title}" created successfully! 📝')
        return response
    
    def get_success_url(self):
        """
        Return URL to redirect to after successful creation.
        
        Returns:
            str: URL to the parent notebook's detail page
        """
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id})


class NoteDetailView(LoginRequiredMixin, DetailView):
    """
    Display detailed view of a single note.
    
    Shows note content, metadata, and associated tags.
    Uses select_related for optimized database queries.
    
    Attributes:
        model: The Note model
        template_name: Path to the detail template
        context_object_name: Name for the context variable
        pk_url_kwarg: URL parameter name for note ID
    """
    model = Note
    template_name = 'notes/note_detail.html'
    context_object_name = 'note'
    pk_url_kwarg = 'note_id'
    
    def get_queryset(self):
        """
        Return only notes owned by current user with optimized queries.
        
        Uses select_related to fetch related notebook in the same query.
        
        Returns:
            QuerySet: Filtered and optimized Note objects
        """
        return Note.objects.filter(user=self.request.user).select_related('notebook')
    
    def get_context_data(self, **kwargs):
        """
        Add note tags to the context.
        
        Fetches all tags associated with this note using optimized queries.
        
        Args:
            **kwargs: Base context data from parent class
            
        Returns:
            dict: Context data with 'tags' key added
        """
        context = super().get_context_data(**kwargs)
        context['tags'] = self.object.note_tags.select_related('tag').all()
        return context


class NoteUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edit an existing note.
    
    Allows users to update the title and content of their notes.
    Reuses the same template as NoteCreateView.
    
    Attributes:
        model: The Note model
        template_name: Path to the create/edit template
        fields: List of editable fields
        pk_url_kwarg: URL parameter name for note ID
    """
    model = Note
    template_name = 'notes/note_create.html'
    fields = ['title', 'content']
    pk_url_kwarg = 'note_id'
    
    def get_queryset(self):
        """
        Return only notes owned by the current user.
        
        Returns:
            QuerySet: Filtered Note objects
        """
        return Note.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        """
        Add notebook and edit flag to context.
        
        Args:
            **kwargs: Base context data from parent class
            
        Returns:
            dict: Context data with 'notebook' and 'is_edit' keys
        """
        context = super().get_context_data(**kwargs)
        context['notebook'] = self.object.notebook
        context['is_edit'] = True
        return context
    
    def form_valid(self, form):
        """
        Display success message when note is updated.
        
        Args:
            form: The validated Note form instance
            
        Returns:
            HttpResponse: Redirect to note detail page
        """
        response = super().form_valid(form)
        messages.success(self.request, f'Note "{self.object.title}" updated successfully! ✨')
        return response
    
    def get_success_url(self):
        """
        Return URL to redirect to after successful update.
        
        Returns:
            str: URL to the note detail page
        """
        return reverse('notes:note_detail', kwargs={'note_id': self.object.id})


class NoteDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete a note with confirmation.
    
    Displays a confirmation page before deleting the note.
    After deletion, redirects to the parent notebook's detail page.
    
    Attributes:
        model: The Note model
        template_name: Path to the delete confirmation template
        pk_url_kwarg: URL parameter name for note ID
    """
    model = Note
    template_name = 'notes/note_delete.html'
    pk_url_kwarg = 'note_id'
    
    def get_queryset(self):
        """
        Return only notes owned by the current user.
        
        Returns:
            QuerySet: Filtered Note objects
        """
        return Note.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        """
        Return URL to redirect to after successful deletion.
        
        Returns:
            str: URL to the parent notebook's detail page
        """
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.notebook.id})
    
    def form_valid(self, form):
        """
        Display success message when note is deleted.
        
        Stores note title before deletion for the success message.
        
        Args:
            form: The deletion confirmation form
            
        Returns:
            HttpResponse: Redirect to notebook detail page
        """
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f'Note "{title}" deleted successfully.')
        return response


class NoteTogglePinView(LoginRequiredMixin, View):
    """
    Toggle the pinned status of a note.
    
    Pinned notes appear first in listings. Supports both AJAX
    and regular POST requests.
    
    POST Parameters:
        note_id (int): ID of the note to toggle
        
    Returns:
        For AJAX: JSON with success status and is_pinned boolean
        For POST: Redirect to note detail page
    """
    
    def post(self, request, note_id):
        """
        Handle POST request to toggle pin status.
        
        Args:
            request: The HTTP request object
            note_id (int): ID of the note to toggle
            
        Returns:
            JsonResponse: If AJAX request, returns JSON with status
            HttpResponseRedirect: If regular POST, redirects to detail page
        """
        note = get_object_or_404(Note, id=note_id, user=request.user)
        note.is_pinned = not note.is_pinned
        note.save()
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_pinned': note.is_pinned
            })
        
        # Handle regular POST requests
        status = 'pinned' if note.is_pinned else 'unpinned'
        messages.success(request, f'Note {status}!')
        return redirect('notes:note_detail', note_id=note.id)


class TagListView(LoginRequiredMixin, ListView):
    """
    Display a list of all tags created by the user.
    
    Tags are used to organize and categorize notes across notebooks.
    
    Attributes:
        model: The Tag model
        template_name: Path to the list template
        context_object_name: Name for the context variable
    """
    model = Tag
    template_name = 'notes/tag_list.html'
    context_object_name = 'tags'
    
    def get_queryset(self):
        """
        Return only tags created by the current user.
        
        Returns:
            QuerySet: Filtered Tag objects ordered by name
        """
        return Tag.objects.filter(user=self.request.user)


class TagCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new tag for organizing notes.
    
    Validates that tag names are unique per user.
    If a tag with the same name exists, displays info message
    instead of creating duplicate.
    
    Attributes:
        model: The Tag model
        template_name: Path to the create template
        fields: List of fields to include in form
        success_url: URL to redirect to after successful creation
    """
    model = Tag
    template_name = 'notes/tag_create.html'
    fields = ['name', 'color']
    success_url = reverse_lazy('notes:tag_list')
    
    def form_valid(self, form):
        """
        Associate tag with user and check for duplicates.
        
        Args:
            form: The validated Tag form instance
            
        Returns:
            HttpResponse: Redirect to tag list with appropriate message
        """
        form.instance.user = self.request.user
        
        # Check if tag already exists for this user
        existing_tag = Tag.objects.filter(
            name=form.cleaned_data['name'],
            user=self.request.user
        ).first()
        
        if existing_tag:
            messages.info(self.request, f'Tag "{existing_tag.name}" already exists.')
            return redirect('notes:tag_list')
        
        response = super().form_valid(form)
        messages.success(self.request, f'Tag "{self.object.name}" created!')
        return response


class NoteAddTagView(LoginRequiredMixin, View):
    """
    Add an existing tag to a note.
    
    Creates a NoteTag relationship between the specified note and tag.
    Uses get_or_create to prevent duplicate associations.
    
    POST Parameters:
        note_id (int): ID of the note
        tag_id (int): ID of the tag to add
    """
    
    def post(self, request, note_id):
        """
        Handle POST request to add tag to note.
        
        Args:
            request: The HTTP request object with 'tag_id' in POST data
            note_id (int): ID of the note to add tag to
            
        Returns:
            HttpResponseRedirect: Redirect to note detail page
        """
        note = get_object_or_404(Note, id=note_id, user=request.user)
        tag_id = request.POST.get('tag_id')
        tag = get_object_or_404(Tag, id=tag_id, user=request.user)
        
        NoteTag.objects.get_or_create(note=note, tag=tag)
        messages.success(request, f'Tag "{tag.name}" added to note!')
        
        return redirect('notes:note_detail', note_id=note.id)


class NoteRemoveTagView(LoginRequiredMixin, View):
    """
    Remove a tag from a note.
    
    Deletes the NoteTag relationship between the specified note and tag.
    The tag itself is not deleted, only its association with the note.
    
    POST Parameters:
        note_id (int): ID of the note
        tag_id (int): ID of the tag to remove
    """
    
    def post(self, request, note_id, tag_id):
        """
        Handle POST request to remove tag from note.
        
        Args:
            request: The HTTP request object
            note_id (int): ID of the note to remove tag from
            tag_id (int): ID of the tag to remove
            
        Returns:
            HttpResponseRedirect: Redirect to note detail page
        """
        note = get_object_or_404(Note, id=note_id, user=request.user)
        tag = get_object_or_404(Tag, id=tag_id, user=request.user)
        
        NoteTag.objects.filter(note=note, tag=tag).delete()
        messages.success(request, f'Tag "{tag.name}" removed from note!')
        
        return redirect('notes:note_detail', note_id=note.id)

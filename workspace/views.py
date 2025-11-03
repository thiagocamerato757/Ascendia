"""
Workspace views module.

This module contains all class-based views for managing notebooks (workspaces).
All views require user authentication via LoginRequiredMixin.
"""

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from .models import Notebook
from .forms import NotebookForm


class WorkspaceHomeView(LoginRequiredMixin, ListView):
    """
    Display a list of all notebooks belonging to the authenticated user.
    
    The notebooks are displayed in a grid layout, ordered by favorite status
    first, then by most recently updated.
    
    Attributes:
        model: The Notebook model
        template_name: Path to the home template
        context_object_name: Name for the context variable containing notebooks
    """
    model = Notebook
    template_name = 'workspace/home.html'
    context_object_name = 'notebooks'
    
    def get_queryset(self):
        """
        Return only notebooks owned by the current user.
        
        Notebooks are ordered by favorite status (favorites first),
        then by most recently updated.
        
        Returns:
            QuerySet: Filtered and ordered Notebook objects
        """
        return Notebook.objects.filter(user=self.request.user).order_by('-is_favorite', '-updated_at')


class NotebookDetailView(LoginRequiredMixin, DetailView):
    """
    Display detailed view of a single notebook with all its notes.
    
    Shows notebook information, metadata, and a list of all notes
    contained within the notebook.
    
    Attributes:
        model: The Notebook model
        template_name: Path to the detail template
        context_object_name: Name for the context variable
        pk_url_kwarg: URL parameter name for notebook ID
    """
    model = Notebook
    template_name = 'workspace/notebook_detail.html'
    context_object_name = 'notebook'
    pk_url_kwarg = 'notebook_id'
    
    def get_queryset(self):
        """
        Return only notebooks owned by the current user.
        
        Returns:
            QuerySet: Filtered Notebook objects
        """
        return Notebook.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        """
        Add notes and notes count to the context.
        
        Args:
            **kwargs: Base context data from parent class
            
        Returns:
            dict: Context data with added 'notes' and 'notes_count' keys
        """
        context = super().get_context_data(**kwargs)
        context['notes'] = self.object.notes.all()
        context['notes_count'] = context['notes'].count()
        return context


class NotebookCreateView(LoginRequiredMixin, CreateView):
    """
    Handle creation of new notebooks.
    
    Displays a form for creating a new notebook with fields:
    - Title (required)
    - Description (optional)
    - Color (choice from predefined colors)
    - Favorite status (boolean)
    
    Automatically associates the notebook with the authenticated user.
    
    Attributes:
        model: The Notebook model
        form_class: Form class for notebook creation
        template_name: Path to the create/edit template
    """
    model = Notebook
    form_class = NotebookForm
    template_name = 'workspace/notebook_create.html'
    
    def form_valid(self, form):
        """
        Associate notebook with current user and display success message.
        
        Args:
            form: The validated NotebookForm instance
            
        Returns:
            HttpResponse: Redirect to the newly created notebook's detail page
        """
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{self.object.title}" created successfully! 🎉')
        return response
    
    def form_invalid(self, form):
        """
        Display error message when form validation fails.
        
        Args:
            form: The invalid NotebookForm instance
            
        Returns:
            HttpResponse: Re-render the form with errors
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        """
        Return URL to redirect to after successful creation.
        
        Returns:
            str: URL to the notebook detail page
        """
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.id})


class NotebookUpdateView(LoginRequiredMixin, UpdateView):
    """
    Handle editing of existing notebooks.
    
    Allows users to update notebook information including title,
    description, color, and favorite status. Reuses the same
    template as NotebookCreateView.
    
    Attributes:
        model: The Notebook model
        form_class: Form class for notebook editing
        template_name: Path to the create/edit template
        pk_url_kwarg: URL parameter name for notebook ID
    """
    model = Notebook
    form_class = NotebookForm
    template_name = 'workspace/notebook_create.html'
    pk_url_kwarg = 'notebook_id'
    
    def get_queryset(self):
        """
        Return only notebooks owned by the current user.
        
        Returns:
            QuerySet: Filtered Notebook objects
        """
        return Notebook.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        """
        Add is_edit flag to distinguish from create mode.
        
        Args:
            **kwargs: Base context data from parent class
            
        Returns:
            dict: Context data with 'is_edit' flag set to True
        """
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        return context
    
    def form_valid(self, form):
        """
        Display success message when notebook is updated.
        
        Args:
            form: The validated NotebookForm instance
            
        Returns:
            HttpResponse: Redirect to the notebook's detail page
        """
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{self.object.title}" updated successfully! ✨')
        return response
    
    def form_invalid(self, form):
        """
        Display error message when form validation fails.
        
        Args:
            form: The invalid NotebookForm instance
            
        Returns:
            HttpResponse: Re-render the form with errors
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        """
        Return URL to redirect to after successful update.
        
        Returns:
            str: URL to the notebook detail page
        """
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.id})


class NotebookDeleteView(LoginRequiredMixin, DeleteView):
    """
    Handle deletion of notebooks with confirmation.
    
    Displays a confirmation page before deleting the notebook.
    Shows warning about data loss (all notes will be deleted).
    
    Attributes:
        model: The Notebook model
        template_name: Path to the delete confirmation template
        pk_url_kwarg: URL parameter name for notebook ID
        success_url: URL to redirect to after successful deletion
    """
    model = Notebook
    template_name = 'workspace/notebook_delete.html'
    pk_url_kwarg = 'notebook_id'
    success_url = reverse_lazy('workspace:home')
    
    def get_queryset(self):
        """
        Return only notebooks owned by the current user.
        
        Returns:
            QuerySet: Filtered Notebook objects
        """
        return Notebook.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        """
        Display success message when notebook is deleted.
        
        Stores the notebook title before deletion for the success message.
        
        Args:
            form: The deletion confirmation form
            
        Returns:
            HttpResponse: Redirect to workspace home
        """
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{title}" deleted successfully.')
        return response


class NotebookToggleFavoriteView(LoginRequiredMixin, View):
    """
    Toggle the favorite status of a notebook.
    
    This view handles both AJAX and regular POST requests.
    For AJAX requests, returns JSON response with updated status.
    For regular POST, redirects to notebook detail page.
    
    POST Parameters:
        notebook_id (int): ID of the notebook to toggle
        
    Returns:
        For AJAX: JSON with success status and is_favorite boolean
        For POST: Redirect to notebook detail page
    """
    
    def post(self, request, notebook_id):
        """
        Handle POST request to toggle favorite status.
        
        Args:
            request: The HTTP request object
            notebook_id (int): ID of the notebook to toggle
            
        Returns:
            JsonResponse: If AJAX request, returns JSON with status
            HttpResponseRedirect: If regular POST, redirects to detail page
        """
        notebook = get_object_or_404(Notebook, id=notebook_id, user=request.user)
        notebook.is_favorite = not notebook.is_favorite
        notebook.save()
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_favorite': notebook.is_favorite
            })
        
        # Handle regular POST requests
        status = 'added to' if notebook.is_favorite else 'removed from'
        messages.success(request, f'Notebook {status} favorites!')
        return redirect('workspace:notebook_detail', notebook_id=notebook.id)

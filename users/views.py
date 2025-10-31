"""
Users app views.

This module contains class-based views for user registration
and authentication management.
"""

from typing import Any
from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpRequest, HttpResponse
from .forms import SignUpForm


class SignUpView(CreateView):
    """
    New user registration view.
    
    Allows new users to sign up for the system. After registration,
    the user is automatically logged in and redirected to the homepage
    with a welcome message.
    
    Attributes:
        form_class (SignUpForm): Custom registration form
        template_name (str): HTML template for rendering
        success_url (str): Redirect URL after success
    """
    
    form_class = SignUpForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('home')
    
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Checks if the user is already authenticated before processing the request.
        
        Already authenticated users are redirected to the homepage,
        preventing duplicate registrations.
        
        Args:
            request (HttpRequest): HTTP request
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            HttpResponse: HTTP response (redirect or normal view)
        """
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form: SignUpForm) -> HttpResponse:
        """
        Processes the valid form.
        
        Saves the new user, performs automatic login and displays welcome
        message before redirecting to the homepage.
        
        Args:
            form (SignUpForm): Validated form with user data
            
        Returns:
            HttpResponse: Redirect to homepage
        """
        user: User = form.save()
        login(self.request, user)
        messages.success(
            self.request, 
            f'Welcome to Ascendia, {user.username}!',
            extra_tags='success'
        )
        return redirect(self.success_url)


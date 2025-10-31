"""
Custom authentication views.

This module contains custom views for user authentication,
extending Django's default views with additional functionalities.
"""

from typing import Any
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse


class CustomLoginView(LoginView):
    """
    Custom login view.
    
    Extends Django's default LoginView by adding a welcome
    message after successful login.
    
    Attributes:
        template_name (str): HTML template for rendering the login form
    """
    
    template_name = 'users/login.html'
    
    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        """
        Processes the valid login form.
        
        Authenticates the user and adds a welcome message
        before redirecting to the configured page.
        
        Args:
            form (AuthenticationForm): Validated authentication form
            
        Returns:
            HttpResponse: Redirect to the next page (usually homepage)
        """
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Welcome back, {self.request.user.username}!',
            extra_tags='success'
        )
        return response

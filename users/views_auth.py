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
    message after successful login and "Remember Me" functionality.
    
    Attributes:
        template_name (str): HTML template for rendering the login form
    """
    
    template_name = 'users/login.html'
    
    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        """
        Processes the valid login form.
        
        Authenticates the user, handles "Remember Me" functionality,
        and adds a welcome message before redirecting.
        
        Args:
            form (AuthenticationForm): Validated authentication form
            
        Returns:
            HttpResponse: Redirect to the next page (usually homepage)
        """
        # Call parent to log in the user
        response = super().form_valid(form)
        
        # Handle "Remember Me" functionality after login
        remember_me = self.request.POST.get('remember_me')
        
        if not remember_me:
            # Expire when ALL browser windows/tabs are closed
            # Set to 0 to use session-only cookies
            self.request.session.set_expiry(0)
            # Force session to be marked as modified
            self.request.session.modified = True
        else:
            # Session expires after 2 weeks (1209600 seconds)
            self.request.session.set_expiry(1209600)
            self.request.session.modified = True
        
        messages.success(
            self.request, 
            f'Welcome back, {self.request.user.username}!',
            extra_tags='success'
        )
        return response

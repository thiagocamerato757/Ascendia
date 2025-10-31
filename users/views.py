"""
Users app views.

This module contains class-based views for user registration
and authentication management.
"""

from typing import Any
from django.shortcuts import redirect, render
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpRequest, HttpResponse
from .forms import SignUpForm, UserUpdateForm, ProfileUpdateForm


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


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """
    User profile view with edit functionality.
    
    Allows authenticated users to view and update their profile information,
    including username, email, name, and avatar image.
    
    Args:
        request (HttpRequest): HTTP request
        
    Returns:
        HttpResponse: Rendered profile page
    """
    # Ensure user has a profile
    from .models import Profile
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, 
            request.FILES, 
            instance=profile
        )
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(
                request,
                'Your profile has been updated successfully!',
                extra_tags='success'
            )
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    
    return render(request, 'users/profile.html', context)


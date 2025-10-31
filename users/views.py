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
    from django.core.files.base import ContentFile
    import base64
    import uuid
    
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, 
            request.FILES, 
            instance=profile
        )
        
        # Avatar is now handled via AJAX, so we don't process it here
        # Just save user info and whatsapp
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            # Don't save avatar field from form, it's handled by AJAX
            profile.whatsapp = profile_form.cleaned_data.get('whatsapp')
            profile.save()
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


@login_required
def update_avatar(request: HttpRequest) -> HttpResponse:
    """
    AJAX endpoint to update or delete avatar.
    
    Args:
        request (HttpRequest): HTTP request with avatar data
        
    Returns:
        HttpResponse: JSON response with status
    """
    from django.http import JsonResponse
    from .models import Profile
    from django.core.files.base import ContentFile
    import base64
    import uuid
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    try:
        # Handle avatar deletion
        delete_avatar = request.POST.get('delete_avatar')
        if delete_avatar == 'true':
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
                profile.save()
            return JsonResponse({
                'success': True,
                'message': 'Avatar removed successfully',
                'avatar_url': None
            })
        
        # Handle cropped avatar upload
        avatar_cropped = request.POST.get('avatar_cropped')
        if avatar_cropped and avatar_cropped.startswith('data:image'):
            # Delete old avatar if exists
            if profile.avatar:
                profile.avatar.delete(save=False)
            
            # Extract base64 data
            format, imgstr = avatar_cropped.split(';base64,')
            ext = format.split('/')[-1]
            
            # Decode and save
            data = ContentFile(base64.b64decode(imgstr))
            file_name = f'avatar_{request.user.username}_{uuid.uuid4()}.{ext}'
            profile.avatar.save(file_name, data, save=True)
            
            return JsonResponse({
                'success': True,
                'message': 'Avatar updated successfully',
                'avatar_url': profile.avatar.url
            })
        
        return JsonResponse({'success': False, 'error': 'No avatar data provided'}, status=400)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


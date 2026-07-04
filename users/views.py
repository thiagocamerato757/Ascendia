import base64
import uuid
from typing import Any
from django.shortcuts import redirect, render
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpRequest, HttpResponse, JsonResponse
from .forms import SignUpForm, UserUpdateForm, ProfileUpdateForm
from .models import Profile


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('home')

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SignUpForm) -> HttpResponse:
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
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=profile
        )

        # Avatar uploads go through the AJAX endpoint (update_avatar),
        # so only user info and whatsapp are saved here.
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile.whatsapp = profile_form.cleaned_data.get('whatsapp')
            profile.save()
            messages.success(
                request,
                'Your profile has been updated.',
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
    """AJAX endpoint to upload a cropped avatar or delete the current one."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

    profile, created = Profile.objects.get_or_create(user=request.user)

    try:
        delete_avatar = request.POST.get('delete_avatar')
        if delete_avatar == 'true':
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
                profile.save()
            return JsonResponse({
                'success': True,
                'message': 'Avatar removed',
                'avatar_url': None
            })

        avatar_cropped = request.POST.get('avatar_cropped')
        if avatar_cropped and avatar_cropped.startswith('data:image'):
            if profile.avatar:
                profile.avatar.delete(save=False)

            format, imgstr = avatar_cropped.split(';base64,')
            ext = format.split('/')[-1]

            data = ContentFile(base64.b64decode(imgstr))
            file_name = f'avatar_{request.user.username}_{uuid.uuid4()}.{ext}'
            profile.avatar.save(file_name, data, save=True)

            return JsonResponse({
                'success': True,
                'message': 'Avatar updated',
                'avatar_url': profile.avatar.url
            })

        return JsonResponse({'success': False, 'error': 'No avatar data provided'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

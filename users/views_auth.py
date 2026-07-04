from typing import Any
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse


class CustomLoginView(LoginView):
    template_name = 'users/login.html'

    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        response = super().form_valid(form)

        remember_me = self.request.POST.get('remember_me')

        if not remember_me:
            # Session-only cookie: expires when the browser is closed
            self.request.session.set_expiry(0)
            self.request.session.modified = True
        else:
            # Keep the session for 2 weeks
            self.request.session.set_expiry(1209600)
            self.request.session.modified = True

        messages.success(
            self.request,
            f'Welcome back, {self.request.user.username}!',
            extra_tags='success'
        )
        return response

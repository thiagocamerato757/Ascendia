from django.contrib.auth.views import LoginView
from django.contrib import messages


class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Welcome back, {self.request.user.username}!',
            extra_tags='success'
        )
        return response

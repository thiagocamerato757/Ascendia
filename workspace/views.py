from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from .models import Notebook
from .forms import NotebookForm


class WorkspaceHomeView(LoginRequiredMixin, ListView):
    model = Notebook
    template_name = 'workspace/home.html'
    context_object_name = 'notebooks'

    def get_queryset(self):
        return Notebook.objects.filter(user=self.request.user).order_by('-is_favorite', '-updated_at')


class NotebookDetailView(LoginRequiredMixin, DetailView):
    model = Notebook
    template_name = 'workspace/notebook_detail.html'
    context_object_name = 'notebook'
    pk_url_kwarg = 'notebook_id'

    def get_queryset(self):
        return Notebook.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notes'] = self.object.notes.all()
        context['notes_count'] = context['notes'].count()
        return context


class NotebookCreateView(LoginRequiredMixin, CreateView):
    model = Notebook
    form_class = NotebookForm
    template_name = 'workspace/notebook_create.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{self.object.title}" created.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.id})


class NotebookUpdateView(LoginRequiredMixin, UpdateView):
    model = Notebook
    form_class = NotebookForm
    template_name = 'workspace/notebook_create.html'
    pk_url_kwarg = 'notebook_id'

    def get_queryset(self):
        return Notebook.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{self.object.title}" updated.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.id})


class NotebookDeleteView(LoginRequiredMixin, DeleteView):
    model = Notebook
    template_name = 'workspace/notebook_delete.html'
    pk_url_kwarg = 'notebook_id'
    success_url = reverse_lazy('workspace:home')

    def get_queryset(self):
        return Notebook.objects.filter(user=self.request.user)

    def form_valid(self, form):
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f'Notebook "{title}" deleted.')
        return response


class NotebookToggleFavoriteView(LoginRequiredMixin, View):
    def post(self, request, notebook_id):
        notebook = get_object_or_404(Notebook, id=notebook_id, user=request.user)
        notebook.is_favorite = not notebook.is_favorite
        notebook.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_favorite': notebook.is_favorite
            })

        status = 'added to' if notebook.is_favorite else 'removed from'
        messages.success(request, f'Notebook {status} favorites.')
        return redirect('workspace:notebook_detail', notebook_id=notebook.id)

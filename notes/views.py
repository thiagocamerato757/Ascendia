from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from workspace.models import Notebook

from .forms import NoteForm, TagForm
from .models import Note, NoteTag, Tag


class NoteCreateView(LoginRequiredMixin, CreateView):
    model = Note
    template_name = 'notes/note_create.html'
    form_class = NoteForm

    def dispatch(self, request, *args, **kwargs):
        # LoginRequiredMixin only runs inside super().dispatch, so guard the
        # notebook lookup against anonymous users
        if request.user.is_authenticated:
            self.notebook = get_object_or_404(Notebook, id=kwargs['notebook_id'], user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notebook'] = self.notebook
        return context

    def form_valid(self, form):
        form.instance.notebook = self.notebook
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, _('Note "%(title)s" created.') % {'title': self.object.title})
        return response

    def get_success_url(self):
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.notebook.id})


class NoteDetailView(LoginRequiredMixin, DetailView):
    model = Note
    template_name = 'notes/note_detail.html'
    context_object_name = 'note'
    pk_url_kwarg = 'note_id'

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user).select_related('notebook')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = self.object.note_tags.select_related('tag').all()
        return context


class NoteUpdateView(LoginRequiredMixin, UpdateView):
    model = Note
    template_name = 'notes/note_create.html'
    form_class = NoteForm
    pk_url_kwarg = 'note_id'

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notebook'] = self.object.notebook
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Note "%(title)s" updated.') % {'title': self.object.title})
        return response

    def get_success_url(self):
        return reverse('notes:note_detail', kwargs={'note_id': self.object.id})


class NoteDeleteView(LoginRequiredMixin, DeleteView):
    model = Note
    template_name = 'notes/note_delete.html'
    pk_url_kwarg = 'note_id'

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)

    def get_success_url(self):
        return reverse('workspace:notebook_detail', kwargs={'notebook_id': self.object.notebook.id})

    def form_valid(self, form):
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, _('Note "%(title)s" deleted.') % {'title': title})
        return response


class NoteTogglePinView(LoginRequiredMixin, View):
    def post(self, request, note_id):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        note.is_pinned = not note.is_pinned
        note.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_pinned': note.is_pinned
            })

        if note.is_pinned:
            messages.success(request, _('Note pinned.'))
        else:
            messages.success(request, _('Note unpinned.'))
        return redirect('notes:note_detail', note_id=note.id)


class TagListView(LoginRequiredMixin, ListView):
    model = Tag
    template_name = 'notes/tag_list.html'
    context_object_name = 'tags'

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)


class TagCreateView(LoginRequiredMixin, CreateView):
    model = Tag
    template_name = 'notes/tag_create.html'
    form_class = TagForm
    success_url = reverse_lazy('notes:tag_list')

    def form_valid(self, form):
        form.instance.user = self.request.user

        existing_tag = Tag.objects.filter(
            name=form.cleaned_data['name'],
            user=self.request.user
        ).first()

        if existing_tag:
            messages.info(self.request, _('Tag "%(name)s" already exists.') % {'name': existing_tag.name})
            return redirect('notes:tag_list')

        response = super().form_valid(form)
        messages.success(self.request, _('Tag "%(name)s" created.') % {'name': self.object.name})
        return response


class NoteAddTagView(LoginRequiredMixin, View):
    def post(self, request, note_id):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        tag_id = request.POST.get('tag_id')
        tag = get_object_or_404(Tag, id=tag_id, user=request.user)

        NoteTag.objects.get_or_create(note=note, tag=tag)
        messages.success(request, _('Tag "%(name)s" added.') % {'name': tag.name})

        return redirect('notes:note_detail', note_id=note.id)


class NoteRemoveTagView(LoginRequiredMixin, View):
    def post(self, request, note_id, tag_id):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        tag = get_object_or_404(Tag, id=tag_id, user=request.user)

        NoteTag.objects.filter(note=note, tag=tag).delete()
        messages.success(request, _('Tag "%(name)s" removed.') % {'name': tag.name})

        return redirect('notes:note_detail', note_id=note.id)

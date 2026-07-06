from django import forms
from workspace.forms import COLOR_CHOICES
from .models import Note, Tag


class NoteForm(forms.ModelForm):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'input-aurora',
            'placeholder': 'Note title',
            'autofocus': True,
        })
    )

    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'input-aurora',
            'placeholder': 'Write your note here... (optional)',
            'rows': 12,
        })
    )

    class Meta:
        model = Note
        fields = ['title', 'content']


class TagForm(forms.ModelForm):
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'input-aurora',
            'placeholder': 'Tag name',
            'autofocus': True,
        })
    )

    color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        initial='#06b6d4',
        widget=forms.RadioSelect
    )

    class Meta:
        model = Tag
        fields = ['name', 'color']

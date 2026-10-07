from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Notebook

COLOR_CHOICES = [
    ('#06b6d4', _('Cyan')),
    ('#10b981', _('Mint')),
    ('#3b82f6', _('Blue')),
    ('#8b5cf6', _('Purple')),
    ('#ec4899', _('Pink')),
    ('#f59e0b', _('Amber')),
    ('#ef4444', _('Red')),
    ('#14b8a6', _('Teal')),
]


class NotebookForm(forms.ModelForm):
    """Form for creating and editing notebooks"""

    COLOR_CHOICES = COLOR_CHOICES

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'c-field__input',
            'placeholder': _('My Learning Notebook'),
            'autofocus': True,
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'c-field__input',
            'placeholder': _('What will you learn in this notebook? (optional)'),
            'rows': 4,
        })
    )
    
    color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        initial='#06b6d4',
        widget=forms.RadioSelect(attrs={
            'class': 'color-picker-radio'
        })
    )
    
    is_favorite = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'c-checkbox__input'
        })
    )
    
    class Meta:
        model = Notebook
        fields = ['title', 'description', 'color', 'is_favorite']

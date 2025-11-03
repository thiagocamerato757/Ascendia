from django import forms
from .models import Notebook


class NotebookForm(forms.ModelForm):
    """Form for creating and editing notebooks"""
    
    COLOR_CHOICES = [
        ('#06b6d4', 'Cyan'),
        ('#10b981', 'Mint'),
        ('#3b82f6', 'Blue'),
        ('#8b5cf6', 'Purple'),
        ('#ec4899', 'Pink'),
        ('#f59e0b', 'Amber'),
        ('#ef4444', 'Red'),
        ('#14b8a6', 'Teal'),
    ]
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'input-aurora',
            'placeholder': 'My Learning Notebook',
            'autofocus': True,
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'input-aurora',
            'placeholder': 'What will you learn in this notebook? (optional)',
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
            'class': 'checkbox-aurora'
        })
    )
    
    class Meta:
        model = Notebook
        fields = ['title', 'description', 'color', 'is_favorite']

"""
Users app forms.

This module contains custom forms for user registration,
with validations and additional fields.
"""

from typing import Any, Dict
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    """
    Custom user registration form.
    
    Extends Django's default UserCreationForm by adding a required email field
    and custom placeholders for better UX.
    
    Attributes:
        email (EmailField): Required email field with placeholder
    """
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email'
        }),
        help_text='Required. Enter a valid email address.',
        label='Email'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Choose a username'
            }),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initializes the form and adds placeholders to password fields.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        super(SignUpForm, self).__init__(*args, **kwargs)
        
        # Add placeholders to password fields
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Confirm your password'
        })

    def save(self, commit: bool = True) -> User:
        """
        Saves the user with the provided email.
        
        Args:
            commit (bool): If True, saves the user to the database.
                          If False, only creates the instance without saving.
        
        Returns:
            User: Created user instance
        """
        user = super(SignUpForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
        
        return user

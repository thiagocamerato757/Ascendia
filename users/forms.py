from typing import Any
from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from .models import Profile


class SignUpForm(UserCreationForm):
    """UserCreationForm with a required email field."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
            'class': 'input-aurora'
        }),
        help_text='Required. Enter a valid email address.',
        label='Email'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Choose a username',
                'class': 'input-aurora'
            }),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Create a password',
            'class': 'input-aurora'
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Confirm your password',
            'class': 'input-aurora'
        })

    def save(self, commit: bool = True) -> User:
        user = super(SignUpForm, self).save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()

        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Enter your username',
            'class': 'input-aurora'
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Enter your password',
            'class': 'input-aurora'
        })


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Enter your email',
            'class': 'input-aurora'
        })


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'placeholder': 'New password',
            'class': 'input-aurora'
        })
        self.fields['new_password2'].widget.attrs.update({
            'placeholder': 'Confirm new password',
            'class': 'input-aurora'
        })


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
            'class': 'input-aurora'
        }),
        label='Email'
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Username',
                'class': 'input-aurora'
            }),
            'first_name': forms.TextInput(attrs={
                'placeholder': 'First name',
                'class': 'input-aurora'
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Last name',
                'class': 'input-aurora'
            }),
        }
        labels = {
            'username': 'Username',
            'first_name': 'First Name',
            'last_name': 'Last Name',
        }


class ProfileUpdateForm(forms.ModelForm):
    whatsapp = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '+55 11 98765-4321',
            'class': 'input-aurora'
        }),
        label='WhatsApp',
        help_text='Enter your WhatsApp number with country code'
    )

    class Meta:
        model = Profile
        fields = ['avatar', 'whatsapp']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'file-input-aurora',
                'accept': 'image/*'
            })
        }
        labels = {
            'avatar': 'Profile Picture',
            'whatsapp': 'WhatsApp'
        }

    def clean_whatsapp(self) -> str:
        whatsapp = self.cleaned_data.get('whatsapp', '')

        if whatsapp:
            cleaned = ''.join(c for c in whatsapp if c.isdigit() or c == '+')

            if not cleaned.startswith('+'):
                raise forms.ValidationError('WhatsApp number must start with country code (e.g., +55)')

            digits = cleaned[1:]
            if len(digits) < 10:
                raise forms.ValidationError('WhatsApp number must have at least 10 digits')

            return whatsapp

        return whatsapp

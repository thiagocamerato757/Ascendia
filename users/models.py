"""
Users app models.

This module contains models related to system users,
including profiles with avatars and extended functionalities.
"""

from typing import Optional
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """
    User profile model.
    
    Extends Django's default User model by adding extra fields
    such as avatar and other personalized information.
    
    Attributes:
        user (User): One-to-one relationship with Django's User model
        avatar (ImageField): User's avatar image (optional)
        whatsapp (CharField): User's WhatsApp number (optional)
    """
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile',
        help_text="User associated with this profile"
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        null=True, 
        blank=True,
        help_text="User's profile picture"
    )
    whatsapp = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="User's WhatsApp number with country code (e.g., +55 11 98765-4321)"
    )
    
    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        ordering = ['user__username']
    
    def __str__(self) -> str:
        """
        Returns string representation of the profile.
        
        Returns:
            str: Username followed by 'Profile'
        """
        return f'{self.user.username} Profile'
    
    @property
    def avatar_url(self) -> Optional[str]:
        """
        Returns the user's avatar URL.
        
        Returns:
            Optional[str]: Avatar URL if it exists, None otherwise
        """
        if self.avatar:
            return self.avatar.url
        return None
    
    @property
    def whatsapp_link(self) -> Optional[str]:
        """
        Returns a WhatsApp click-to-chat URL.
        
        Returns:
            Optional[str]: WhatsApp URL if number exists, None otherwise
        """
        if self.whatsapp:
            # Remove all non-digit characters except +
            cleaned = ''.join(c for c in self.whatsapp if c.isdigit() or c == '+')
            # Remove + for the URL
            number = cleaned.replace('+', '')
            return f'https://wa.me/{number}'
        return None


@receiver(post_save, sender=User)
def create_user_profile(sender: type, instance: User, created: bool, **kwargs) -> None:
    """
    Signal receiver that automatically creates a Profile when a User is created.
    
    Args:
        sender (type): The model that sent the signal (User)
        instance (User): The user instance that was saved
        created (bool): True if a new instance was created
        **kwargs: Additional signal arguments
    """
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender: type, instance: User, **kwargs) -> None:
    """
    Signal receiver that saves the Profile whenever the User is saved.
    
    Args:
        sender (type): The model that sent the signal (User)
        instance (User): The user instance that was saved
        **kwargs: Additional signal arguments
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()

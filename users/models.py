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

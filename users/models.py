from typing import Optional
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Extra user data (avatar, whatsapp) linked one-to-one to User."""
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
        return f'{self.user.username} Profile'

    @property
    def avatar_url(self) -> Optional[str]:
        if self.avatar:
            return self.avatar.url
        return None

    @property
    def whatsapp_link(self) -> Optional[str]:
        """WhatsApp click-to-chat URL, or None if no number is set."""
        if self.whatsapp:
            # wa.me wants digits only, no + or separators
            cleaned = ''.join(c for c in self.whatsapp if c.isdigit() or c == '+')
            number = cleaned.replace('+', '')
            return f'https://wa.me/{number}'
        return None


@receiver(post_save, sender=User)
def create_user_profile(sender: type, instance: User, created: bool, **kwargs) -> None:
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender: type, instance: User, **kwargs) -> None:
    if hasattr(instance, 'profile'):
        instance.profile.save()

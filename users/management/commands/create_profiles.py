"""
Management command to create profiles for users without one.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Profile


class Command(BaseCommand):
    """
    Django management command to create Profile instances for all users
    who don't have one.
    
    Usage: python manage.py create_profiles
    """
    
    help = 'Creates Profile instances for all users without one'

    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Variable length argument list
            **options: Arbitrary keyword arguments
        """
        users_without_profile = []
        
        # Find all users without a profile
        for user in User.objects.all():
            try:
                # Try to access the profile
                _ = user.profile
            except Profile.DoesNotExist:
                # Create profile for this user
                Profile.objects.create(user=user)
                users_without_profile.append(user.username)
        
        if users_without_profile:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created profiles for {len(users_without_profile)} users: '
                    f'{", ".join(users_without_profile)}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles!')
            )

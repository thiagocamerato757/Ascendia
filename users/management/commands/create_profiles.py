from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Profile


class Command(BaseCommand):
    help = 'Creates Profile instances for all users without one'

    def handle(self, *args, **options):
        users_without_profile = []

        for user in User.objects.all():
            try:
                _ = user.profile
            except Profile.DoesNotExist:
                Profile.objects.create(user=user)
                users_without_profile.append(user.username)

        if users_without_profile:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created profiles for {len(users_without_profile)} users: '
                    f'{", ".join(users_without_profile)}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles.')
            )

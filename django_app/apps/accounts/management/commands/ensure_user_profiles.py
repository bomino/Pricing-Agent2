"""
Management command to ensure all users have profiles
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.core.models import Organization


class Command(BaseCommand):
    help = 'Ensures all users have a UserProfile'

    def handle(self, *args, **options):
        # Get or create default organization
        default_org, created = Organization.objects.get_or_create(
            name='Default Organization',
            defaults={
                'code': 'DEFAULT',
                'description': 'Default organization for users'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created default organization'))
        
        # Check all users
        users_without_profile = []
        for user in User.objects.all():
            if not hasattr(user, 'profile'):
                # Create profile for user
                profile = UserProfile.objects.create(
                    user=user,
                    organization=default_org,
                    role='admin' if user.is_superuser else 'user',
                    department='General'
                )
                users_without_profile.append(user.username)
                self.stdout.write(self.style.SUCCESS(f'Created profile for user: {user.username}'))
        
        if not users_without_profile:
            self.stdout.write(self.style.SUCCESS('All users already have profiles'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created profiles for {len(users_without_profile)} users'))
"""
Management command to create user profiles for all users
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.core.models import Organization
from apps.core.rbac import Role


class Command(BaseCommand):
    help = 'Creates user profiles and organizations for all users'

    def handle(self, *args, **options):
        # Create default organization if it doesn't exist
        default_org, created = Organization.objects.get_or_create(
            code='DEFAULT',
            defaults={
                'name': 'Default Organization',
                'type': 'buyer',
                'description': 'Default organization for users'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created default organization: {default_org.name}')
            )
        
        # Create user profiles for all users
        users_without_profiles = User.objects.filter(profile__isnull=True)
        
        for user in users_without_profiles:
            # Determine role based on user properties
            if user.is_superuser:
                role = Role.ADMIN
            elif user.is_staff:
                role = Role.ANALYST
            else:
                role = Role.USER
            
            # Create user profile
            profile = UserProfile.objects.create(
                user=user,
                organization=default_org,
                phone='',
                department='General',
                job_title='Staff',
                role=role
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created profile for user: {user.username} with role: {role}'
                )
            )
        
        # Update existing profiles without organization
        profiles_without_org = UserProfile.objects.filter(organization__isnull=True)
        if profiles_without_org.exists():
            profiles_without_org.update(organization=default_org)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {profiles_without_org.count()} profiles with default organization'
                )
            )
        
        # Summary
        total_users = User.objects.count()
        profiles_count = UserProfile.objects.count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary:\n'
                f'Total users: {total_users}\n'
                f'User profiles: {profiles_count}\n'
                f'Default organization: {default_org.name}'
            )
        )
"""
Management command to set up RBAC roles and demo users
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from apps.core.models import Organization
from apps.accounts.models import UserProfile
from apps.core.rbac import create_roles_and_permissions, assign_role, Role


class Command(BaseCommand):
    help = 'Set up RBAC roles, permissions, and demo users'
    
    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Setting up RBAC system...')
        
        # Create roles and permissions
        create_roles_and_permissions()
        self.stdout.write(self.style.SUCCESS('[OK] Roles and permissions created'))
        
        # Create demo organization
        org, created = Organization.objects.get_or_create(
            code='DEMO2024',
            defaults={
                'name': 'Demo Corporation',
                'type': 'buyer',
                'description': 'Demo organization for testing',
                'website': 'https://demo.vtx.com',
                'email': 'demo@vtx.com',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'[OK] Created organization: {org.name}'))
        
        # Create demo users
        demo_users = [
            {
                'username': 'admin',
                'email': 'admin@vtx.com',
                'password': 'admin123',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'analyst',
                'email': 'analyst@vtx.com',
                'password': 'analyst123',
                'first_name': 'Alice',
                'last_name': 'Analyst',
                'role': Role.ANALYST,
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'user',
                'email': 'user@vtx.com',
                'password': 'user123',
                'first_name': 'Bob',
                'last_name': 'User',
                'role': Role.USER,
                'is_staff': False,
                'is_superuser': False,
            },
        ]
        
        for user_data in demo_users:
            # Check if user exists
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_staff': user_data['is_staff'],
                    'is_superuser': user_data['is_superuser'],
                }
            )
            
            if created:
                user.set_password(user_data['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(f'[OK] Created user: {user.username}'))
            else:
                self.stdout.write(f'  User {user.username} already exists')
            
            # Create or update user profile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': org,
                    'role': user_data['role'],
                    'job_title': f'{user_data["role"].title()} at Demo Corp',
                    'department': 'Procurement' if user_data['role'] != Role.ADMIN else 'Administration',
                    'phone': '+1-555-0100',
                    'timezone': 'America/New_York',
                    'language': 'en',
                    'notifications_enabled': True,
                    'email_notifications': True,
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created profile for {user.username}'))
            
            # Assign role
            assign_role(user, user_data['role'])
            self.stdout.write(self.style.SUCCESS(f'  [OK] Assigned role {user_data["role"]} to {user.username}'))
        
        # Create additional test users if needed
        test_users = [
            ('john.doe', 'John', 'Doe', Role.ANALYST),
            ('jane.smith', 'Jane', 'Smith', Role.USER),
            ('mike.johnson', 'Mike', 'Johnson', Role.USER),
            ('sarah.williams', 'Sarah', 'Williams', Role.ANALYST),
        ]
        
        for username, first_name, last_name, role in test_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@vtx.com',
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': False,
                    'is_superuser': False,
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
                
                # Create profile
                UserProfile.objects.create(
                    user=user,
                    organization=org,
                    role=role,
                    job_title=f'{role.title()} at Demo Corp',
                    department='Procurement',
                    phone='+1-555-0200',
                )
                
                # Assign role
                assign_role(user, role)
                
                self.stdout.write(self.style.SUCCESS(f'[OK] Created test user: {username}'))
        
        self.stdout.write(self.style.SUCCESS('\n[COMPLETE] RBAC setup complete!'))
        self.stdout.write('\nDemo users created:')
        self.stdout.write('  Admin:   admin / admin123')
        self.stdout.write('  Analyst: analyst / analyst123')
        self.stdout.write('  User:    user / user123')
        self.stdout.write('\nTest users: password123 for all')
        self.stdout.write('  - john.doe (Analyst)')
        self.stdout.write('  - jane.smith (User)')
        self.stdout.write('  - mike.johnson (User)')
        self.stdout.write('  - sarah.williams (Analyst)')
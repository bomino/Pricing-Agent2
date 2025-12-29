"""
Prepare database for deployment - run migrations and initial setup
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
import sys


class Command(BaseCommand):
    help = 'Prepare database for deployment - migrations and initial setup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-checks',
            action='store_true',
            help='Skip system checks',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting deployment preparation...\n')
        
        # Step 1: Check database connection
        self.stdout.write('Checking database connection...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write(self.style.SUCCESS('Database connection OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Database connection failed: {e}'))
            sys.exit(1)
        
        # Step 2: Run system checks
        if not options['skip_checks']:
            self.stdout.write('\nRunning system checks...')
            try:
                call_command('check')
                self.stdout.write(self.style.SUCCESS('System checks passed'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'System check warnings: {e}'))
        
        # Step 3: Show pending migrations
        self.stdout.write('\nChecking for pending migrations...')
        call_command('showmigrations', '--plan', verbosity=0)
        
        # Step 4: Run migrations
        self.stdout.write('\nApplying database migrations...')
        try:
            call_command('migrate', '--noinput')
            self.stdout.write(self.style.SUCCESS('Migrations applied successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Migration failed: {e}'))
            sys.exit(1)
        
        # Step 5: Create cache table
        self.stdout.write('\nCreating cache table...')
        try:
            call_command('createcachetable')
            self.stdout.write(self.style.SUCCESS('Cache table created'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Cache table may already exist: {e}'))
        
        # Step 6: Collect static files
        self.stdout.write('\nCollecting static files...')
        try:
            call_command('collectstatic', '--noinput', '--clear')
            self.stdout.write(self.style.SUCCESS('Static files collected'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Static file collection failed: {e}'))
        
        # Step 7: Ensure default organization exists
        self.stdout.write('\nEnsuring default organization...')
        from apps.core.models import Organization
        org, created = Organization.objects.get_or_create(
            code='DEFAULT',
            defaults={'name': 'Default Organization'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created default organization'))
        else:
            self.stdout.write('Default organization already exists')
        
        # Step 8: Set up RBAC
        self.stdout.write('\nSetting up role-based access control...')
        try:
            call_command('setup_rbac')
            self.stdout.write(self.style.SUCCESS('RBAC setup complete'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'RBAC setup warning: {e}'))
        
        # Step 9: Ensure user profiles
        self.stdout.write('\nEnsuring user profiles...')
        try:
            call_command('ensure_user_profiles')
            self.stdout.write(self.style.SUCCESS('User profiles ensured'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'User profile warning: {e}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('Deployment preparation complete!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Create a superuser: python manage.py createsuperuser')
        self.stdout.write('2. Test the application: python manage.py runserver')
        self.stdout.write('3. Run health check: curl http://localhost:8000/health/')
        self.stdout.write('\nFor production, ensure all environment variables are set correctly.')
"""
Database backup command for production deployment
Creates JSON fixtures for essential data
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os
import json
from datetime import datetime
import subprocess


class Command(BaseCommand):
    help = 'Create database backup for deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to store backup files',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'sql'],
            default='json',
            help='Backup format (json fixtures or SQL dump)',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        format_type = options['format']
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(f'Created backup directory: {output_dir}')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_type == 'json':
            self.create_json_backup(output_dir, timestamp)
        else:
            self.create_sql_backup(output_dir, timestamp)
    
    def create_json_backup(self, output_dir, timestamp):
        """Create JSON fixture backups"""
        apps_to_backup = [
            'auth.User',
            'core.Organization',
            'core.UserProfile',
            'accounts.UserProfile',
            'procurement.Supplier',
            'procurement.PurchaseOrder',
            'pricing.Material',
            'pricing.Price',
            'analytics.Report',
        ]
        
        for app_model in apps_to_backup:
            filename = f"{app_model.replace('.', '_')}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            try:
                with open(filepath, 'w') as f:
                    call_command('dumpdata', app_model, 
                               indent=2, 
                               format='json',
                               stdout=f)
                self.stdout.write(self.style.SUCCESS(f'Backed up {app_model} to {filename}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to backup {app_model}: {str(e)}'))
        
        # Create a manifest file
        manifest = {
            'timestamp': timestamp,
            'apps': apps_to_backup,
            'django_version': settings.VERSION if hasattr(settings, 'VERSION') else 'unknown',
            'database': settings.DATABASES['default']['NAME'],
        }
        
        manifest_file = os.path.join(output_dir, f'manifest_{timestamp}.json')
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'\nBackup completed: {output_dir}'))
        self.stdout.write(f'Manifest: {manifest_file}')
    
    def create_sql_backup(self, output_dir, timestamp):
        """Create SQL dump backup"""
        db_settings = settings.DATABASES['default']
        
        if db_settings['ENGINE'] != 'django.db.backends.postgresql':
            self.stdout.write(self.style.ERROR('SQL backup only supports PostgreSQL'))
            return
        
        filename = f"backup_{timestamp}.sql"
        filepath = os.path.join(output_dir, filename)
        
        # Build pg_dump command
        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']
        
        cmd = [
            'pg_dump',
            '-h', db_settings.get('HOST', 'localhost'),
            '-p', str(db_settings.get('PORT', 5432)),
            '-U', db_settings['USER'],
            '-d', db_settings['NAME'],
            '-f', filepath,
            '--verbose',
            '--clean',
            '--no-owner',
            '--no-privileges',
        ]
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS(f'SQL backup created: {filepath}'))
            else:
                self.stdout.write(self.style.ERROR(f'SQL backup failed: {result.stderr}'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('pg_dump not found. Please install PostgreSQL client tools.'))
"""
Health check management command
"""
from django.core.management.base import BaseCommand
from django.test import Client
import json


class Command(BaseCommand):
    help = 'Run health check on the application'

    def handle(self, *args, **options):
        client = Client()
        
        self.stdout.write('Running health check...\n')
        
        try:
            response = client.get('/health/')
            
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS(f"Status: {data.get('status', 'unknown')}"))
                
                if 'services' in data:
                    self.stdout.write('\nService Status:')
                    for service, status in data['services'].items():
                        if status == 'healthy':
                            self.stdout.write(self.style.SUCCESS(f"  {service}: {status}"))
                        else:
                            self.stdout.write(self.style.ERROR(f"  {service}: {status}"))
                
                self.stdout.write(f"\nTimestamp: {data.get('timestamp', 'N/A')}")
                self.stdout.write(self.style.SUCCESS('\nHealth check passed!'))
                
            else:
                self.stdout.write(self.style.ERROR(f'Health check failed with status code: {response.status_code}'))
                if response.content:
                    data = json.loads(response.content)
                    self.stdout.write(self.style.ERROR(f"Error: {data}"))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Health check failed: {str(e)}'))
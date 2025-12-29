"""
Management command to populate staging data from uploaded files for testing
"""
import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.data_ingestion.services.file_parser import FileParser


class Command(BaseCommand):
    help = 'Populate staging data from uploaded files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--upload-id',
            type=str,
            help='Upload ID to populate staging data for'
        )
    
    def handle(self, *args, **options):
        upload_id = options.get('upload_id')
        
        if not upload_id:
            # Get the latest upload without staging data
            upload = DataUpload.objects.filter(
                status__in=['pending', 'completed', 'mapping']
            ).first()
            if not upload:
                self.stdout.write(self.style.ERROR('No uploads found'))
                return
            upload_id = str(upload.id)
        else:
            upload = DataUpload.objects.get(id=upload_id)
        
        self.stdout.write(f'Processing upload: {upload.original_filename}')
        self.stdout.write(f'Upload ID: {upload.id}')
        
        # Check if staging data already exists
        existing = ProcurementDataStaging.objects.filter(upload=upload).count()
        if existing > 0:
            self.stdout.write(self.style.WARNING(f'Found {existing} existing staging records'))
            # Clear them
            ProcurementDataStaging.objects.filter(upload=upload).delete()
            self.stdout.write('[OK] Cleared existing staging records')
        
        # Parse the file
        try:
            parser = FileParser()
            df, detected_schema = parser.parse_file(upload.file, upload.file_format)
            
            self.stdout.write(f'Parsed {len(df)} rows from file')
            
            # Create default column mapping if not exists
            if not upload.column_mapping:
                # Auto-map based on detected schema
                mapping = {}
                for col in df.columns:
                    col_lower = str(col).lower()
                    if 'po' in col_lower or 'order' in col_lower:
                        mapping[col] = 'po_number'
                    elif 'supplier' in col_lower or 'vendor' in col_lower:
                        if 'code' in col_lower:
                            mapping[col] = 'supplier_code'
                        else:
                            mapping[col] = 'supplier_name'
                    elif 'material' in col_lower or 'item' in col_lower or 'product' in col_lower:
                        if 'code' in col_lower or 'sku' in col_lower:
                            mapping[col] = 'material_code'
                        else:
                            mapping[col] = 'material_description'
                    elif 'quantity' in col_lower or 'qty' in col_lower:
                        mapping[col] = 'quantity'
                    elif 'price' in col_lower or 'cost' in col_lower:
                        if 'total' in col_lower:
                            mapping[col] = 'total_price'
                        else:
                            mapping[col] = 'unit_price'
                    elif 'currency' in col_lower or 'curr' in col_lower:
                        mapping[col] = 'currency'
                    elif 'date' in col_lower:
                        if 'delivery' in col_lower:
                            mapping[col] = 'delivery_date'
                        else:
                            mapping[col] = 'purchase_date'
                
                upload.column_mapping = mapping
                upload.save()
                self.stdout.write('[OK] Created column mapping')
            
            # Create staging records
            staging_records = []
            for idx, row in df.iterrows():
                # Map columns to staging fields
                staging_data = {
                    'upload': upload,
                    'row_number': idx + 1,
                    'validation_status': 'valid',
                    'raw_data': row.to_dict()
                }
                
                # Map fields based on column mapping
                for source_col, target_field in upload.column_mapping.items():
                    if source_col in row:
                        value = row[source_col]
                        if pd.notna(value):
                            if target_field == 'quantity':
                                try:
                                    staging_data[target_field] = float(value)
                                except:
                                    staging_data[target_field] = 0
                            elif target_field in ['unit_price', 'total_price']:
                                try:
                                    # Clean price values
                                    if isinstance(value, str):
                                        value = value.replace('$', '').replace(',', '')
                                    staging_data[target_field] = float(value)
                                except:
                                    staging_data[target_field] = 0
                            elif target_field in ['purchase_date', 'delivery_date']:
                                try:
                                    staging_data[target_field] = pd.to_datetime(value).date()
                                except:
                                    staging_data[target_field] = timezone.now().date()
                            else:
                                staging_data[target_field] = str(value)
                
                # Add default values if missing
                if 'currency' not in staging_data or not staging_data.get('currency'):
                    staging_data['currency'] = 'USD'
                
                staging_records.append(ProcurementDataStaging(**staging_data))
            
            # Bulk create staging records
            ProcurementDataStaging.objects.bulk_create(staging_records)
            
            # Update upload
            upload.status = 'pending'  # Reset to pending for processing
            upload.total_rows = len(staging_records)
            upload.detected_schema = detected_schema
            upload.save()
            
            self.stdout.write(self.style.SUCCESS(f'[OK] Created {len(staging_records)} staging records'))
            self.stdout.write(f'\nUpload is now ready for processing!')
            self.stdout.write(f'Run: python manage.py process_pending_uploads --upload-id {upload.id}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            import traceback
            traceback.print_exc()
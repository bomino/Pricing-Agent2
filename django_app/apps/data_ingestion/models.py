"""
Data Ingestion Models for Procurement Data Upload and Processing
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.utils import timezone
import uuid
from apps.procurement.models import Supplier
from apps.pricing.models import Material

User = get_user_model()


class DataUpload(models.Model):
    """
    Track file uploads and processing status for procurement data
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('mapping', 'Mapping Columns'),
        ('ready_to_process', 'Ready to Process'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partially Processed'),
    ]
    
    FILE_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel (XLSX)'),
        ('xls', 'Excel (XLS)'),
        ('parquet', 'Parquet'),
    ]
    
    DATA_TYPE_CHOICES = [
        ('purchase_orders', 'Purchase Orders'),
        ('invoices', 'Invoices'),
        ('contracts', 'Contracts'),
        ('suppliers', 'Supplier Master'),
        ('materials', 'Material Master'),
        ('spend_data', 'Spend Analysis'),
        ('price_history', 'Historical Prices'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # File information
    file = models.FileField(
        upload_to='uploads/procurement/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls', 'parquet']),
        ]
    )
    original_filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES)
    file_size = models.BigIntegerField(validators=[MaxValueValidator(52428800)])  # 50MB limit
    data_type = models.CharField(max_length=30, choices=DATA_TYPE_CHOICES)
    
    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    warnings = models.JSONField(default=list)
    
    # Statistics
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    duplicate_rows = models.IntegerField(default=0)
    data_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Overall data quality score (0-100)")
    
    # Validation and mapping
    detected_schema = models.JSONField(default=dict, help_text="Auto-detected column schema")
    column_mapping = models.JSONField(default=dict, help_text="User-confirmed column mappings")
    validation_rules = models.JSONField(default=dict, help_text="Applied validation rules")
    validation_report = models.JSONField(default=dict, help_text="Detailed validation results")
    
    # Processing metadata
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration_seconds = models.IntegerField(null=True, blank=True)
    processing_progress = models.IntegerField(default=0, help_text="Processing progress percentage")
    celery_task_id = models.CharField(max_length=255, blank=True, help_text="Celery task ID for async processing")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['status', 'organization']),
            models.Index(fields=['data_type', 'organization']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} - {self.get_status_display()}"
    
    def get_processing_percentage(self):
        if self.total_rows == 0:
            return 0
        return round((self.processed_rows / self.total_rows) * 100, 2)


class DataMappingTemplate(models.Model):
    """
    Reusable column mapping templates for different data sources
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=30, choices=DataUpload.DATA_TYPE_CHOICES)
    source_system = models.CharField(max_length=100, blank=True, help_text="e.g., SAP, Oracle, Coupa")
    
    # Column mappings: source_column -> target_field
    column_mappings = models.JSONField(default=dict)
    
    # Data transformations
    transformations = models.JSONField(
        default=dict,
        help_text="Field-level transformations (e.g., date formats, currency conversion)"
    )
    
    # Validation rules specific to this template
    validation_rules = models.JSONField(default=dict)
    
    # Usage tracking
    times_used = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['organization', 'name']
        ordering = ['-times_used', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.data_type})"


class ProcurementDataStaging(models.Model):
    """
    Staging table for uploaded procurement data before final processing
    """
    VALIDATION_STATUS_CHOICES = [
        ('pending', 'Pending Validation'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('corrected', 'Corrected'),
        ('ignored', 'Ignored'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='staging_records')
    row_number = models.IntegerField()
    
    # Raw data storage
    raw_data = models.JSONField(help_text="Original row data as uploaded")
    
    # Validation
    validation_status = models.CharField(max_length=20, choices=VALIDATION_STATUS_CHOICES, default='pending')
    validation_errors = models.JSONField(default=list)
    validation_warnings = models.JSONField(default=list)
    
    # Mapped and cleaned fields (nullable until mapping is confirmed)
    # Purchase Order / Invoice fields
    po_number = models.CharField(max_length=50, blank=True, db_index=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    line_item_number = models.CharField(max_length=20, blank=True)
    
    # Supplier information
    supplier_name = models.CharField(max_length=255, blank=True)
    supplier_code = models.CharField(max_length=50, blank=True, db_index=True)
    supplier_site = models.CharField(max_length=100, blank=True)
    
    # Material/Service information
    material_code = models.CharField(max_length=100, blank=True, db_index=True)
    material_description = models.TextField(blank=True)
    material_category = models.CharField(max_length=100, blank=True)
    material_group = models.CharField(max_length=100, blank=True)
    
    # Quantity and UOM
    quantity = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True)
    unit_of_measure = models.CharField(max_length=20, blank=True)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    total_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    
    # Dates
    purchase_date = models.DateField(null=True, blank=True, db_index=True)
    delivery_date = models.DateField(null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    
    # Additional fields
    buyer_name = models.CharField(max_length=100, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)
    gl_account = models.CharField(max_length=50, blank=True)
    project_code = models.CharField(max_length=50, blank=True)
    
    # Processing flags
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['upload', 'row_number']
        indexes = [
            models.Index(fields=['upload', 'validation_status']),
            models.Index(fields=['supplier_code', 'material_code']),
            models.Index(fields=['purchase_date']),
        ]
    
    def __str__(self):
        return f"Row {self.row_number} from {self.upload.original_filename}"
    
    @property
    def organization(self):
        return self.upload.organization


class DataIngestionLog(models.Model):
    """
    Audit log for all data ingestion activities
    """
    ACTION_CHOICES = [
        ('upload_started', 'Upload Started'),
        ('validation_completed', 'Validation Completed'),
        ('mapping_saved', 'Mapping Saved'),
        ('processing_started', 'Processing Started'),
        ('processing_completed', 'Processing Completed'),
        ('error_occurred', 'Error Occurred'),
        ('manual_correction', 'Manual Correction'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Log details
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    # Metrics
    rows_affected = models.IntegerField(default=0)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['upload', '-timestamp']
        indexes = [
            models.Index(fields=['upload', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.upload.original_filename}"


class MatchingConflict(models.Model):
    """Records potential duplicate matches that need user resolution"""

    CONFLICT_TYPES = [
        ('supplier', 'Supplier Match'),
        ('material', 'Material Match'),
    ]

    RESOLUTION_STATUS = [
        ('pending', 'Pending Review'),
        ('resolved_match', 'Confirmed as Match'),
        ('resolved_new', 'Confirmed as New'),
        ('auto_resolved', 'Auto-Resolved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(
        'DataUpload',
        on_delete=models.CASCADE,
        related_name='conflicts'
    )
    staging_record = models.ForeignKey(
        'ProcurementDataStaging',
        on_delete=models.CASCADE,
        related_name='conflicts'
    )

    conflict_type = models.CharField(
        max_length=20,
        choices=CONFLICT_TYPES
    )
    status = models.CharField(
        max_length=20,
        choices=RESOLUTION_STATUS,
        default='pending'
    )

    # The incoming value that triggered the conflict
    incoming_value = models.CharField(max_length=255)
    incoming_code = models.CharField(max_length=100, blank=True, null=True)

    # Potential matches found (stored as JSON)
    potential_matches = models.JSONField(default=list)
    # Example: [
    #   {"id": "uuid", "name": "Supplier A", "code": "SUP001", "similarity": 0.92},
    #   {"id": "uuid", "name": "Supplier B", "code": "SUP002", "similarity": 0.85}
    # ]

    # Resolution details
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_conflicts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # If matched to existing record
    matched_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    matched_material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Confidence scores
    highest_similarity = models.FloatField(default=0.0)
    auto_resolve_threshold = models.FloatField(default=0.95)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-highest_similarity', 'created_at']
        indexes = [
            models.Index(fields=['upload', 'status']),
            models.Index(fields=['conflict_type', 'status']),
        ]

    def __str__(self):
        return f"{self.conflict_type} conflict: {self.incoming_value} ({self.status})"

    def resolve_as_match(self, matched_id, user=None):
        """Resolve conflict as a match to existing record"""
        from datetime import datetime

        self.status = 'resolved_match'
        self.resolved_by = user
        self.resolved_at = timezone.now()

        if self.conflict_type == 'supplier':
            self.matched_supplier_id = matched_id
        elif self.conflict_type == 'material':
            self.matched_material_id = matched_id

        self.save()

    def resolve_as_new(self, user=None):
        """Resolve conflict as a new record (not a match)"""
        self.status = 'resolved_new'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()

    def auto_resolve(self):
        """Auto-resolve if similarity is above threshold"""
        if self.potential_matches and self.highest_similarity >= self.auto_resolve_threshold:
            best_match = max(self.potential_matches, key=lambda x: x.get('similarity', 0))
            self.resolve_as_match(best_match['id'])
            self.status = 'auto_resolved'
            self.save()
            return True
        return False
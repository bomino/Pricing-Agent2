"""
Core models for the pricing agent application
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone


class TimestampedModel(models.Model):
    """Abstract base class with created/updated timestamps"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Organization(TimestampedModel):
    """Organization model for multi-tenancy"""
    
    ORGANIZATION_TYPES = [
        ('buyer', 'Buyer'),
        ('supplier', 'Supplier'),
        ('both', 'Both'),
    ]
    
    name = models.CharField(max_length=255)
    code = models.CharField(
        max_length=50,
        unique=True,
        validators=[RegexValidator(
            regex=r'^[A-Z0-9_]+$',
            message='Code must contain only uppercase letters, numbers, and underscores'
        )]
    )
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'organizations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @classmethod
    def generate_code(cls):
        """Generate unique organization code"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.objects.filter(code=code).exists():
                return code


class AuditLog(models.Model):
    """Audit log for tracking user actions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.created_at}"


class Category(TimestampedModel):
    """Category model for materials/products"""
    
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'
        ordering = ['level', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['parent', 'level']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate level based on parent"""
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Get full category path"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name


class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)  # Can be accessed by frontend
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_configuration'
        ordering = ['key']
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get configuration value by key"""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value, description='', is_public=False, user=None):
        """Set configuration value"""
        config, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'description': description,
                'is_public': is_public,
                'updated_by': user,
            }
        )
        if not created:
            config.value = value
            config.description = description
            config.is_public = is_public
            config.updated_by = user
            config.save()
        return config


class Notification(TimestampedModel):
    """System notifications"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('ml_prediction', 'ML Prediction'),
        ('price_alert', 'Price Alert'),
        ('workflow', 'Workflow'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    recipient = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
            models.Index(fields=['organization', 'type']),
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.recipient} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
    
    @classmethod
    def create_notification(cls, recipient, title, message, type='info', priority='medium', data=None, organization=None):
        """Create a new notification"""
        return cls.objects.create(
            recipient=recipient,
            organization=organization,
            type=type,
            priority=priority,
            title=title,
            message=message,
            data=data or {}
        )
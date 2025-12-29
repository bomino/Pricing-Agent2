"""
Security-related models for enterprise security framework
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import TimestampedModel, Organization

User = get_user_model()


class UserSecuritySettings(TimestampedModel):
    """Security settings for users"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_settings')
    
    # Multi-Factor Authentication
    mfa_enabled = models.BooleanField(default=False)
    totp_secret = models.TextField(blank=True)  # Encrypted TOTP secret
    backup_codes = models.JSONField(default=list, blank=True)  # Encrypted backup codes
    mfa_recovery_codes_generated_at = models.DateTimeField(null=True, blank=True)
    
    # Password settings
    password_expires_at = models.DateTimeField(null=True, blank=True)
    force_password_change = models.BooleanField(default=False)
    password_change_required_reason = models.TextField(blank=True)
    
    # Account security
    security_questions = models.JSONField(default=dict, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login_at = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    lockout_count = models.PositiveIntegerField(default=0)
    
    # Session preferences
    require_mfa_for_sensitive_actions = models.BooleanField(default=True)
    session_timeout_minutes = models.PositiveIntegerField(null=True, blank=True)  # Override default
    allow_concurrent_sessions = models.BooleanField(default=True)
    
    # Notifications
    notify_on_login = models.BooleanField(default=True)
    notify_on_password_change = models.BooleanField(default=True)
    notify_on_mfa_change = models.BooleanField(default=True)
    notify_on_suspicious_activity = models.BooleanField(default=True)
    
    # Data privacy
    data_retention_days = models.PositiveIntegerField(null=True, blank=True)
    allow_data_export = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_security_settings'
    
    def __str__(self):
        return f"{self.user.email} Security Settings"
    
    @property
    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False
    
    def lock_account(self, minutes: int = 30, reason: str = ""):
        """Lock user account"""
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.lockout_count += 1
        if reason:
            self.password_change_required_reason = reason
        self.save()
    
    def unlock_account(self):
        """Unlock user account"""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.password_change_required_reason = ""
        self.save()


class PasswordHistory(TimestampedModel):
    """Track password history for policy enforcement"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    password_hash = models.CharField(max_length=128)
    algorithm = models.CharField(max_length=50, default='pbkdf2_sha256')
    salt = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'password_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.created_at}"


class SecurityEvent(TimestampedModel):
    """Track security events"""
    
    EVENT_TYPES = [
        # Authentication events
        ('login_success', 'Successful Login'),
        ('login_failure', 'Failed Login'),
        ('logout', 'Logout'),
        ('session_expired', 'Session Expired'),
        ('mfa_setup', 'MFA Setup'),
        ('mfa_verification_success', 'MFA Verification Success'),
        ('mfa_verification_failure', 'MFA Verification Failure'),
        ('mfa_disabled', 'MFA Disabled'),
        
        # Account events
        ('password_changed', 'Password Changed'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('password_reset_requested', 'Password Reset Requested'),
        ('password_reset_completed', 'Password Reset Completed'),
        
        # Security events
        ('suspicious_activity', 'Suspicious Activity'),
        ('api_key_created', 'API Key Created'),
        ('api_key_revoked', 'API Key Revoked'),
        ('permission_changed', 'Permission Changed'),
        ('data_export', 'Data Export'),
        ('data_deletion', 'Data Deletion'),
        
        # System events
        ('security_scan', 'Security Scan'),
        ('vulnerability_detected', 'Vulnerability Detected'),
        ('policy_violation', 'Policy Violation'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='low')
    
    # Event details
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    
    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    risk_score = models.PositiveIntegerField(default=0)  # 0-100 risk score
    
    # Investigation
    investigated = models.BooleanField(default=False)
    investigated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='investigated_security_events'
    )
    investigation_notes = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'security_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type', 'created_at']),
            models.Index(fields=['organization', 'severity', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['event_type', 'severity']),
            models.Index(fields=['resolved', 'severity']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.user or 'System'} - {self.created_at}"
    
    @classmethod
    def log_event(cls, event_type: str, user=None, organization=None, description: str = "", 
                  severity: str = 'low', ip_address: str = None, user_agent: str = "",
                  session_id: str = "", metadata: dict = None, risk_score: int = 0):
        """Log security event"""
        return cls.objects.create(
            user=user,
            organization=organization,
            event_type=event_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=metadata or {},
            risk_score=risk_score,
        )


class APIKeyPermission(TimestampedModel):
    """Granular permissions for API keys"""
    
    api_key = models.ForeignKey('accounts.APIKey', on_delete=models.CASCADE, related_name='detailed_permissions')
    resource = models.CharField(max_length=100)  # e.g., 'materials', 'suppliers', 'quotes'
    actions = models.JSONField(default=list)  # e.g., ['read', 'create', 'update', 'delete']
    conditions = models.JSONField(default=dict, blank=True)  # Additional conditions
    
    class Meta:
        db_table = 'api_key_permissions'
        unique_together = ['api_key', 'resource']
    
    def __str__(self):
        return f"{self.api_key.name} - {self.resource}"
    
    def has_action(self, action: str) -> bool:
        """Check if API key has specific action permission"""
        return action in self.actions or '*' in self.actions


class DataClassification(TimestampedModel):
    """Data classification for privacy compliance"""
    
    CLASSIFICATION_LEVELS = [
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('confidential', 'Confidential'),
        ('restricted', 'Restricted'),
        ('top_secret', 'Top Secret'),
    ]
    
    DATA_CATEGORIES = [
        ('pii', 'Personally Identifiable Information'),
        ('financial', 'Financial Information'),
        ('pricing', 'Pricing Information'),
        ('commercial', 'Commercial Information'),
        ('technical', 'Technical Information'),
        ('operational', 'Operational Information'),
    ]
    
    table_name = models.CharField(max_length=100)
    column_name = models.CharField(max_length=100, blank=True)
    classification_level = models.CharField(max_length=20, choices=CLASSIFICATION_LEVELS)
    data_category = models.CharField(max_length=20, choices=DATA_CATEGORIES)
    
    # Compliance requirements
    requires_encryption = models.BooleanField(default=False)
    requires_masking = models.BooleanField(default=False)
    retention_days = models.PositiveIntegerField(null=True, blank=True)
    geographic_restrictions = models.JSONField(default=list, blank=True)
    
    # Access controls
    required_role_level = models.CharField(max_length=20, blank=True)
    requires_mfa = models.BooleanField(default=False)
    audit_access = models.BooleanField(default=True)
    
    # Compliance flags
    gdpr_applicable = models.BooleanField(default=False)
    ccpa_applicable = models.BooleanField(default=False)
    sox_applicable = models.BooleanField(default=False)
    pci_applicable = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'data_classification'
        unique_together = ['table_name', 'column_name']
        indexes = [
            models.Index(fields=['classification_level']),
            models.Index(fields=['data_category']),
            models.Index(fields=['requires_encryption']),
        ]
    
    def __str__(self):
        column_ref = f".{self.column_name}" if self.column_name else ""
        return f"{self.table_name}{column_ref} - {self.classification_level}"


class ComplianceAudit(TimestampedModel):
    """Compliance audit records"""
    
    AUDIT_TYPES = [
        ('gdpr', 'GDPR Compliance'),
        ('ccpa', 'CCPA Compliance'),
        ('sox', 'SOX Compliance'),
        ('soc2', 'SOC 2 Compliance'),
        ('iso27001', 'ISO 27001 Compliance'),
        ('pci_dss', 'PCI DSS Compliance'),
        ('internal', 'Internal Audit'),
        ('external', 'External Audit'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    audit_type = models.CharField(max_length=20, choices=AUDIT_TYPES)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='compliance_audits')
    auditor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Audit details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scope = models.JSONField(default=dict, blank=True)  # What's being audited
    
    # Scheduling
    scheduled_date = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Status and results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    findings = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Compliance scores (0-100)
    overall_score = models.PositiveIntegerField(null=True, blank=True)
    technical_score = models.PositiveIntegerField(null=True, blank=True)
    policy_score = models.PositiveIntegerField(null=True, blank=True)
    training_score = models.PositiveIntegerField(null=True, blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    next_audit_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'compliance_audits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'audit_type']),
            models.Index(fields=['status', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"{self.audit_type} - {self.organization.name} - {self.scheduled_date.date()}"


class DataRetentionPolicy(TimestampedModel):
    """Data retention policies for compliance"""
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='retention_policies')
    data_type = models.CharField(max_length=100)  # e.g., 'user_data', 'transaction_logs', 'audit_logs'
    
    # Retention settings
    retention_days = models.PositiveIntegerField()
    archive_after_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Legal holds
    legal_hold_applies = models.BooleanField(default=False)
    legal_hold_reason = models.TextField(blank=True)
    legal_hold_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Compliance requirements
    regulatory_basis = models.CharField(max_length=100, blank=True)  # e.g., 'GDPR Article 5', 'SOX 404'
    business_justification = models.TextField(blank=True)
    
    # Deletion process
    auto_delete_enabled = models.BooleanField(default=False)
    delete_method = models.CharField(max_length=50, default='soft_delete')  # soft_delete, hard_delete, archive
    notification_required = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'data_retention_policies'
        unique_together = ['organization', 'data_type']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.data_type} - {self.retention_days} days"


class EncryptionKey(TimestampedModel):
    """Encryption key management"""
    
    KEY_TYPES = [
        ('aes256', 'AES-256'),
        ('rsa2048', 'RSA-2048'),
        ('rsa4096', 'RSA-4096'),
        ('ed25519', 'Ed25519'),
    ]
    
    KEY_PURPOSES = [
        ('data_encryption', 'Data Encryption'),
        ('jwt_signing', 'JWT Signing'),
        ('api_authentication', 'API Authentication'),
        ('backup_encryption', 'Backup Encryption'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='encryption_keys')
    key_id = models.CharField(max_length=255, unique=True)
    key_type = models.CharField(max_length=20, choices=KEY_TYPES)
    purpose = models.CharField(max_length=50, choices=KEY_PURPOSES)
    
    # Key material (encrypted with master key)
    encrypted_key_material = models.TextField()
    public_key = models.TextField(blank=True)  # For asymmetric keys
    
    # Key lifecycle
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_rotated_at = models.DateTimeField(auto_now_add=True)
    rotation_interval_days = models.PositiveIntegerField(default=90)
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Access control
    authorized_users = models.ManyToManyField(User, blank=True)
    authorized_roles = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'encryption_keys'
        indexes = [
            models.Index(fields=['organization', 'purpose', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.key_id} - {self.purpose}"
    
    def is_expired(self) -> bool:
        """Check if key is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def needs_rotation(self) -> bool:
        """Check if key needs rotation"""
        if self.rotation_interval_days and self.last_rotated_at:
            rotation_due = self.last_rotated_at + timezone.timedelta(days=self.rotation_interval_days)
            return timezone.now() > rotation_due
        return False
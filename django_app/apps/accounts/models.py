"""
User and authentication models
"""
import uuid
# from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth.models import User  # Use Django's built-in User
from apps.core.models import TimestampedModel, Organization


# TEMPORARILY DISABLED: Custom User model to avoid conflicts during initial setup
# We'll re-enable this once the base project is working
"""
class User(AbstractUser):
    # Extended user model
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    is_email_verified = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Override username to make it optional
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text='Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': "A user with that username already exists.",
        },
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        ordering = ['email']
    
    def save(self, *args, **kwargs):
        # Override save to auto-generate username if not provided
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        # Return the first_name plus the last_name, with a space in between
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()
    
    def get_short_name(self):
        # Return the short name for the user
        return self.first_name
    
    @property
    def is_locked(self):
        # Check if account is locked
        if self.account_locked_until:
            from django.utils import timezone
            return timezone.now() < self.account_locked_until
        return False
    
    def lock_account(self, minutes=30):
        # Lock account for specified minutes
        from django.utils import timezone
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save()
    
    def unlock_account(self):
        # Unlock account
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save()
"""


class UserProfile(TimestampedModel):
    """Extended user profile information"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    job_title = models.CharField(max_length=255, blank=True)
    department = models.CharField(max_length=255, blank=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_profiles')
    
    # Contact information
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    mobile = models.CharField(max_length=20, blank=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    notifications_enabled = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    # Profile details
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    linkedin_url = models.URLField(blank=True)
    
    # System fields
    is_active = models.BooleanField(default=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Role and permissions
    role = models.CharField(
        max_length=50,
        choices=[
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            ('analyst', 'Analyst'),
            ('buyer', 'Buyer'),
            ('viewer', 'Viewer'),
        ],
        default='viewer'
    )
    
    # Security
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=255, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'user_profiles'
        ordering = ['user__email']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.organization.name}"
    
    @property
    def full_name(self):
        """Get user's full name"""
        return self.user.get_full_name()
    
    @property
    def email(self):
        """Get user's email"""
        return self.user.email
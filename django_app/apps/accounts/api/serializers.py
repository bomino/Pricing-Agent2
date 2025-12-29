"""
Accounts API serializers
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.accounts.models import UserProfile
from apps.core.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model"""
    
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'code', 'type', 'description', 'website', 
            'phone', 'email', 'address', 'settings', 'is_active',
            'created_at', 'updated_at', 'user_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_count']
    
    def get_user_count(self, obj):
        """Get the number of users in this organization"""
        return obj.user_profiles.filter(is_active=True).count()
    
    def validate_code(self, value):
        """Validate organization code format"""
        if not value.isupper():
            raise serializers.ValidationError("Code must be uppercase")
        return value


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    full_name = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login', 'full_name', 'profile'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'full_name', 'profile']
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.get_full_name()
    
    def get_profile(self, obj):
        """Get user profile data"""
        try:
            profile = obj.profile
            return {
                'job_title': profile.job_title,
                'department': profile.department,
                'organization': profile.organization.name,
                'role': profile.role,
                'avatar': profile.avatar.url if profile.avatar else None,
                'timezone': profile.timezone,
                'language': profile.language,
            }
        except UserProfile.DoesNotExist:
            return None


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users"""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    organization_code = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'password', 'password_confirm', 'organization_code'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def validate(self, attrs):
        """Validate password confirmation and organization"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")
        
        # Validate organization exists
        organization_code = attrs.get('organization_code')
        try:
            organization = Organization.objects.get(code=organization_code, is_active=True)
            attrs['organization'] = organization
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Invalid organization code")
        
        return attrs
    
    def create(self, validated_data):
        """Create user with profile"""
        # Remove fields that aren't User model fields
        organization = validated_data.pop('organization')
        validated_data.pop('password_confirm')
        validated_data.pop('organization_code')
        
        # Create user
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile
        UserProfile.objects.create(
            user=user,
            organization=organization,
        )
        
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    
    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    manager = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'job_title', 'department', 'manager', 'organization',
            'phone', 'mobile', 'timezone', 'language', 'notifications_enabled',
            'email_notifications', 'sms_notifications', 'bio', 'avatar',
            'linkedin_url', 'is_active', 'date_of_birth', 'role',
            'two_factor_enabled', 'last_login_ip', 'failed_login_attempts',
            'created_at', 'updated_at', 'full_name'
        ]
        read_only_fields = [
            'id', 'user', 'organization', 'created_at', 'updated_at', 
            'full_name', 'last_login_ip', 'failed_login_attempts'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.full_name


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profiles"""
    
    class Meta:
        model = UserProfile
        fields = [
            'job_title', 'department', 'phone', 'mobile', 'timezone', 
            'language', 'notifications_enabled', 'email_notifications',
            'sms_notifications', 'bio', 'avatar', 'linkedin_url', 
            'date_of_birth'
        ]
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if value and not value.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            raise serializers.ValidationError("Invalid phone number format")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password"""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate password change"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords do not match")
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    
    def save(self):
        """Change user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserListSerializer(serializers.ModelSerializer):
    """Minimal serializer for user lists"""
    
    profile_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'profile_summary'
        ]
    
    def get_profile_summary(self, obj):
        """Get basic profile information"""
        try:
            profile = obj.profile
            return {
                'job_title': profile.job_title,
                'organization': profile.organization.name,
                'role': profile.role,
                'is_active': profile.is_active,
            }
        except UserProfile.DoesNotExist:
            return None


class OrganizationDetailSerializer(OrganizationSerializer):
    """Detailed organization serializer with related data"""
    
    user_profiles = UserListSerializer(many=True, read_only=True)
    recent_activity = serializers.SerializerMethodField()
    
    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + ['user_profiles', 'recent_activity']
    
    def get_recent_activity(self, obj):
        """Get recent organization activity"""
        # This could include recent logins, created users, etc.
        from django.utils import timezone
        from datetime import timedelta
        
        recent_date = timezone.now() - timedelta(days=30)
        recent_users = obj.user_profiles.filter(created_at__gte=recent_date).count()
        
        return {
            'new_users_30_days': recent_users,
            'total_active_users': obj.user_profiles.filter(is_active=True).count(),
        }


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics"""
    
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    inactive_users = serializers.IntegerField()
    new_users_30_days = serializers.IntegerField()
    users_by_role = serializers.DictField()
    users_by_organization = serializers.DictField()


class LoginHistorySerializer(serializers.Serializer):
    """Serializer for user login history"""
    
    user_id = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.CharField()
    last_login = serializers.DateTimeField()
    login_count = serializers.IntegerField()
    failed_attempts = serializers.IntegerField()
    last_ip = serializers.IPAddressField()
    
    
class UserActivitySerializer(serializers.Serializer):
    """Serializer for user activity tracking"""
    
    user = UserListSerializer()
    action = serializers.CharField()
    timestamp = serializers.DateTimeField()
    ip_address = serializers.IPAddressField()
    user_agent = serializers.CharField()
    details = serializers.JSONField()


class BulkUserOperationSerializer(serializers.Serializer):
    """Serializer for bulk user operations"""
    
    OPERATION_CHOICES = [
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('delete', 'Delete'),
        ('change_role', 'Change Role'),
        ('change_organization', 'Change Organization'),
    ]
    
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100
    )
    operation = serializers.ChoiceField(choices=OPERATION_CHOICES)
    parameters = serializers.JSONField(required=False)
    
    def validate(self, attrs):
        """Validate bulk operation"""
        operation = attrs['operation']
        parameters = attrs.get('parameters', {})
        
        if operation == 'change_role' and 'role' not in parameters:
            raise serializers.ValidationError("Role is required for change_role operation")
        
        if operation == 'change_organization' and 'organization_code' not in parameters:
            raise serializers.ValidationError("Organization code is required for change_organization operation")
        
        return attrs


class OrganizationStatsSerializer(serializers.Serializer):
    """Serializer for organization statistics"""
    
    total_organizations = serializers.IntegerField()
    active_organizations = serializers.IntegerField()
    inactive_organizations = serializers.IntegerField()
    organizations_by_type = serializers.DictField()
    average_users_per_org = serializers.FloatField()


class UserPermissionsSerializer(serializers.Serializer):
    """Serializer for user permissions"""
    
    user_permissions = serializers.ListField(child=serializers.CharField())
    group_permissions = serializers.ListField(child=serializers.CharField())
    all_permissions = serializers.ListField(child=serializers.CharField())
    has_admin_access = serializers.BooleanField()
    role = serializers.CharField()
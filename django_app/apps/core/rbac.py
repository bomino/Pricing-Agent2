"""
Role-Based Access Control (RBAC) System
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


class Role(models.TextChoices):
    """System Roles"""
    ADMIN = 'admin', 'Administrator'
    ANALYST = 'analyst', 'Analyst'
    USER = 'user', 'User'


# Permission mappings for each role
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        # Full system access
        'view_all',
        'edit_all',
        'delete_all',
        'manage_users',
        'manage_organizations',
        'manage_system_settings',
        'view_analytics',
        'export_data',
        'import_data',
        'manage_integrations',
        'approve_rfqs',
        'manage_suppliers',
        'manage_materials',
        'manage_pricing',
        'generate_predictions',
        'configure_alerts',
        'view_audit_logs',
        'manage_roles',
    ],
    Role.ANALYST: [
        # Read and analyze data, create reports
        'view_all',
        'view_analytics',
        'export_data',
        'generate_predictions',
        'create_reports',
        'view_suppliers',
        'view_materials',
        'view_pricing',
        'create_rfqs',
        'view_rfqs',
        'compare_quotes',
        'configure_alerts',
        'edit_own_content',
    ],
    Role.USER: [
        # Basic read access and own content management
        'view_dashboard',
        'view_materials',
        'view_suppliers',
        'view_pricing',
        'create_rfqs',
        'view_own_rfqs',
        'edit_own_content',
        'view_own_analytics',
        'export_own_data',
    ],
}


def create_roles_and_permissions():
    """Create roles (groups) and assign permissions"""
    from django.contrib.auth.models import User
    
    # Create groups for each role
    for role_name, role_display in Role.choices:
        group, created = Group.objects.get_or_create(name=role_name)
        if created:
            print(f"Created role: {role_display}")
    
    # Create custom permissions
    content_type = ContentType.objects.get_for_model(User)
    
    custom_permissions = [
        ('view_all', 'Can view all data'),
        ('edit_all', 'Can edit all data'),
        ('delete_all', 'Can delete all data'),
        ('manage_users', 'Can manage users'),
        ('manage_organizations', 'Can manage organizations'),
        ('manage_system_settings', 'Can manage system settings'),
        ('view_analytics', 'Can view analytics'),
        ('export_data', 'Can export data'),
        ('import_data', 'Can import data'),
        ('manage_integrations', 'Can manage integrations'),
        ('approve_rfqs', 'Can approve RFQs'),
        ('manage_suppliers', 'Can manage suppliers'),
        ('manage_materials', 'Can manage materials'),
        ('manage_pricing', 'Can manage pricing'),
        ('generate_predictions', 'Can generate predictions'),
        ('configure_alerts', 'Can configure alerts'),
        ('view_audit_logs', 'Can view audit logs'),
        ('manage_roles', 'Can manage roles'),
        ('create_reports', 'Can create reports'),
        ('view_suppliers', 'Can view suppliers'),
        ('view_materials', 'Can view materials'),
        ('view_pricing', 'Can view pricing'),
        ('create_rfqs', 'Can create RFQs'),
        ('view_rfqs', 'Can view RFQs'),
        ('view_own_rfqs', 'Can view own RFQs'),
        ('compare_quotes', 'Can compare quotes'),
        ('edit_own_content', 'Can edit own content'),
        ('view_dashboard', 'Can view dashboard'),
        ('view_own_analytics', 'Can view own analytics'),
        ('export_own_data', 'Can export own data'),
    ]
    
    for codename, name in custom_permissions:
        permission, created = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={'name': name}
        )
        if created:
            print(f"Created permission: {name}")
    
    # Assign permissions to roles
    for role_name, permissions_list in ROLE_PERMISSIONS.items():
        group = Group.objects.get(name=role_name)
        for perm_codename in permissions_list:
            try:
                permission = Permission.objects.get(
                    codename=perm_codename,
                    content_type=content_type
                )
                group.permissions.add(permission)
            except Permission.DoesNotExist:
                print(f"Permission {perm_codename} not found")
        print(f"Assigned permissions to role: {role_name}")


def assign_role(user, role):
    """Assign a role to a user"""
    # Remove all existing groups
    user.groups.clear()
    
    # Add new role
    group = Group.objects.get(name=role)
    user.groups.add(group)
    
    # Update user profile if exists
    if hasattr(user, 'userprofile'):
        user.profile.role = role
        user.profile.save()


def get_user_role(user):
    """Get the primary role of a user"""
    if user.is_superuser:
        return Role.ADMIN
    
    if hasattr(user, 'userprofile') and user.profile.role:
        return user.profile.role
    
    # Check groups
    if user.groups.filter(name=Role.ADMIN).exists():
        return Role.ADMIN
    elif user.groups.filter(name=Role.ANALYST).exists():
        return Role.ANALYST
    elif user.groups.filter(name=Role.USER).exists():
        return Role.USER
    
    return Role.USER  # Default role


def has_role(user, role):
    """Check if user has a specific role"""
    if user.is_superuser and role == Role.ADMIN:
        return True
    return user.groups.filter(name=role).exists()


def has_any_role(user, roles):
    """Check if user has any of the specified roles"""
    if user.is_superuser and Role.ADMIN in roles:
        return True
    return user.groups.filter(name__in=roles).exists()


def has_permission(user, permission):
    """Check if user has a specific permission"""
    if user.is_superuser:
        return True
    
    # Check both user permissions and group permissions
    return user.has_perm(f'auth.{permission}')


# Decorators for view protection
def role_required(*roles):
    """Decorator to require specific roles for a view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Please log in to access this page.')
                return redirect('core:login')
            
            if not has_any_role(request.user, roles):
                messages.error(request, 'You do not have permission to access this page.')
                raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def permission_required(*permissions):
    """Decorator to require specific permissions for a view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Please log in to access this page.')
                return redirect('core:login')
            
            for permission in permissions:
                if not has_permission(request.user, permission):
                    messages.error(request, f'You do not have the required permission: {permission}')
                    raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


# Mixin for class-based views
class RoleRequiredMixin:
    """Mixin to require specific roles for class-based views"""
    required_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            return redirect('core:login')
        
        if self.required_roles and not has_any_role(request.user, self.required_roles):
            messages.error(request, 'You do not have permission to access this page.')
            raise PermissionDenied
        
        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredMixin:
    """Mixin to require specific permissions for class-based views"""
    required_permissions = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            return redirect('core:login')
        
        for permission in self.required_permissions:
            if not has_permission(request.user, permission):
                messages.error(request, f'You do not have the required permission: {permission}')
                raise PermissionDenied
        
        return super().dispatch(request, *args, **kwargs)


# Template context processor
def rbac_context(request):
    """Add RBAC context to templates"""
    if request.user.is_authenticated:
        return {
            'user_role': get_user_role(request.user),
            'is_admin': has_role(request.user, Role.ADMIN),
            'is_analyst': has_role(request.user, Role.ANALYST),
            'is_user': has_role(request.user, Role.USER),
            'Role': Role,
        }
    return {
        'user_role': None,
        'is_admin': False,
        'is_analyst': False,
        'is_user': False,
        'Role': Role,
    }
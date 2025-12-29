"""
Mixins for views that need user organization access
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from apps.accounts.models import UserProfile
from apps.core.models import Organization


class OrganizationRequiredMixin(LoginRequiredMixin):
    """
    Mixin that ensures the user has a profile with an organization.
    Provides safe access to user's organization.
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        # Ensure user has a profile
        if not hasattr(request.user, 'profile'):
            # Create profile on the fly if needed
            default_org, _ = Organization.objects.get_or_create(
                name='Default Organization',
                defaults={
                    'code': 'DEFAULT',
                    'description': 'Default organization for users'
                }
            )
            
            UserProfile.objects.create(
                user=request.user,
                organization=default_org,
                role='admin' if request.user.is_superuser else 'user',
                department='General'
            )
            
            messages.info(request, "Your user profile has been created.")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_user_organization(self):
        """
        Safe method to get user's organization
        """
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile.organization
        return None
    
    def get_queryset(self):
        """
        Filter queryset by user's organization if applicable
        """
        queryset = super().get_queryset()
        organization = self.get_user_organization()
        
        if organization and hasattr(queryset.model, 'organization'):
            return queryset.filter(organization=organization)
        return queryset


def get_user_organization(user):
    """
    Utility function to safely get a user's organization.
    Creates profile if it doesn't exist.
    """
    if not user.is_authenticated:
        return None
    
    try:
        return user.profile.organization
    except (AttributeError, UserProfile.DoesNotExist):
        # Create profile on the fly
        default_org, _ = Organization.objects.get_or_create(
            name='Default Organization',
            defaults={
                'code': 'DEFAULT', 
                'description': 'Default organization for users'
            }
        )
        
        profile = UserProfile.objects.create(
            user=user,
            organization=default_org,
            role='admin' if user.is_superuser else 'user',
            department='General'
        )
        
        return profile.organization
"""
Account management views
"""
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, UpdateView
)
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
    LogoutView as DjangoLogoutView,
    PasswordChangeView as DjangoPasswordChangeView,
    PasswordResetView as DjangoPasswordResetView
)
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.contrib import messages
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .serializers import UserSerializer, UserProfileSerializer


class LoginView(DjangoLoginView):
    """Custom login view with styled template and proper redirects
    
    Uses the auth/login.html template which includes:
    - Gradient animated background
    - Glass-effect login card
    - SSO integration placeholders
    - Demo credentials display
    
    Redirects authenticated users to home page after login.
    """
    template_name = 'auth/login.html'  # Use the nicely styled auth template
    redirect_authenticated_user = True
    success_url = reverse_lazy('core:home')  # Redirect to home page after login
    
    def form_valid(self, form):
        messages.success(self.request, 'Welcome back!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any messages to context for display
        context['show_messages'] = True
        return context


class LogoutView(DjangoLogoutView):
    """Secure logout view with POST-only requirement
    
    Security features:
    - Only accepts POST requests to prevent CSRF attacks
    - Displays success message with username before logout
    - Redirects GET requests with warning message
    - Uses modal confirmation in UI (see base.html)
    
    After logout, users are redirected to the login page.
    """
    next_page = reverse_lazy('accounts:login')  # Redirect to login page after logout
    http_method_names = ['post', 'options']  # Only allow POST for security
    
    def dispatch(self, request, *args, **kwargs):
        # Handle GET requests by redirecting to home with message
        if request.method == 'GET':
            if request.user.is_authenticated:
                messages.warning(request, 'Please use the logout button in the menu to logout securely.')
                return redirect('core:home')
            else:
                return redirect('accounts:login')
        
        # Handle POST requests normally
        if request.user.is_authenticated:
            username = request.user.get_username()
            messages.success(request, f'Goodbye {username}! You have been logged out successfully.')
        return super().dispatch(request, *args, **kwargs)


class RegisterView(CreateView):
    """User registration view"""
    model = User
    template_name = 'accounts/register.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'password']
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create user profile
        UserProfile.objects.get_or_create(user=self.object)
        messages.success(self.request, 'Account created successfully! Please log in.')
        return response


class ProfileView(OrganizationRequiredMixin, UpdateView):
    """User profile view"""
    model = User
    template_name = 'accounts/profile.html'
    fields = ['first_name', 'last_name', 'email']
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'], created = UserProfile.objects.get_or_create(
            user=self.request.user
        )
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


class UserListView(OrganizationRequiredMixin, ListView):
    """List all users (admin only)"""
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by('-date_joined')


class UserDetailView(OrganizationRequiredMixin, DetailView):
    """User detail view"""
    model = User
    template_name = 'accounts/user_detail.html'
    context_object_name = 'user_obj'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'], created = UserProfile.objects.get_or_create(
            user=self.object
        )
        return context


class PasswordChangeView(DjangoPasswordChangeView):
    """Password change view"""
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')
    
    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully!')
        return super().form_valid(form)


class PasswordResetView(DjangoPasswordResetView):
    """Password reset view"""
    template_name = 'accounts/password_reset.html'
    success_url = reverse_lazy('accounts:password_reset_done')
    email_template_name = 'accounts/password_reset_email.html'


# API ViewSets
class UserViewSet(viewsets.ModelViewSet):
    """User API ViewSet"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        # Get profile safely
        try:
            profile = request.user.profile
        except AttributeError:
            # Create profile if it doesn't exist
            from apps.core.models import Organization
            default_org, _ = Organization.objects.get_or_create(
                name='Default Organization',
                defaults={'code': 'DEFAULT', 'description': 'Default organization for users'}
            )
            profile = UserProfile.objects.create(
                user=request.user,
                organization=default_org,
                role='admin' if request.user.is_superuser else 'user',
                department='General'
            )
        
        profile_data = UserProfileSerializer(profile).data
        
        return Response({
            'user': serializer.data,
            'profile': profile_data
        })
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password"""
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not request.user.check_password(old_password):
            return Response(
                {'error': 'Invalid old password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response({'message': 'Password changed successfully'})


class UserProfileViewSet(viewsets.ModelViewSet):
    """User Profile API ViewSet"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserProfile.objects.filter(user__is_active=True)
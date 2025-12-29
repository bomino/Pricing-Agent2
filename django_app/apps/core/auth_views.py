"""
Authentication views with RBAC support
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .rbac import assign_role, Role, get_user_role, create_roles_and_permissions
from .models import Organization
from apps.accounts.models import UserProfile
import logging

logger = logging.getLogger(__name__)


class LoginView(View):
    """Enhanced login view with role detection"""
    template_name = 'auth/login.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return self.redirect_by_role(request.user)
        return render(request, self.template_name)
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        
        # Allow login with email or username
        if '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                username = user_obj.username
            except User.DoesNotExist:
                pass
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Set session expiry based on remember me
            if not remember:
                request.session.set_expiry(0)  # Browser close
            else:
                request.session.set_expiry(1209600)  # 2 weeks
            
            # Log successful login
            logger.info(f"User {user.username} logged in with role {get_user_role(user)}")
            
            # Welcome message with role
            role = get_user_role(user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}! You are logged in as {role.label}.')
            
            # Redirect based on role
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return self.redirect_by_role(user)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
            logger.warning(f"Failed login attempt for username: {username}")
            return render(request, self.template_name)
    
    def redirect_by_role(self, user):
        """Redirect user based on their role"""
        role = get_user_role(user)
        
        if role == Role.ADMIN:
            return redirect('admin:index')
        elif role == Role.ANALYST:
            return redirect('analytics:dashboard')
        else:
            return redirect('core:dashboard')


class LogoutView(View):
    """Logout view"""
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        return self.post(request)
    
    def post(self, request):
        username = request.user.username
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        logger.info(f"User {username} logged out")
        return redirect('core:login')


class RegisterView(CreateView):
    """User registration view with organization creation"""
    template_name = 'auth/register.html'
    success_url = reverse_lazy('core:login')
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return render(request, self.template_name)
    
    @transaction.atomic
    def post(self, request):
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        organization_name = request.POST.get('organization_name')
        organization_code = request.POST.get('organization_code')
        role = request.POST.get('role', Role.USER)
        
        # Validation
        errors = []
        
        if User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        
        if User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        
        if password1 != password2:
            errors.append('Passwords do not match.')
        
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, self.template_name, {'form_data': request.POST})
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create or get organization
            if organization_code:
                # Try to join existing organization
                try:
                    organization = Organization.objects.get(code=organization_code)
                except Organization.DoesNotExist:
                    messages.error(request, 'Invalid organization code.')
                    user.delete()
                    return render(request, self.template_name, {'form_data': request.POST})
            else:
                # Create new organization
                organization = Organization.objects.create(
                    name=organization_name or f"{first_name}'s Organization",
                    code=Organization.generate_code(),
                    type='buyer'
                )
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                organization=organization,
                role=role,
                phone='',
                department='',
                position=''
            )
            
            # Assign role
            assign_role(user, role)
            
            messages.success(request, 'Registration successful! Please log in.')
            logger.info(f"New user registered: {username} with role {role}")
            
            return redirect('core:login')
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            messages.error(request, 'Registration failed. Please try again.')
            return render(request, self.template_name, {'form_data': request.POST})


class PasswordResetView(View):
    """Password reset request view"""
    template_name = 'auth/password_reset.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            # Here you would send password reset email
            # For now, we'll just show a success message
            messages.success(request, 'Password reset instructions have been sent to your email.')
            logger.info(f"Password reset requested for {email}")
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            messages.success(request, 'If an account exists with this email, you will receive password reset instructions.')
        
        return redirect('core:login')


class ProfileView(TemplateView):
    """User profile view"""
    template_name = 'auth/profile.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_role'] = get_user_role(self.request.user)
        return context
    
    def post(self, request):
        user = request.user
        profile = user.profile
        
        # Update user info
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update profile info
        profile.phone = request.POST.get('phone', profile.phone)
        profile.department = request.POST.get('department', profile.department)
        profile.position = request.POST.get('position', profile.position)
        profile.save()
        
        messages.success(request, 'Profile updated successfully.')
        return redirect('core:profile')


class UserManagementView(TemplateView):
    """Admin view for managing users and roles"""
    template_name = 'auth/user_management.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        # Check if user is admin
        if get_user_role(self.request.user) != Role.ADMIN:
            messages.error(self.request, 'You do not have permission to access this page.')
            return redirect('core:dashboard')
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.all().select_related('userprofile')
        context['roles'] = Role.choices
        return context
    
    def post(self, request):
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            
            if action == 'change_role':
                new_role = request.POST.get('role')
                assign_role(user, new_role)
                messages.success(request, f'Role updated for {user.username}')
                
            elif action == 'toggle_active':
                user.is_active = not user.is_active
                user.save()
                status = 'activated' if user.is_active else 'deactivated'
                messages.success(request, f'User {user.username} has been {status}')
                
            elif action == 'delete':
                username = user.username
                user.delete()
                messages.success(request, f'User {username} has been deleted')
                
        except User.DoesNotExist:
            messages.error(request, 'User not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('core:user_management')
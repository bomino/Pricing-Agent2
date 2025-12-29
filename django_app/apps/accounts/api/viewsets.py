"""
Accounts API viewsets
"""
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination

from apps.accounts.models import UserProfile
from apps.core.models import Organization, AuditLog
from .serializers import (
    UserSerializer, UserProfileSerializer, OrganizationSerializer,
    UserCreateSerializer, UserProfileUpdateSerializer, 
    ChangePasswordSerializer, UserListSerializer,
    OrganizationDetailSerializer, UserStatsSerializer,
    LoginHistorySerializer, UserActivitySerializer,
    BulkUserOperationSerializer, OrganizationStatsSerializer,
    UserPermissionsSerializer
)
from apps.core.security import SecurityMixin, AuditMixin
from apps.core.pagination import StandardResultsSetPagination


class OrganizationViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.
    
    Provides CRUD operations for organizations with proper access control,
    filtering, searching, and audit logging.
    """
    
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter organizations based on user permissions"""
        user = self.request.user
        
        if user.is_superuser:
            return Organization.objects.all()
        
        # Regular users can only see their own organization
        try:
            user_profile = user.profile
            return Organization.objects.filter(id=user_profile.organization.id)
        except UserProfile.DoesNotExist:
            return Organization.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return OrganizationDetailSerializer
        return OrganizationSerializer
    
    def perform_create(self, serializer):
        """Create organization with audit logging"""
        organization = serializer.save()
        self.log_action('create', organization)
    
    def perform_update(self, serializer):
        """Update organization with audit logging"""
        original_data = self.get_object().__dict__.copy()
        organization = serializer.save()
        self.log_action('update', organization, changes={
            'original': original_data,
            'updated': serializer.validated_data
        })
    
    def perform_destroy(self, instance):
        """Soft delete organization"""
        instance.is_active = False
        instance.save()
        self.log_action('deactivate', instance)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """Activate an organization"""
        organization = self.get_object()
        organization.is_active = True
        organization.save()
        self.log_action('activate', organization)
        
        return Response(
            {'status': 'Organization activated'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get users in organization"""
        organization = self.get_object()
        users = User.objects.filter(profile__organization=organization)
        
        # Apply pagination
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = UserListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get organization statistics"""
        organization = self.get_object()
        
        user_profiles = organization.user_profiles.all()
        stats = {
            'total_users': user_profiles.count(),
            'active_users': user_profiles.filter(is_active=True).count(),
            'users_by_role': dict(
                user_profiles.values('role').annotate(count=Count('role')).values_list('role', 'count')
            ),
            'recent_activity': {
                'new_users_30_days': user_profiles.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count(),
            }
        }
        
        return Response(stats)


class UserViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing users.
    
    Provides CRUD operations for users with proper access control,
    filtering, searching, and audit logging.
    """
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'profile__role', 'profile__organization']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'profile__job_title']
    ordering_fields = ['username', 'email', 'date_joined', 'last_login']
    ordering = ['-date_joined']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter users based on permissions"""
        user = self.request.user
        
        if user.is_superuser:
            return User.objects.all().select_related('profile', 'profile__organization')
        
        # Users can only see users in their organization
        try:
            user_profile = user.profile
            return User.objects.filter(
                profile__organization=user_profile.organization
            ).select_related('profile', 'profile__organization')
        except UserProfile.DoesNotExist:
            return User.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'list':
            return UserListSerializer
        return UserSerializer
    
    def perform_create(self, serializer):
        """Create user with audit logging"""
        user = serializer.save()
        self.log_action('create_user', user)
    
    def perform_update(self, serializer):
        """Update user with audit logging"""
        original_data = self.get_object().__dict__.copy()
        user = serializer.save()
        self.log_action('update_user', user, changes={
            'original': original_data,
            'updated': serializer.validated_data
        })
    
    def perform_destroy(self, instance):
        """Soft delete user"""
        instance.is_active = False
        instance.save()
        self.log_action('deactivate_user', instance)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change user password"""
        user = self.get_object()
        
        # Users can only change their own password unless they're admin
        if user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only change your own password'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            self.log_action('change_password', user)
            return Response({'status': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """Activate a user"""
        user = self.get_object()
        user.is_active = True
        user.save()
        
        # Also activate user profile if it exists
        try:
            user.profile.is_active = True
            user.profile.save()
        except UserProfile.DoesNotExist:
            pass
        
        self.log_action('activate_user', user)
        return Response({'status': 'User activated'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        """Deactivate a user"""
        user = self.get_object()
        user.is_active = False
        user.save()
        
        # Also deactivate user profile if it exists
        try:
            user.profile.is_active = False
            user.profile.save()
        except UserProfile.DoesNotExist:
            pass
        
        self.log_action('deactivate_user', user)
        return Response({'status': 'User deactivated'})
    
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get user permissions"""
        user = self.get_object()
        
        # Users can only view their own permissions unless they're admin
        if user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only view your own permissions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_perms = user.user_permissions.values_list('codename', flat=True)
        group_perms = user.groups.values_list('permissions__codename', flat=True)
        all_perms = list(user.get_all_permissions())
        
        role = None
        try:
            role = user.profile.role
        except UserProfile.DoesNotExist:
            pass
        
        data = {
            'user_permissions': list(user_perms),
            'group_permissions': list(group_perms),
            'all_permissions': all_perms,
            'has_admin_access': user.is_staff or user.is_superuser,
            'role': role
        }
        
        serializer = UserPermissionsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_operations(self, request):
        """Perform bulk operations on users"""
        serializer = BulkUserOperationSerializer(data=request.data)
        
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            operation = serializer.validated_data['operation']
            parameters = serializer.validated_data.get('parameters', {})
            
            users = User.objects.filter(id__in=user_ids)
            results = {'success': [], 'errors': []}
            
            for user in users:
                try:
                    if operation == 'activate':
                        user.is_active = True
                        user.save()
                        results['success'].append(str(user.id))
                        
                    elif operation == 'deactivate':
                        user.is_active = False
                        user.save()
                        results['success'].append(str(user.id))
                        
                    elif operation == 'change_role':
                        if hasattr(user, 'profile'):
                            user.profile.role = parameters['role']
                            user.profile.save()
                            results['success'].append(str(user.id))
                        else:
                            results['errors'].append({
                                'user_id': str(user.id),
                                'error': 'User has no profile'
                            })
                    
                    # Log the action
                    self.log_action(f'bulk_{operation}', user)
                    
                except Exception as e:
                    results['errors'].append({
                        'user_id': str(user.id),
                        'error': str(e)
                    })
            
            return Response(results)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def stats(self, request):
        """Get user statistics"""
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        # Users by role
        role_stats = dict(
            UserProfile.objects.values('role').annotate(
                count=Count('role')
            ).values_list('role', 'count')
        )
        
        # Users by organization
        org_stats = dict(
            UserProfile.objects.select_related('organization').values(
                'organization__name'
            ).annotate(count=Count('organization')).values_list(
                'organization__name', 'count'
            )
        )
        
        # New users in last 30 days
        new_users_30_days = User.objects.filter(
            date_joined__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'new_users_30_days': new_users_30_days,
            'users_by_role': role_stats,
            'users_by_organization': org_stats,
        }
        
        serializer = UserStatsSerializer(stats)
        return Response(serializer.data)


class UserProfileViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user profiles.
    
    Provides CRUD operations for user profiles with proper access control.
    """
    
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'organization', 'is_active', 'department']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'job_title', 'department']
    ordering_fields = ['user__first_name', 'user__last_name', 'job_title', 'created_at']
    ordering = ['user__first_name', 'user__last_name']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter profiles based on permissions"""
        user = self.request.user
        
        if user.is_superuser:
            return UserProfile.objects.all().select_related('user', 'organization', 'manager')
        
        # Users can only see profiles in their organization
        try:
            user_profile = user.profile
            return UserProfile.objects.filter(
                organization=user_profile.organization
            ).select_related('user', 'organization', 'manager')
        except UserProfile.DoesNotExist:
            return UserProfile.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action in ['update', 'partial_update']:
            return UserProfileUpdateSerializer
        return UserProfileSerializer
    
    def perform_update(self, serializer):
        """Update profile with audit logging"""
        original_data = self.get_object().__dict__.copy()
        profile = serializer.save()
        self.log_action('update_profile', profile, changes={
            'original': original_data,
            'updated': serializer.validated_data
        })
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['patch'])
    def update_me(self, request):
        """Update current user's profile"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UserProfileUpdateSerializer(
            profile, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            self.log_action('update_own_profile', profile)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuthViewSet(viewsets.ViewSet):
    """
    Authentication endpoints.
    
    Provides login, logout, and token management functionality.
    """
    
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    
    @action(detail=False, methods=['post'], permission_classes=[])
    def login(self, request):
        """Authenticate user and return token"""
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user:
            if not user.is_active:
                return Response(
                    {'error': 'Account is disabled'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            login(request, user)
            
            # Log successful login
            AuditLog.objects.create(
                user=user,
                action='login',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Return user data
            serializer = UserSerializer(user)
            return Response({
                'user': serializer.data,
                'message': 'Login successful'
            })
        
        else:
            # Log failed login attempt
            try:
                failed_user = User.objects.get(username=username)
                AuditLog.objects.create(
                    user=failed_user,
                    action='login_failed',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except User.DoesNotExist:
                pass
            
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """Logout user"""
        # Log logout
        AuditLog.objects.create(
            user=request.user,
            action='logout',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logout(request)
        
        return Response({'message': 'Logout successful'})
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def profile(self, request):
        """Get current user profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user activity and audit logs.
    
    Provides read-only access to audit logs and user activity.
    """
    
    queryset = AuditLog.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'action', 'object_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter activity based on permissions"""
        user = self.request.user
        
        if user.is_superuser:
            return AuditLog.objects.all()
        
        # Regular users can only see their organization's activity
        try:
            user_profile = user.profile
            return AuditLog.objects.filter(
                organization=user_profile.organization
            )
        except UserProfile.DoesNotExist:
            return AuditLog.objects.filter(user=user)
    
    def list(self, request):
        """List activity logs"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = []
            for log in page:
                data.append({
                    'id': str(log.id),
                    'user': {
                        'id': str(log.user.id) if log.user else None,
                        'username': log.user.username if log.user else None,
                        'email': log.user.email if log.user else None,
                    },
                    'action': log.action,
                    'object_type': log.object_type,
                    'object_id': str(log.object_id) if log.object_id else None,
                    'object_repr': log.object_repr,
                    'changes': log.changes,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at,
                })
            
            return self.get_paginated_response(data)
        
        # If no pagination, return all results
        data = [
            {
                'id': str(log.id),
                'user': {
                    'id': str(log.user.id) if log.user else None,
                    'username': log.user.username if log.user else None,
                    'email': log.user.email if log.user else None,
                },
                'action': log.action,
                'object_type': log.object_type,
                'object_id': str(log.object_id) if log.object_id else None,
                'object_repr': log.object_repr,
                'changes': log.changes,
                'ip_address': log.ip_address,
                'created_at': log.created_at,
            }
            for log in queryset
        ]
        
        return Response(data)
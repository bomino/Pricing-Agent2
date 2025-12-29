"""
Accounts API URL configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

# Create router and register viewsets
router = DefaultRouter()
router.register(r'users', viewsets.UserViewSet, basename='users')
router.register(r'profiles', viewsets.UserProfileViewSet, basename='user-profiles')
router.register(r'organizations', viewsets.OrganizationViewSet, basename='organizations')
router.register(r'auth', viewsets.AuthViewSet, basename='auth')
router.register(r'activity', viewsets.ActivityViewSet, basename='activity')

app_name = 'accounts-api'

urlpatterns = [
    # API router URLs
    path('', include(router.urls)),
    
    # Additional custom endpoints can be added here if needed
]

# API endpoints documentation:
"""
Organizations:
- GET    /api/v1/accounts/organizations/           - List organizations
- POST   /api/v1/accounts/organizations/           - Create organization
- GET    /api/v1/accounts/organizations/{id}/      - Get organization details
- PUT    /api/v1/accounts/organizations/{id}/      - Update organization
- PATCH  /api/v1/accounts/organizations/{id}/      - Partial update organization
- DELETE /api/v1/accounts/organizations/{id}/      - Delete organization
- POST   /api/v1/accounts/organizations/{id}/activate/ - Activate organization
- GET    /api/v1/accounts/organizations/{id}/users/ - Get organization users
- GET    /api/v1/accounts/organizations/{id}/stats/ - Get organization stats

Users:
- GET    /api/v1/accounts/users/                   - List users
- POST   /api/v1/accounts/users/                   - Create user
- GET    /api/v1/accounts/users/{id}/              - Get user details
- PUT    /api/v1/accounts/users/{id}/              - Update user
- PATCH  /api/v1/accounts/users/{id}/              - Partial update user
- DELETE /api/v1/accounts/users/{id}/              - Delete user
- GET    /api/v1/accounts/users/me/                - Get current user
- POST   /api/v1/accounts/users/{id}/change_password/ - Change user password
- POST   /api/v1/accounts/users/{id}/activate/     - Activate user
- POST   /api/v1/accounts/users/{id}/deactivate/   - Deactivate user
- GET    /api/v1/accounts/users/{id}/permissions/  - Get user permissions
- POST   /api/v1/accounts/users/bulk_operations/   - Bulk user operations
- GET    /api/v1/accounts/users/stats/             - Get user statistics

User Profiles:
- GET    /api/v1/accounts/profiles/                - List user profiles
- GET    /api/v1/accounts/profiles/{id}/           - Get profile details
- PUT    /api/v1/accounts/profiles/{id}/           - Update profile
- PATCH  /api/v1/accounts/profiles/{id}/           - Partial update profile
- GET    /api/v1/accounts/profiles/me/             - Get current user profile
- PATCH  /api/v1/accounts/profiles/update_me/      - Update current user profile

Authentication:
- POST   /api/v1/accounts/auth/login/              - Login user
- POST   /api/v1/accounts/auth/logout/             - Logout user
- GET    /api/v1/accounts/auth/profile/            - Get current user profile

Activity:
- GET    /api/v1/accounts/activity/                - List activity logs

Query Parameters:
- page: Page number for pagination
- page_size: Number of items per page (default: 50, max: 100)
- search: Search term for filtering
- ordering: Field to order by (prefix with '-' for descending)
- is_active: Filter by active status (true/false)
- role: Filter by user role
- organization: Filter by organization ID
- type: Filter organizations by type

Example Requests:

1. List users with filtering:
   GET /api/v1/accounts/users/?search=john&role=admin&is_active=true&page=1

2. Create new user:
   POST /api/v1/accounts/users/
   {
     "username": "john.doe",
     "email": "john.doe@example.com",
     "first_name": "John",
     "last_name": "Doe",
     "password": "secure_password123",
     "password_confirm": "secure_password123",
     "organization_code": "ORG001"
   }

3. Update user profile:
   PATCH /api/v1/accounts/profiles/me/
   {
     "job_title": "Senior Manager",
     "department": "Procurement",
     "phone": "+1-555-123-4567"
   }

4. Bulk activate users:
   POST /api/v1/accounts/users/bulk_operations/
   {
     "user_ids": ["uuid1", "uuid2", "uuid3"],
     "operation": "activate"
   }

5. Change password:
   POST /api/v1/accounts/users/{id}/change_password/
   {
     "old_password": "current_password",
     "new_password": "new_secure_password",
     "new_password_confirm": "new_secure_password"
   }

Response Format:
All responses follow a consistent format:
- List endpoints return paginated results with 'count', 'next', 'previous', and 'results'
- Detail endpoints return the object data directly
- Error responses include 'error' message and appropriate HTTP status codes
- Success operations return 'status' message

Permissions:
- IsAuthenticated: Required for all endpoints
- IsAdminUser: Required for admin operations (bulk ops, stats, etc.)
- Users can only access their own data unless they have admin privileges
- Organization filtering automatically applied based on user's organization
"""
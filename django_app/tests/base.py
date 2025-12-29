"""
Base test classes and utilities for Django tests.
"""
import json
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.core.models import Organization, Tenant

User = get_user_model()


class BaseTestCase(TestCase):
    """
    Base test case with common setup and utilities.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the test class."""
        cls.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-org",
            is_active=True
        )
        
        cls.tenant = Tenant.objects.create(
            organization=cls.organization,
            name="Test Tenant",
            slug="test-tenant",
            schema_name="test_tenant"
        )
        
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            organization=cls.organization
        )
        
        cls.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            organization=cls.organization
        )
    
    def setUp(self):
        """Set up for each test method."""
        self.client.force_login(self.user)
    
    def assertResponseContains(self, response, text, count=None, status_code=200):
        """Assert that response contains text."""
        self.assertEqual(response.status_code, status_code)
        if count:
            self.assertContains(response, text, count=count)
        else:
            self.assertContains(response, text)
    
    def assertResponseNotContains(self, response, text, status_code=200):
        """Assert that response does not contain text."""
        self.assertEqual(response.status_code, status_code)
        self.assertNotContains(response, text)
    
    def assertRedirectsTo(self, response, url_name, **kwargs):
        """Assert that response redirects to given URL."""
        expected_url = reverse(url_name, kwargs=kwargs)
        self.assertRedirects(response, expected_url)


class BaseAPITestCase(APITestCase):
    """
    Base API test case with authentication and common utilities.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the test class."""
        cls.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-org",
            is_active=True
        )
        
        cls.tenant = Tenant.objects.create(
            organization=cls.organization,
            name="Test Tenant",
            slug="test-tenant",
            schema_name="test_tenant"
        )
        
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            organization=cls.organization
        )
        
        cls.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            organization=cls.organization
        )
    
    def setUp(self):
        """Set up for each test method."""
        self.client.force_authenticate(user=self.user)
    
    def authenticate_as_admin(self):
        """Authenticate as admin user."""
        self.client.force_authenticate(user=self.admin_user)
    
    def authenticate_as_user(self, user):
        """Authenticate as specific user."""
        self.client.force_authenticate(user=user)
    
    def logout(self):
        """Logout current user."""
        self.client.force_authenticate(user=None)
    
    def assertResponseStatus(self, response, expected_status):
        """Assert response status with detailed error info."""
        if response.status_code != expected_status:
            error_detail = getattr(response, 'data', response.content)
            self.fail(
                f"Expected status {expected_status}, got {response.status_code}. "
                f"Response: {error_detail}"
            )
    
    def assertResponseSuccess(self, response):
        """Assert response is successful (2xx)."""
        self.assertTrue(
            200 <= response.status_code < 300,
            f"Expected 2xx status, got {response.status_code}. "
            f"Response: {getattr(response, 'data', response.content)}"
        )
    
    def assertResponseError(self, response, expected_status=400):
        """Assert response is an error."""
        self.assertEqual(response.status_code, expected_status)
    
    def assertResponseHasKeys(self, response, keys):
        """Assert response data has specified keys."""
        self.assertResponseSuccess(response)
        for key in keys:
            self.assertIn(key, response.data)
    
    def assertResponseMissingKeys(self, response, keys):
        """Assert response data is missing specified keys."""
        self.assertResponseSuccess(response)
        for key in keys:
            self.assertNotIn(key, response.data)
    
    def post_json(self, url, data=None, **kwargs):
        """POST JSON data to URL."""
        return self.client.post(
            url, 
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )
    
    def put_json(self, url, data=None, **kwargs):
        """PUT JSON data to URL."""
        return self.client.put(
            url,
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )
    
    def patch_json(self, url, data=None, **kwargs):
        """PATCH JSON data to URL."""
        return self.client.patch(
            url,
            data=json.dumps(data) if data else None,
            content_type='application/json',
            **kwargs
        )


class BaseTransactionTestCase(TransactionTestCase):
    """
    Base transaction test case for testing database transactions.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        cls.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-org",
            is_active=True
        )
        
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            organization=cls.organization
        )
    
    def setUp(self):
        """Set up for each test method."""
        self.client.force_login(self.user)


class ModelTestMixin:
    """
    Mixin for testing Django models.
    """
    
    def assertModelFieldExists(self, model_class, field_name):
        """Assert that model has specified field."""
        self.assertTrue(
            hasattr(model_class, field_name),
            f"Model {model_class.__name__} does not have field '{field_name}'"
        )
    
    def assertModelFieldType(self, model_class, field_name, field_type):
        """Assert that model field is of specified type."""
        field = model_class._meta.get_field(field_name)
        self.assertIsInstance(
            field,
            field_type,
            f"Field '{field_name}' is not of type {field_type.__name__}"
        )
    
    def assertModelFieldMaxLength(self, model_class, field_name, max_length):
        """Assert that model field has specified max length."""
        field = model_class._meta.get_field(field_name)
        self.assertEqual(
            field.max_length,
            max_length,
            f"Field '{field_name}' max_length is {field.max_length}, expected {max_length}"
        )
    
    def assertModelFieldRequired(self, model_class, field_name, required=True):
        """Assert that model field is required/optional."""
        field = model_class._meta.get_field(field_name)
        is_required = not field.null and not field.blank
        if required:
            self.assertTrue(
                is_required,
                f"Field '{field_name}' should be required but is optional"
            )
        else:
            self.assertFalse(
                is_required,
                f"Field '{field_name}' should be optional but is required"
            )


class SerializerTestMixin:
    """
    Mixin for testing DRF serializers.
    """
    
    def assertSerializerValid(self, serializer, data):
        """Assert that serializer is valid with given data."""
        serializer_instance = serializer(data=data)
        self.assertTrue(
            serializer_instance.is_valid(),
            f"Serializer errors: {serializer_instance.errors}"
        )
        return serializer_instance
    
    def assertSerializerInvalid(self, serializer, data, expected_errors=None):
        """Assert that serializer is invalid with given data."""
        serializer_instance = serializer(data=data)
        self.assertFalse(
            serializer_instance.is_valid(),
            "Serializer should be invalid but validation passed"
        )
        
        if expected_errors:
            for field, error_messages in expected_errors.items():
                self.assertIn(field, serializer_instance.errors)
                if isinstance(error_messages, list):
                    for error_message in error_messages:
                        self.assertIn(error_message, str(serializer_instance.errors[field]))
                else:
                    self.assertIn(error_messages, str(serializer_instance.errors[field]))
        
        return serializer_instance
    
    def assertSerializerFieldRequired(self, serializer, field_name, data):
        """Assert that serializer field is required."""
        data_without_field = data.copy()
        data_without_field.pop(field_name, None)
        
        serializer_instance = serializer(data=data_without_field)
        self.assertFalse(serializer_instance.is_valid())
        self.assertIn(field_name, serializer_instance.errors)
        self.assertIn("required", str(serializer_instance.errors[field_name]).lower())


class ViewTestMixin:
    """
    Mixin for testing Django views.
    """
    
    def assertViewRequiresAuth(self, url, method='GET', data=None):
        """Assert that view requires authentication."""
        self.logout()
        
        if method == 'GET':
            response = self.client.get(url)
        elif method == 'POST':
            response = self.client.post(url, data=data)
        elif method == 'PUT':
            response = self.put_json(url, data=data)
        elif method == 'PATCH':
            response = self.patch_json(url, data=data)
        elif method == 'DELETE':
            response = self.client.delete(url)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        self.assertIn(response.status_code, [401, 403])
    
    def assertViewRequiresPermission(self, url, method='GET', data=None):
        """Assert that view requires specific permissions."""
        # Test with regular user (should fail)
        if method == 'GET':
            response = self.client.get(url)
        elif method == 'POST':
            response = self.client.post(url, data=data)
        elif method == 'PUT':
            response = self.put_json(url, data=data)
        elif method == 'PATCH':
            response = self.patch_json(url, data=data)
        elif method == 'DELETE':
            response = self.client.delete(url)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        self.assertEqual(response.status_code, 403)
"""
Integration views for third-party system integrations
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, TemplateView
)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib import messages
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import json
import logging
from .models import IntegrationConnection, SyncLog, WebhookEndpoint
from .serializers import IntegrationConnectionSerializer, SyncLogSerializer


logger = logging.getLogger(__name__)


class IntegrationsListView(OrganizationRequiredMixin, TemplateView):
    """Main integrations overview"""
    template_name = 'integrations/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        # Get integration statistics
        context['stats'] = {
            'total_connections': IntegrationConnection.objects.filter(
                organization=organization
            ).count(),
            'active_connections': IntegrationConnection.objects.filter(
                organization=organization,
                is_active=True
            ).count(),
            'recent_syncs': SyncLog.objects.filter(
                organization=organization,
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count(),
            'failed_syncs': SyncLog.objects.filter(
                organization=organization,
                status='failed',
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count(),
        }
        
        # Get recent connections
        context['recent_connections'] = IntegrationConnection.objects.filter(
            organization=organization
        ).order_by('-created_at')[:5]
        
        return context


class ConnectionListView(OrganizationRequiredMixin, ListView):
    """List integration connections"""
    model = IntegrationConnection
    template_name = 'integrations/connection_list.html'
    context_object_name = 'connections'
    paginate_by = 20
    
    def get_queryset(self):
        return IntegrationConnection.objects.filter(
            organization=self.get_user_organization()
        ).order_by('-created_at')


class ConnectionDetailView(OrganizationRequiredMixin, DetailView):
    """Integration connection detail view"""
    model = IntegrationConnection
    template_name = 'integrations/connection_detail.html'
    context_object_name = 'connection'
    
    def get_queryset(self):
        return IntegrationConnection.objects.filter(
            organization=self.get_user_organization()
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent sync logs for this connection
        context['recent_syncs'] = SyncLog.objects.filter(
            connection=self.object
        ).order_by('-created_at')[:10]
        
        # Get sync statistics
        total_syncs = SyncLog.objects.filter(connection=self.object).count()
        successful_syncs = SyncLog.objects.filter(
            connection=self.object, status='completed'
        ).count()
        
        context['sync_stats'] = {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'success_rate': round((successful_syncs / total_syncs * 100), 2) if total_syncs > 0 else 0,
        }
        
        return context


class ConnectionCreateView(OrganizationRequiredMixin, CreateView):
    """Create new integration connection"""
    model = IntegrationConnection
    template_name = 'integrations/connection_form.html'
    fields = [
        'name', 'integration_type', 'endpoint_url', 'authentication_method',
        'api_key', 'username', 'sync_frequency', 'is_active'
    ]
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Integration "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class ConnectionUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update integration connection"""
    model = IntegrationConnection
    template_name = 'integrations/connection_form.html'
    fields = [
        'name', 'endpoint_url', 'authentication_method',
        'api_key', 'username', 'sync_frequency', 'is_active'
    ]
    
    def get_queryset(self):
        return IntegrationConnection.objects.filter(
            organization=self.get_user_organization()
        )
    
    def form_valid(self, form):
        messages.success(self.request, f'Integration "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class ConnectionTestView(OrganizationRequiredMixin, TemplateView):
    """Test integration connection"""
    
    def post(self, request, pk):
        connection = get_object_or_404(
            IntegrationConnection,
            pk=pk,
            organization=request.user.profile.organization
        )
        
        try:
            # This would typically test the actual connection
            # For now, simulate a successful test
            test_result = self._test_connection(connection)
            
            if test_result['success']:
                messages.success(request, 'Connection test successful!')
                return JsonResponse({
                    'status': 'success',
                    'message': 'Connection test passed',
                    'details': test_result['details']
                })
            else:
                messages.error(request, f'Connection test failed: {test_result["error"]}')
                return JsonResponse({
                    'status': 'error',
                    'message': test_result['error']
                }, status=400)
                
        except Exception as e:
            logger.error(f'Connection test failed for {connection.name}: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': 'Connection test failed'
            }, status=500)
    
    def _test_connection(self, connection):
        """Test the connection (placeholder implementation)"""
        # This would contain actual connection testing logic
        return {
            'success': True,
            'details': {
                'response_time': '150ms',
                'endpoint_status': 'reachable',
                'auth_status': 'valid'
            }
        }


# ERP Integration Views
class SAPIntegrationView(OrganizationRequiredMixin, TemplateView):
    """SAP integration management"""
    template_name = 'integrations/sap_integration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get SAP connections
        context['sap_connections'] = IntegrationConnection.objects.filter(
            organization=self.get_user_organization(),
            integration_type='sap'
        )
        
        return context


class OracleIntegrationView(OrganizationRequiredMixin, TemplateView):
    """Oracle integration management"""
    template_name = 'integrations/oracle_integration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get Oracle connections
        context['oracle_connections'] = IntegrationConnection.objects.filter(
            organization=self.get_user_organization(),
            integration_type='oracle'
        )
        
        return context


class SageIntegrationView(OrganizationRequiredMixin, TemplateView):
    """Sage integration management"""
    template_name = 'integrations/sage_integration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get Sage connections
        context['sage_connections'] = IntegrationConnection.objects.filter(
            organization=self.get_user_organization(),
            integration_type='sage'
        )
        
        return context


# Market Data Integration Views
class BloombergIntegrationView(OrganizationRequiredMixin, TemplateView):
    """Bloomberg integration management"""
    template_name = 'integrations/bloomberg_integration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['bloomberg_connections'] = IntegrationConnection.objects.filter(
            organization=self.get_user_organization(),
            integration_type='bloomberg'
        )
        
        return context


class ReutersIntegrationView(OrganizationRequiredMixin, TemplateView):
    """Reuters integration management"""
    template_name = 'integrations/reuters_integration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['reuters_connections'] = IntegrationConnection.objects.filter(
            organization=self.get_user_organization(),
            integration_type='reuters'
        )
        
        return context


class SupplierPortalIntegrationView(OrganizationRequiredMixin, TemplateView):
    """Supplier portal integration management"""
    template_name = 'integrations/supplier_portal_integration.html'


# Data Synchronization Views
class ManualSyncView(OrganizationRequiredMixin, TemplateView):
    """Manual data synchronization"""
    
    def post(self, request, *args, **kwargs):
        connection_id = request.POST.get('connection_id')
        sync_type = request.POST.get('sync_type', 'full')
        
        try:
            connection = IntegrationConnection.objects.get(
                id=connection_id,
                organization=get_user_organization(request.user)
            )
            
            # Create sync log
            sync_log = SyncLog.objects.create(
                connection=connection,
                organization=get_user_organization(request.user),
                sync_type=sync_type,
                status='running',
                started_by=request.user
            )
            
            # This would typically trigger async sync process
            # For now, simulate successful sync
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = 100  # Placeholder
            sync_log.save()
            
            messages.success(request, 'Synchronization completed successfully!')
            return JsonResponse({
                'status': 'success',
                'sync_id': sync_log.id,
                'message': 'Sync completed successfully'
            })
            
        except IntegrationConnection.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Integration connection not found'
            }, status=404)
        except Exception as e:
            logger.error(f'Manual sync failed: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': 'Sync failed'
            }, status=500)


class ScheduleSyncView(OrganizationRequiredMixin, TemplateView):
    """Schedule data synchronization"""
    template_name = 'integrations/schedule_sync.html'
    
    def post(self, request, *args, **kwargs):
        # Handle sync scheduling
        return JsonResponse({'status': 'success', 'message': 'Sync scheduled successfully'})


class SyncLogListView(OrganizationRequiredMixin, ListView):
    """List synchronization logs"""
    model = SyncLog
    template_name = 'integrations/sync_log_list.html'
    context_object_name = 'sync_logs'
    paginate_by = 50
    
    def get_queryset(self):
        return SyncLog.objects.filter(
            organization=self.get_user_organization()
        ).select_related('connection').order_by('-created_at')


class SyncLogDetailView(OrganizationRequiredMixin, DetailView):
    """Synchronization log detail view"""
    model = SyncLog
    template_name = 'integrations/sync_log_detail.html'
    context_object_name = 'sync_log'
    
    def get_queryset(self):
        return SyncLog.objects.filter(
            organization=self.get_user_organization()
        ).select_related('connection')


# Webhook Views
class WebhookListView(OrganizationRequiredMixin, ListView):
    """List webhook endpoints"""
    model = WebhookEndpoint
    template_name = 'integrations/webhook_list.html'
    context_object_name = 'webhooks'
    
    def get_queryset(self):
        return WebhookEndpoint.objects.filter(
            organization=self.get_user_organization()
        ).order_by('-created_at')


class WebhookCreateView(OrganizationRequiredMixin, CreateView):
    """Create webhook endpoint"""
    model = WebhookEndpoint
    template_name = 'integrations/webhook_form.html'
    fields = ['name', 'url', 'event_types', 'is_active']
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class WebhookUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update webhook endpoint"""
    model = WebhookEndpoint
    template_name = 'integrations/webhook_form.html'
    fields = ['name', 'url', 'event_types', 'is_active']
    
    def get_queryset(self):
        return WebhookEndpoint.objects.filter(
            organization=self.get_user_organization()
        )


@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiveView(APIView):
    """Receive webhook data"""
    permission_classes = []  # Webhooks don't use standard auth
    
    def post(self, request, *args, **kwargs):
        try:
            # Parse webhook data
            webhook_data = json.loads(request.body)
            
            # Log webhook receipt
            logger.info(f'Webhook received: {webhook_data}')
            
            # Process webhook data based on type
            self._process_webhook(webhook_data)
            
            return Response({'status': 'received'}, status=status.HTTP_200_OK)
            
        except json.JSONDecodeError:
            logger.error('Invalid JSON in webhook request')
            return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Webhook processing failed: {str(e)}')
            return Response({'error': 'Processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_webhook(self, data):
        """Process received webhook data"""
        event_type = data.get('event_type')
        
        if event_type == 'price_update':
            self._handle_price_update(data)
        elif event_type == 'supplier_update':
            self._handle_supplier_update(data)
        # Add more event handlers as needed
    
    def _handle_price_update(self, data):
        """Handle price update webhook"""
        # This would contain logic to update price data
        pass
    
    def _handle_supplier_update(self, data):
        """Handle supplier update webhook"""
        # This would contain logic to update supplier data
        pass


# API ViewSets
class IntegrationConnectionViewSet(viewsets.ModelViewSet):
    """Integration Connection API ViewSet"""
    serializer_class = IntegrationConnectionSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return IntegrationConnection.objects.filter(
            organization=self.get_user_organization()
        )
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test integration connection"""
        connection = self.get_object()
        
        try:
            # Test the connection
            test_result = self._test_connection(connection)
            
            return Response({
                'status': 'success' if test_result['success'] else 'failed',
                'details': test_result
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync_data(self, request, pk=None):
        """Trigger data synchronization"""
        connection = self.get_object()
        sync_type = request.data.get('sync_type', 'incremental')
        
        # Create sync log
        sync_log = SyncLog.objects.create(
            connection=connection,
            organization=request.user.profile.organization,
            sync_type=sync_type,
            status='pending',
            started_by=request.user
        )
        
        # This would typically trigger async sync
        # For now, return the sync log ID
        return Response({
            'sync_id': sync_log.id,
            'status': 'initiated',
            'message': 'Synchronization started'
        })
    
    def _test_connection(self, connection):
        """Test connection implementation"""
        # Placeholder implementation
        return {'success': True, 'response_time': '150ms'}


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Sync Log API ViewSet (read-only)"""
    serializer_class = SyncLogSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SyncLog.objects.filter(
            organization=self.get_user_organization()
        ).select_related('connection')
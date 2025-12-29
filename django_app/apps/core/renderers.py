"""
Custom renderers for different response types
"""
from rest_framework import renderers
from rest_framework.renderers import JSONRenderer
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template import RequestContext


class HTMXRenderer(renderers.BaseRenderer):
    """
    Renderer for HTMX requests that returns HTML partials
    """
    media_type = 'text/html'
    format = 'html'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data as HTML partial for HTMX requests
        """
        request = renderer_context.get('request')
        response = renderer_context.get('response')
        view = renderer_context.get('view')
        
        # Check if this is an HTMX request
        if not request or not request.htmx:
            # Fall back to JSON for non-HTMX requests
            return JSONRenderer().render(data, accepted_media_type, renderer_context)
        
        # Get template name from view or data
        template_name = self.get_template_name(view, data, request)
        
        if not template_name:
            # Fall back to JSON if no template specified
            return JSONRenderer().render(data, accepted_media_type, renderer_context)
        
        # Render template with data
        try:
            context = self.get_context_data(data, request, view)
            html = render_to_string(template_name, context, request=request)
            return html.encode('utf-8')
        except Exception as e:
            # Fall back to JSON on template error
            error_data = {
                'error': f'Template rendering failed: {str(e)}',
                'data': data
            }
            return JSONRenderer().render(error_data, accepted_media_type, renderer_context)
    
    def get_template_name(self, view, data, request):
        """
        Get template name for rendering
        """
        # Try to get from view attribute
        if hasattr(view, 'htmx_template_name'):
            return view.htmx_template_name
        
        # Try to get from data
        if isinstance(data, dict) and 'template_name' in data:
            return data['template_name']
        
        # Generate default template name based on view
        if hasattr(view, 'model') and view.model:
            model_name = view.model._meta.model_name
            app_name = view.model._meta.app_label
            action = getattr(view, 'action', 'list')
            return f'partials/{app_name}/{model_name}_{action}.html'
        
        return None
    
    def get_context_data(self, data, request, view):
        """
        Get context data for template rendering
        """
        context = {}
        
        # Add data to context
        if isinstance(data, dict):
            context.update(data)
        else:
            context['data'] = data
        
        # Add request to context
        context['request'] = request
        
        # Add view to context
        context['view'] = view
        
        # Add common context variables
        context['is_htmx'] = True
        
        return context


class JSONAPIRenderer(JSONRenderer):
    """
    JSON:API compliant renderer
    """
    media_type = 'application/vnd.api+json'
    format = 'jsonapi'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data in JSON:API format
        """
        if data is None:
            return b''
        
        request = renderer_context.get('request')
        response = renderer_context.get('response')
        view = renderer_context.get('view')
        
        # Transform data to JSON:API format
        jsonapi_data = self.transform_to_jsonapi(data, request, view)
        
        return super().render(jsonapi_data, accepted_media_type, renderer_context)
    
    def transform_to_jsonapi(self, data, request, view):
        """
        Transform data to JSON:API format
        """
        if isinstance(data, dict):
            # Handle paginated responses
            if 'results' in data:
                return {
                    'data': self.transform_results(data['results'], view),
                    'meta': {
                        'pagination': {
                            'count': data.get('count'),
                            'page': data.get('current_page'),
                            'pages': data.get('total_pages'),
                            'per_page': data.get('page_size'),
                        }
                    },
                    'links': {
                        'next': data.get('next'),
                        'prev': data.get('previous'),
                    }
                }
            # Handle single objects
            elif 'id' in data:
                return {
                    'data': self.transform_object(data, view)
                }
            # Handle errors
            elif 'error' in data:
                return {
                    'errors': [data['error']]
                }
        
        elif isinstance(data, list):
            return {
                'data': self.transform_results(data, view)
            }
        
        return {'data': data}
    
    def transform_results(self, results, view):
        """Transform list of results to JSON:API format"""
        return [self.transform_object(item, view) for item in results]
    
    def transform_object(self, obj, view):
        """Transform single object to JSON:API format"""
        if isinstance(obj, dict):
            obj_id = obj.get('id')
            obj_type = self.get_resource_type(view)
            
            attributes = {k: v for k, v in obj.items() if k != 'id'}
            
            return {
                'type': obj_type,
                'id': str(obj_id),
                'attributes': attributes
            }
        
        return obj
    
    def get_resource_type(self, view):
        """Get resource type from view"""
        if hasattr(view, 'model') and view.model:
            return view.model._meta.model_name
        elif hasattr(view, 'serializer_class') and view.serializer_class:
            return getattr(view.serializer_class.Meta, 'model', 'unknown')._meta.model_name
        return 'resource'


class CSVRenderer(renderers.BaseRenderer):
    """
    Renderer for CSV export
    """
    media_type = 'text/csv'
    format = 'csv'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data as CSV
        """
        import csv
        import io
        
        if not data:
            return b''
        
        # Get data list
        if isinstance(data, dict) and 'results' in data:
            data_list = data['results']
        elif isinstance(data, list):
            data_list = data
        else:
            data_list = [data]
        
        if not data_list:
            return b''
        
        # Create CSV
        output = io.StringIO()
        
        # Get field names from first item
        if isinstance(data_list[0], dict):
            fieldnames = data_list[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_list)
        else:
            writer = csv.writer(output)
            for row in data_list:
                writer.writerow(row)
        
        csv_data = output.getvalue()
        output.close()
        
        return csv_data.encode('utf-8')


class ExcelRenderer(renderers.BaseRenderer):
    """
    Renderer for Excel export
    """
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'xlsx'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data as Excel file
        """
        try:
            import openpyxl
            from openpyxl.utils.dataframe import dataframe_to_rows
            import pandas as pd
            import io
        except ImportError:
            raise ImportError("openpyxl and pandas are required for Excel export")
        
        if not data:
            return b''
        
        # Get data list
        if isinstance(data, dict) and 'results' in data:
            data_list = data['results']
        elif isinstance(data, list):
            data_list = data
        else:
            data_list = [data]
        
        if not data_list:
            return b''
        
        # Create DataFrame
        df = pd.DataFrame(data_list)
        
        # Create Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        
        output.seek(0)
        return output.read()
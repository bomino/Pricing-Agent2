"""
Custom template filters for data ingestion app
"""
from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import title, lower, upper, capfirst
import json

register = template.Library()


@register.filter
def replace_underscores(value):
    """
    Replace underscores with spaces
    Usage: {{ value|replace_underscores }}
    """
    if not value:
        return value
    return str(value).replace('_', ' ')


@register.filter  
def replace(value, char):
    """
    Replace character with space
    Usage: {{ value|replace:"_" }}
    """
    if not value:
        return value
    return str(value).replace(char, ' ')


@register.filter
def title_with_underscore(value):
    """
    Convert underscore_case to Title Case
    Usage: {{ value|title_with_underscore }}
    """
    if not value:
        return value
    return str(value).replace('_', ' ').title()


@register.filter
def safe_get(dictionary, key, default=''):
    """
    Safely get a value from a dictionary with a default
    Usage: {{ mydict|safe_get:"key" }}
    """
    if not dictionary:
        return default
    if not isinstance(dictionary, dict):
        return default
    return dictionary.get(key, default)


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary in templates
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_nested(data, keys):
    """
    Get nested dictionary values
    Usage: {{ data|get_nested:"key1.key2.key3" }}
    """
    if not data:
        return None
    
    key_list = keys.split('.')
    value = data
    
    for key in key_list:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
        if value is None:
            return None
    
    return value


@register.filter
def json_dumps(value):
    """
    Convert Python object to JSON string
    """
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return '{}'


@register.filter
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ value|percentage:total }}
    """
    try:
        if total == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def multiply(value, arg):
    """
    Multiply values
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def intcomma(value):
    """
    Format number with thousands separator
    Usage: {{ value|intcomma }}
    """
    try:
        value = int(float(value))
        return f"{value:,}"
    except (TypeError, ValueError):
        return value


@register.filter
def currency_format(value, currency='USD'):
    """
    Format value as currency
    Usage: {{ value|currency_format:"USD" }}
    """
    try:
        value = float(value)
        if currency == 'USD':
            return f"${value:,.2f}"
        elif currency == 'EUR':
            return f"€{value:,.2f}"
        elif currency == 'GBP':
            return f"£{value:,.2f}"
        elif currency == 'JPY':
            return f"¥{value:,.0f}"
        else:
            return f"{currency} {value:,.2f}"
    except (TypeError, ValueError):
        return f"{currency} 0.00"


@register.filter
def status_badge(status):
    """
    Return CSS classes for status badges
    Usage: {{ status|status_badge }}
    """
    status_classes = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'processing': 'bg-blue-100 text-blue-800',
        'validating': 'bg-purple-100 text-purple-800',
        'mapping': 'bg-indigo-100 text-indigo-800',
        'completed': 'bg-green-100 text-green-800',
        'failed': 'bg-red-100 text-red-800',
        'partial': 'bg-orange-100 text-orange-800',
        'valid': 'bg-green-100 text-green-800',
        'invalid': 'bg-red-100 text-red-800',
    }
    return status_classes.get(status, 'bg-gray-100 text-gray-800')


@register.filter
def truncate_middle(value, length=50):
    """
    Truncate string in the middle
    Usage: {{ long_string|truncate_middle:50 }}
    """
    value = str(value)
    if len(value) <= length:
        return value
    
    half = (length - 3) // 2
    return f"{value[:half]}...{value[-half:]}"


@register.simple_tag
def get_field_value(row_data, field_name):
    """
    Get field value from row data
    Usage: {% get_field_value row_data "field_name" %}
    """
    if isinstance(row_data, dict):
        return row_data.get(field_name, '')
    return ''


@register.inclusion_tag('data_ingestion/partials/progress_bar.html')
def progress_bar(current, total, color='blue'):
    """
    Render a progress bar
    Usage: {% progress_bar current total "green" %}
    """
    if total == 0:
        percentage = 0
    else:
        percentage = round((current / total) * 100, 1)
    
    return {
        'current': current,
        'total': total,
        'percentage': percentage,
        'color': color
    }
"""
Clean up test data from previous runs
"""
import os
import sys
import django

# Add Django app to path
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from apps.procurement.models import PurchaseOrder, PurchaseOrderLine
from apps.pricing.models import Price

# Clean up test POs
test_pos = PurchaseOrder.objects.filter(po_number__startswith='PO-2024-')
po_count = test_pos.count()
if po_count > 0:
    print(f'Deleting {po_count} test POs')
    test_pos.delete()
else:
    print('No test POs to delete')

# Check current state
print(f'\nCurrent Database State:')
print(f'  - POs: {PurchaseOrder.objects.count()}')
print(f'  - Prices: {Price.objects.count()}')

print('\nReady for fresh test run!')
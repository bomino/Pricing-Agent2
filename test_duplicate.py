#!/usr/bin/env python
"""
Test RFQ duplication functionality
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from apps.procurement.models import RFQ, Supplier
from apps.core.models import Organization
from django.contrib.auth import get_user_model

User = get_user_model()

def test_rfq_duplication():
    print("\n" + "="*60)
    print("TESTING RFQ DUPLICATION FUNCTIONALITY")
    print("="*60 + "\n")

    user = User.objects.get(username='bomino')
    org = Organization.objects.get(code='VSTX001')

    # Get an RFQ to duplicate
    original_rfq = RFQ.objects.filter(organization=org, priority='urgent').first()
    if original_rfq:
        print(f"[INFO] Duplicating RFQ: {original_rfq.rfq_number}")
        print(f"  Original Title: {original_rfq.title}")

        # Create duplicate
        duplicated_rfq = RFQ.objects.create(
            organization=org,
            title=f'Copy of {original_rfq.title}',
            rfq_number=f'{original_rfq.rfq_number}-DUP',
            description=original_rfq.description,
            department=original_rfq.department,
            cost_center=original_rfq.cost_center,
            deadline=original_rfq.deadline,
            required_delivery_date=original_rfq.required_delivery_date,
            payment_terms=original_rfq.payment_terms,
            delivery_terms=original_rfq.delivery_terms,
            priority=original_rfq.priority,
            status='draft',
            evaluation_criteria=original_rfq.evaluation_criteria,
            terms_and_conditions=original_rfq.terms_and_conditions,
            public_rfq=original_rfq.public_rfq,
            created_by=user
        )

        # Copy suppliers
        try:
            duplicated_rfq.suppliers.set(original_rfq.suppliers.all())
            suppliers_count = duplicated_rfq.suppliers.count()
            print(f"  [OK] Copied {suppliers_count} suppliers")
        except Exception as e:
            print(f"  [WARNING] Could not copy suppliers: {e}")

        print(f"\n[SUCCESS] Created duplicate RFQ:")
        print(f"  New RFQ Number: {duplicated_rfq.rfq_number}")
        print(f"  Title: {duplicated_rfq.title}")
        print(f"  Status: {duplicated_rfq.status} (set to draft)")
        print(f"  Priority: {duplicated_rfq.priority}")
        print(f"  Access at: http://localhost:8000/procurement/rfqs/{duplicated_rfq.id}/")
    else:
        print("[ERROR] No urgent RFQ found to duplicate")

    # Show summary
    print("\n" + "="*60)
    print("DUPLICATION TEST COMPLETE")
    print("="*60)
    total_rfqs = RFQ.objects.filter(organization=org).count()
    print(f"Total RFQs in system: {total_rfqs}")

if __name__ == '__main__':
    test_rfq_duplication()
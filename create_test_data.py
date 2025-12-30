#!/usr/bin/env python
"""
Create realistic test data for procurement module
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

# Setup Django environment
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from django.contrib.auth import get_user_model
from apps.procurement.models import RFQ, Supplier
from apps.core.models import Organization

User = get_user_model()

def create_test_data():
    print("\nCreating test data for manual testing...")
    print("="*60)

    # Get user
    user = User.objects.get(username='bomino')
    print(f"[OK] Using user: {user.username}")

    # Get or create organization
    org, created = Organization.objects.get_or_create(
        code='VSTX001',
        defaults={
            'name': 'VSTX Manufacturing Corp',
            'type': 'buyer',
            'description': 'Leading manufacturer of industrial components',
            'email': 'procurement@vstx.com',
            'phone': '+1-555-123-4567',
            'address': {
                'street': '123 Industrial Park',
                'city': 'Houston',
                'state': 'TX',
                'zip': '77001',
                'country': 'USA'
            }
        }
    )
    print(f"[OK] Organization: {org.name} ({'created' if created else 'existing'})")

    # Ensure user has organization
    if hasattr(user, 'profile'):
        user.profile.organization = org
        user.profile.save()

    # Create suppliers
    print("\nCreating Suppliers...")
    suppliers_data = [
        {
            'name': 'ArcelorMittal Steel Solutions',
            'code': 'AMST001',
            'supplier_type': 'manufacturer',
            'address': '1 S Dearborn St, Chicago, IL 60603',
            'tax_id': '52-2142789',
            'payment_terms': 'NET30',
            'rating': Decimal('4.5'),
            'notes': 'Primary steel supplier for structural components'
        },
        {
            'name': 'Nucor Corporation',
            'code': 'NUC002',
            'supplier_type': 'manufacturer',
            'address': '1915 Rexford Rd, Charlotte, NC 28211',
            'tax_id': '13-1860817',
            'payment_terms': 'NET45',
            'rating': Decimal('4.7'),
            'notes': 'Specialized in rebar and sheet metal'
        },
        {
            'name': 'Fastenal Company',
            'code': 'FAST003',
            'supplier_type': 'distributor',
            'address': '2001 Theurer Blvd, Winona, MN 55987',
            'tax_id': '41-0948415',
            'payment_terms': 'NET15',
            'rating': Decimal('4.3'),
            'notes': 'Industrial supplies and fasteners distributor'
        }
    ]

    created_suppliers = []
    for data in suppliers_data:
        supplier, created = Supplier.objects.get_or_create(
            organization=org,
            code=data['code'],
            defaults=data
        )
        created_suppliers.append(supplier)
        print(f"  - {supplier.name} ({'created' if created else 'exists'})")

    # Create RFQs
    print("\nCreating RFQs...")
    rfqs_data = [
        {
            'title': 'Q1 2025 Steel Beam Procurement',
            'rfq_number': 'RFQ-2025-001',
            'description': 'Request for quotation for structural steel beams for Q1 2025 construction projects.\n\n'
                         'Requirements:\n'
                         '- W-shape beams: W12x26, W14x30, W16x36\n'
                         '- Length: 20-40 feet\n'
                         '- Grade: ASTM A992/A572-50\n'
                         '- Quantity: 500 tons total\n'
                         '- Delivery: Staggered delivery over Q1 2025',
            'department': 'Procurement',
            'cost_center': 'CC-CONST-001',
            'deadline': timezone.now() + timedelta(days=14),
            'required_delivery_date': (timezone.now() + timedelta(days=60)).date(),
            'payment_terms': 'NET30',
            'delivery_terms': 'FOB Destination',
            'priority': 'high',
            'status': 'published',
            'evaluation_criteria': {'price': 40, 'quality': 30, 'delivery': 20, 'service': 10},
            'terms_and_conditions': 'Standard VSTX procurement terms apply.',
            'public_rfq': False
        },
        {
            'title': 'Industrial Fasteners Annual Contract 2025',
            'rfq_number': 'RFQ-2025-002',
            'description': 'Annual contract for industrial fasteners and hardware supplies.\n\n'
                         'Product Categories:\n'
                         '- Hex bolts (various sizes)\n'
                         '- Socket screws\n'
                         '- Washers and nuts\n'
                         '- Anchoring systems\n'
                         '- Stainless steel fasteners\n\n'
                         'Estimated Annual Volume: $2.5M',
            'department': 'Operations',
            'cost_center': 'CC-OPS-002',
            'deadline': timezone.now() + timedelta(days=21),
            'required_delivery_date': (timezone.now() + timedelta(days=30)).date(),
            'payment_terms': 'NET45',
            'delivery_terms': 'DDP',
            'priority': 'medium',
            'status': 'published',
            'evaluation_criteria': {'price': 35, 'availability': 25, 'quality': 25, 'service': 15},
            'terms_and_conditions': 'Annual contract terms. Volume discounts required.',
            'public_rfq': True
        },
        {
            'title': 'Emergency Rebar Supply - Project Phoenix',
            'rfq_number': 'RFQ-2025-003',
            'description': 'URGENT: Rebar supply needed for Project Phoenix foundation work.\n\n'
                         'Specifications:\n'
                         '- #4 (1/2") rebar: 100 tons\n'
                         '- #5 (5/8") rebar: 150 tons\n'
                         '- #6 (3/4") rebar: 75 tons\n'
                         '- Grade 60 (420 MPa)',
            'department': 'Project Management',
            'cost_center': 'CC-PROJ-PHX',
            'deadline': timezone.now() + timedelta(days=3),
            'required_delivery_date': (timezone.now() + timedelta(days=7)).date(),
            'payment_terms': 'Immediate',
            'delivery_terms': 'FOB Origin',
            'priority': 'urgent',
            'status': 'published',
            'evaluation_criteria': {'availability': 50, 'price': 30, 'quality': 20},
            'terms_and_conditions': 'Expedited terms. Premium accepted for quick delivery.',
            'public_rfq': False
        }
    ]

    for data in rfqs_data:
        try:
            rfq, created = RFQ.objects.get_or_create(
                organization=org,
                rfq_number=data['rfq_number'],
                defaults={**data, 'created_by': user}
            )

            # Add suppliers
            if created:
                rfq.suppliers.set(created_suppliers[:2])  # Add first 2 suppliers
                rfq.invited_suppliers.set(created_suppliers[:2])

            print(f"  - {rfq.title[:50]}... ({'created' if created else 'exists'})")
        except Exception as e:
            print(f"  - Error creating RFQ: {e}")

    print("\n" + "="*60)
    print("TEST DATA CREATION COMPLETE!")
    print("="*60)
    print(f"""
You can now test with:
- Login: bomino / admin123
- Organization: VSTX Manufacturing Corp
- {len(created_suppliers)} Suppliers created
- 3 RFQs with different priorities

Access the application at:
http://localhost:8000/procurement/rfqs/
    """)

if __name__ == '__main__':
    create_test_data()
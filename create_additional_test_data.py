#!/usr/bin/env python
"""
Create additional comprehensive test data for end-to-end testing
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
from apps.procurement.models import RFQ, Supplier, Quote, QuoteItem, PurchaseOrder
from apps.core.models import Organization
from apps.pricing.models import Material

User = get_user_model()

def create_additional_test_data():
    print("\nCreating ADDITIONAL test data for comprehensive testing...")
    print("="*60)

    # Get user and organization
    user = User.objects.get(username='bomino')
    org = Organization.objects.get(code='VSTX001')
    print(f"[OK] Using user: {user.username}")
    print(f"[OK] Organization: {org.name}")

    # Create additional suppliers
    print("\n[STEP 1] Creating Additional Suppliers...")
    additional_suppliers = [
        {
            'name': 'United States Steel Corporation',
            'code': 'USS004',
            'supplier_type': 'manufacturer',
            'address': '600 Grant Street, Pittsburgh, PA 15219',
            'tax_id': '25-1843007',
            'payment_terms': 'NET60',
            'rating': Decimal('4.6'),
            'notes': 'Premium steel products, longer lead times'
        },
        {
            'name': 'Grainger Industrial Supply',
            'code': 'GRG005',
            'supplier_type': 'distributor',
            'address': '100 Grainger Parkway, Lake Forest, IL 60045',
            'tax_id': '36-1150280',
            'payment_terms': 'NET30',
            'rating': Decimal('4.8'),
            'notes': 'MRO supplies and industrial equipment'
        },
        {
            'name': 'McMaster-Carr Supply Company',
            'code': 'MCM006',
            'supplier_type': 'distributor',
            'address': '9630 Norwalk Blvd, Santa Fe Springs, CA 90670',
            'tax_id': '07-0418550',
            'payment_terms': 'NET15',
            'rating': Decimal('4.9'),
            'notes': 'Technical parts and materials, same-day shipping'
        },
        {
            'name': 'Cleveland-Cliffs Inc.',
            'code': 'CLF007',
            'supplier_type': 'manufacturer',
            'address': '200 Public Square, Cleveland, OH 44114',
            'tax_id': '34-1464672',
            'payment_terms': 'NET45',
            'rating': Decimal('4.4'),
            'notes': 'Iron ore and steel production'
        },
        {
            'name': 'HD Supply',
            'code': 'HDS008',
            'supplier_type': 'distributor',
            'address': '3100 Cumberland Blvd, Atlanta, GA 30339',
            'tax_id': '26-0486780',
            'payment_terms': 'NET30',
            'rating': Decimal('4.2'),
            'notes': 'Construction and industrial supplies'
        }
    ]

    created_suppliers = []
    for data in additional_suppliers:
        supplier, created = Supplier.objects.get_or_create(
            organization=org,
            code=data['code'],
            defaults=data
        )
        created_suppliers.append(supplier)
        status = "[CREATED]" if created else "[EXISTS]"
        print(f"  {status} {supplier.name}")

    # Create additional RFQs with various statuses
    print("\n[STEP 2] Creating Additional RFQs...")
    additional_rfqs = [
        {
            'title': 'Warehouse Safety Equipment Q1 2025',
            'rfq_number': 'RFQ-2025-004',
            'description': 'Comprehensive safety equipment procurement for all warehouse facilities.\n\n'
                         'Required Items:\n'
                         '- Hard hats (200 units)\n'
                         '- Safety glasses (500 units)\n'
                         '- High-visibility vests (300 units)\n'
                         '- Steel-toe boots (various sizes)\n'
                         '- First aid kits (50 units)\n'
                         '- Fire extinguishers (30 units)',
            'department': 'Safety & Compliance',
            'cost_center': 'CC-SAFE-001',
            'deadline': timezone.now() + timedelta(days=10),
            'required_delivery_date': (timezone.now() + timedelta(days=30)).date(),
            'payment_terms': 'NET30',
            'delivery_terms': 'DDP',
            'priority': 'high',
            'status': 'published',
            'evaluation_criteria': {'price': 35, 'quality': 35, 'delivery': 20, 'certification': 10},
            'terms_and_conditions': 'All items must meet OSHA standards.',
            'public_rfq': True
        },
        {
            'title': 'Hydraulic Equipment Maintenance Parts',
            'rfq_number': 'RFQ-2025-005',
            'description': 'Replacement parts for hydraulic systems maintenance.\n\n'
                         'Parts Required:\n'
                         '- Hydraulic pumps (10 units)\n'
                         '- Hydraulic cylinders (20 units)\n'
                         '- Hoses and fittings (various)\n'
                         '- Hydraulic fluid (1000 gallons)\n'
                         '- Filter elements (100 units)',
            'department': 'Maintenance',
            'cost_center': 'CC-MAINT-002',
            'deadline': timezone.now() + timedelta(days=7),
            'required_delivery_date': (timezone.now() + timedelta(days=14)).date(),
            'payment_terms': 'NET15',
            'delivery_terms': 'FOB Origin',
            'priority': 'urgent',
            'status': 'published',
            'evaluation_criteria': {'availability': 45, 'price': 30, 'quality': 25},
            'terms_and_conditions': 'OEM parts preferred. Expedited shipping required.',
            'public_rfq': False
        },
        {
            'title': 'Office Renovation Materials',
            'rfq_number': 'RFQ-2025-006',
            'description': 'Materials for corporate office renovation project.\n\n'
                         'Materials Needed:\n'
                         '- Drywall sheets (500 units)\n'
                         '- Paint (200 gallons)\n'
                         '- Ceiling tiles (1000 sq ft)\n'
                         '- LED lighting fixtures (150 units)\n'
                         '- Flooring materials (5000 sq ft)',
            'department': 'Facilities',
            'cost_center': 'CC-FAC-003',
            'deadline': timezone.now() + timedelta(days=30),
            'required_delivery_date': (timezone.now() + timedelta(days=45)).date(),
            'payment_terms': 'NET45',
            'delivery_terms': 'DDP',
            'priority': 'low',
            'status': 'draft',
            'evaluation_criteria': {'price': 40, 'quality': 30, 'aesthetics': 20, 'warranty': 10},
            'terms_and_conditions': 'Eco-friendly materials preferred.',
            'public_rfq': False
        },
        {
            'title': 'Annual Welding Supplies Contract',
            'rfq_number': 'RFQ-2025-007',
            'description': 'Annual contract for welding consumables and equipment.\n\n'
                         'Annual Requirements:\n'
                         '- Welding rods (various types)\n'
                         '- Welding wire (MIG/TIG)\n'
                         '- Shielding gas cylinders\n'
                         '- Welding helmets and PPE\n'
                         '- Cutting torches and tips\n\n'
                         'Estimated annual spend: $1.8M',
            'department': 'Operations',
            'cost_center': 'CC-OPS-004',
            'deadline': timezone.now() + timedelta(days=25),
            'required_delivery_date': (timezone.now() + timedelta(days=60)).date(),
            'payment_terms': 'NET30',
            'delivery_terms': 'FOB Destination',
            'priority': 'medium',
            'status': 'published',
            'evaluation_criteria': {'price': 30, 'quality': 30, 'service': 25, 'inventory': 15},
            'terms_and_conditions': 'Vendor managed inventory preferred.',
            'public_rfq': True
        },
        {
            'title': 'Emergency Generator Replacement',
            'rfq_number': 'RFQ-2025-008',
            'description': 'URGENT: Backup generator replacement for critical facility.\n\n'
                         'Specifications:\n'
                         '- 500kW diesel generator\n'
                         '- Automatic transfer switch\n'
                         '- Sound attenuated enclosure\n'
                         '- Installation and commissioning\n'
                         '- 5-year maintenance contract',
            'department': 'Engineering',
            'cost_center': 'CC-ENG-001',
            'deadline': timezone.now() + timedelta(days=5),
            'required_delivery_date': (timezone.now() + timedelta(days=21)).date(),
            'payment_terms': 'NET30',
            'delivery_terms': 'DDP',
            'priority': 'urgent',
            'status': 'published',
            'evaluation_criteria': {'availability': 40, 'reliability': 30, 'price': 20, 'warranty': 10},
            'terms_and_conditions': 'Turn-key solution required. 24/7 support mandatory.',
            'public_rfq': False
        }
    ]

    rfqs_created = []
    for data in additional_rfqs:
        try:
            rfq, created = RFQ.objects.get_or_create(
                organization=org,
                rfq_number=data['rfq_number'],
                defaults={**data, 'created_by': user}
            )

            if created:
                # Assign suppliers based on RFQ type
                try:
                    if 'safety' in data['title'].lower():
                        suppliers_to_add = Supplier.objects.filter(organization=org, code__in=['GRG005', 'HDS008'])
                        if suppliers_to_add.exists():
                            rfq.suppliers.add(*suppliers_to_add)
                    elif 'hydraulic' in data['title'].lower():
                        suppliers_to_add = Supplier.objects.filter(organization=org, code__in=['MCM006', 'GRG005'])
                        if suppliers_to_add.exists():
                            rfq.suppliers.add(*suppliers_to_add)
                    elif 'welding' in data['title'].lower():
                        suppliers_to_add = Supplier.objects.filter(organization=org, code__in=['FAST003', 'GRG005', 'MCM006'])
                        if suppliers_to_add.exists():
                            rfq.suppliers.add(*suppliers_to_add)
                    elif 'steel' in data['title'].lower() or 'rebar' in data['title'].lower():
                        suppliers_to_add = Supplier.objects.filter(organization=org, code__in=['AMST001', 'NUC002', 'USS004'])
                        if suppliers_to_add.exists():
                            rfq.suppliers.add(*suppliers_to_add)
                    else:
                        # Add random suppliers
                        if created_suppliers[:2]:
                            rfq.suppliers.add(*created_suppliers[:2])
                except Exception as e:
                    print(f"    [WARNING] Could not add suppliers to RFQ: {e}")

            status = "[CREATED]" if created else "[EXISTS]"
            print(f"  {status}: {rfq.title[:50]}... (Priority: {rfq.priority.upper()})")
            rfqs_created.append(rfq)

        except Exception as e:
            print(f"  [ERROR] creating RFQ {data['rfq_number']}: {e}")

    # Create some test quotes
    print("\n[STEP 3] Creating Sample Quotes...")
    rfq_for_quote = RFQ.objects.filter(
        organization=org,
        status='published'
    ).first()

    if rfq_for_quote:
        try:
            if rfq_for_quote.suppliers.exists():
                supplier_for_quote = rfq_for_quote.suppliers.first()
            else:
                supplier_for_quote = Supplier.objects.filter(organization=org).first()
        except Exception as e:
            print(f"  [WARNING] Could not check suppliers: {e}")
            supplier_for_quote = Supplier.objects.filter(organization=org).first()

        if supplier_for_quote:
            try:
                quote, created = Quote.objects.get_or_create(
                    rfq=rfq_for_quote,
                    supplier=supplier_for_quote,
                    organization=org,
                    quote_number=f'QT-{rfq_for_quote.rfq_number}-{supplier_for_quote.code}',
                    defaults={
                        'expires_at': timezone.now() + timedelta(days=30),
                        'currency': 'USD',
                        'payment_terms': supplier_for_quote.payment_terms,
                        'delivery_terms': rfq_for_quote.delivery_terms,
                        'supplier_notes': 'Competitive pricing with volume discounts available.',
                        'status': 'submitted',
                        'submitted_at': timezone.now(),
                        'total_amount': Decimal('70350.00'),
                        'validity_period': 30,
                        'lead_time_days': 14
                    }
                )

                if created:
                    # Add sample quote items
                    for i in range(3):
                        QuoteItem.objects.create(
                            quote=quote,
                            specifications=f'Item {i+1} for {rfq_for_quote.title[:30]}',
                            quantity=100 * (i+1),
                            unit_price=Decimal(str(50.00 + (i * 25))),
                            price=Decimal(str((100 * (i+1)) * (50.00 + (i * 25)))),
                            unit_of_measure='unit',
                            currency='USD',
                            lead_time_days=14
                        )
                    print(f"  [CREATED] Quote: {quote.quote_number}")
                else:
                    print(f"  [EXISTS] Quote: {quote.quote_number}")

            except Exception as e:
                print(f"  [ERROR] creating quote: {e}")

    # Summary statistics
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST DATA SUMMARY")
    print("="*60)

    total_suppliers = Supplier.objects.filter(organization=org).count()
    total_rfqs = RFQ.objects.filter(organization=org).count()
    total_quotes = Quote.objects.filter(organization=org).count()

    print(f"""
Database Statistics:
- Total Suppliers: {total_suppliers}
- Total RFQs: {total_rfqs}
  • Draft: {RFQ.objects.filter(organization=org, status='draft').count()}
  • Published: {RFQ.objects.filter(organization=org, status='published').count()}
  • Closed: {RFQ.objects.filter(organization=org, status='closed').count()}
- Total Quotes: {total_quotes}

Priority Distribution:
- Urgent: {RFQ.objects.filter(organization=org, priority='urgent').count()} RFQs
- High: {RFQ.objects.filter(organization=org, priority='high').count()} RFQs
- Medium: {RFQ.objects.filter(organization=org, priority='medium').count()} RFQs
- Low: {RFQ.objects.filter(organization=org, priority='low').count()} RFQs

Ready for Testing at:
http://localhost:8000/procurement/rfqs/
    """)

if __name__ == '__main__':
    create_additional_test_data()
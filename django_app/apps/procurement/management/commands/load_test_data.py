from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.procurement.models import RFQ, Supplier
from apps.core.models import Organization
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Load test data for procurement module'

    def handle(self, *args, **options):
        self.stdout.write("\nLoading test data for procurement module...")
        self.stdout.write("="*60)

        # Get or create user
        user, created = User.objects.get_or_create(
            username='bomino',
            defaults={
                'email': 'bomino@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'[CREATED] User: {user.username}'))
        else:
            self.stdout.write(f'[EXISTS] User: {user.username}')

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
        if created:
            self.stdout.write(self.style.SUCCESS(f'[CREATED] Organization: {org.name}'))
        else:
            self.stdout.write(f'[EXISTS] Organization: {org.name}')

        # Ensure user has organization
        if hasattr(user, 'profile'):
            user.profile.organization = org
            user.profile.save()

        # Create suppliers
        self.stdout.write("\nCreating Suppliers...")
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
            },
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
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [CREATED] {supplier.name}'))
            else:
                self.stdout.write(f'  [EXISTS] {supplier.name}')

        # Create RFQs
        self.stdout.write("\nCreating RFQs...")
        rfqs_data = [
            {
                'title': 'Q1 2025 Steel Beam Procurement',
                'rfq_number': 'RFQ-2025-001',
                'description': 'Request for quotation for structural steel beams for Q1 2025 construction projects.',
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
                'description': 'Annual contract for industrial fasteners and hardware supplies.',
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
                'description': 'URGENT: Rebar supply needed for Project Phoenix foundation work.',
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
            },
            {
                'title': 'Warehouse Safety Equipment Q1 2025',
                'rfq_number': 'RFQ-2025-004',
                'description': 'Comprehensive safety equipment procurement for all warehouse facilities.',
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
                'description': 'Replacement parts for hydraulic systems maintenance.',
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
                    rfq.suppliers.set(created_suppliers[:3])  # Add first 3 suppliers
                    rfq.invited_suppliers.set(created_suppliers[:3])
                    self.stdout.write(self.style.SUCCESS(f'  [CREATED] {rfq.title[:50]}...'))
                else:
                    self.stdout.write(f'  [EXISTS] {rfq.title[:50]}...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [ERROR] creating RFQ: {e}'))

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("TEST DATA LOADED SUCCESSFULLY!"))
        self.stdout.write("="*60)

        total_suppliers = Supplier.objects.filter(organization=org).count()
        total_rfqs = RFQ.objects.filter(organization=org).count()

        self.stdout.write(f"""
Database Statistics:
- Total Suppliers: {total_suppliers}
- Total RFQs: {total_rfqs}

You can now test with:
- Login: bomino / admin123
- Organization: VSTX Manufacturing Corp

Access the application at:
http://localhost:8000/procurement/rfqs/
        """)
#!/usr/bin/env python
"""
End-to-End Testing Script for Procurement Module
Tests all functionality with realistic manufacturing/construction data
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Setup Django environment
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from django.contrib.auth import get_user_model
from apps.procurement.models import RFQ, Supplier, Quote, QuoteItem, PurchaseOrder, Contract
from apps.accounts.models import Organization

User = get_user_model()

class ProcurementE2ETest:
    """End-to-end testing with realistic data"""

    def __init__(self):
        self.test_results = []
        self.user = None
        self.org = None

    def log_result(self, test_name, status, details=""):
        """Log test results"""
        result = f"{'[PASS]' if status else '[FAIL]'} {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append((test_name, status, details))

    def test_1_login_setup(self):
        """Test 1: Setup user and organization"""
        try:
            # Get or create test user
            self.user, created = User.objects.get_or_create(
                username='bomino',
                defaults={
                    'email': 'bomino@example.com',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'is_active': True,
                    'is_staff': True
                }
            )

            if created:
                self.user.set_password('admin123')
                self.user.save()

            # Get or create organization
            self.org, _ = Organization.objects.get_or_create(
                name='VSTX Manufacturing Corp',
                defaults={
                    'code': 'VSTX001',
                    'description': 'Leading manufacturer of industrial components',
                    'industry': 'Manufacturing',
                    'address': '123 Industrial Park, Houston, TX 77001',
                    'contact_email': 'procurement@vstx.com',
                    'contact_phone': '+1-555-123-4567'
                }
            )

            # Link user to organization
            self.user.profile.organization = self.org
            self.user.profile.save()

            self.log_result("User & Organization Setup", True,
                           f"User: {self.user.username}, Org: {self.org.name}")
            return True

        except Exception as e:
            self.log_result("User & Organization Setup", False, str(e))
            return False

    def test_2_create_suppliers(self):
        """Test 2: Create realistic suppliers"""
        try:
            suppliers_data = [
                {
                    'name': 'ArcelorMittal Steel Solutions',
                    'code': 'AMST001',
                    'contact_person': 'John Richardson',
                    'email': 'j.richardson@arcelormittal.com',
                    'phone': '+1-312-899-3000',
                    'address': '1 S Dearborn St, Chicago, IL 60603',
                    'tax_id': '52-2142789',
                    'payment_terms': 'NET30',
                    'rating': Decimal('4.5'),
                    'category': 'Raw Materials',
                    'notes': 'Primary steel supplier for structural components'
                },
                {
                    'name': 'Nucor Corporation',
                    'code': 'NUC002',
                    'contact_person': 'Sarah Chen',
                    'email': 's.chen@nucor.com',
                    'phone': '+1-704-366-7000',
                    'address': '1915 Rexford Rd, Charlotte, NC 28211',
                    'tax_id': '13-1860817',
                    'payment_terms': 'NET45',
                    'rating': Decimal('4.7'),
                    'category': 'Raw Materials',
                    'notes': 'Specialized in rebar and sheet metal'
                },
                {
                    'name': 'Fastenal Company',
                    'code': 'FAST003',
                    'contact_person': 'Michael Brown',
                    'email': 'm.brown@fastenal.com',
                    'phone': '+1-507-454-5374',
                    'address': '2001 Theurer Blvd, Winona, MN 55987',
                    'tax_id': '41-0948415',
                    'payment_terms': 'NET15',
                    'rating': Decimal('4.3'),
                    'category': 'Fasteners & Hardware',
                    'notes': 'Industrial supplies and fasteners distributor'
                }
            ]

            created_suppliers = []
            for supplier_data in suppliers_data:
                supplier, created = Supplier.objects.get_or_create(
                    organization=self.org,
                    code=supplier_data['code'],
                    defaults=supplier_data
                )
                created_suppliers.append(supplier)

            self.log_result("Supplier Creation", True,
                           f"Created {len(created_suppliers)} suppliers")
            return created_suppliers

        except Exception as e:
            self.log_result("Supplier Creation", False, str(e))
            return []

    def test_3_create_rfqs(self):
        """Test 3: Create realistic RFQs"""
        try:
            suppliers = Supplier.objects.filter(organization=self.org)

            rfqs_data = [
                {
                    'title': 'Q1 2025 Steel Beam Procurement',
                    'rfq_number': 'RFQ-2025-001',
                    'description': """
                    Request for quotation for structural steel beams for Q1 2025 construction projects.

                    Requirements:
                    - W-shape beams: W12x26, W14x30, W16x36
                    - Length: 20-40 feet
                    - Grade: ASTM A992/A572-50
                    - Quantity: 500 tons total
                    - Delivery: Staggered delivery over Q1 2025
                    - Location: Houston, TX construction sites

                    Quality Requirements:
                    - Mill test certificates required
                    - AISC certification preferred
                    - Compliance with ASTM standards
                    """,
                    'department': 'Procurement',
                    'cost_center': 'CC-CONST-001',
                    'deadline': datetime.now() + timedelta(days=14, hours=17),
                    'required_delivery_date': datetime.now().date() + timedelta(days=60),
                    'payment_terms': 'NET30',
                    'delivery_terms': 'FOB Destination',
                    'priority': 'high',
                    'status': 'open',
                    'evaluation_criteria': 'Price: 40%, Quality: 30%, Delivery: 20%, Service: 10%',
                    'terms_and_conditions': 'Standard VSTX procurement terms apply. See attached T&C document.',
                    'public_rfq': False
                },
                {
                    'title': 'Industrial Fasteners Annual Contract 2025',
                    'rfq_number': 'RFQ-2025-002',
                    'description': """
                    Annual contract for industrial fasteners and hardware supplies.

                    Product Categories:
                    - Hex bolts (various sizes)
                    - Socket screws
                    - Washers and nuts
                    - Anchoring systems
                    - Stainless steel fasteners

                    Estimated Annual Volume: $2.5M
                    Delivery: As-needed basis with 48-hour turnaround
                    Locations: Multiple sites across Texas
                    """,
                    'department': 'Operations',
                    'cost_center': 'CC-OPS-002',
                    'deadline': datetime.now() + timedelta(days=21, hours=15),
                    'required_delivery_date': datetime.now().date() + timedelta(days=30),
                    'payment_terms': 'NET45',
                    'delivery_terms': 'DDP',
                    'priority': 'medium',
                    'status': 'open',
                    'evaluation_criteria': 'Price: 35%, Availability: 25%, Quality: 25%, Service: 15%',
                    'terms_and_conditions': 'Annual contract terms. Volume discounts required.',
                    'public_rfq': True
                },
                {
                    'title': 'Emergency Rebar Supply - Project Phoenix',
                    'rfq_number': 'RFQ-2025-003',
                    'description': """
                    URGENT: Rebar supply needed for Project Phoenix foundation work.

                    Specifications:
                    - #4 (1/2") rebar: 100 tons
                    - #5 (5/8") rebar: 150 tons
                    - #6 (3/4") rebar: 75 tons
                    - Grade 60 (420 MPa)

                    Delivery Required: Within 7 days
                    Site: Phoenix Industrial Complex, Houston
                    """,
                    'department': 'Project Management',
                    'cost_center': 'CC-PROJ-PHX',
                    'deadline': datetime.now() + timedelta(days=3, hours=12),
                    'required_delivery_date': datetime.now().date() + timedelta(days=7),
                    'payment_terms': 'Immediate',
                    'delivery_terms': 'FOB Origin',
                    'priority': 'urgent',
                    'status': 'open',
                    'evaluation_criteria': 'Availability: 50%, Price: 30%, Quality: 20%',
                    'terms_and_conditions': 'Expedited terms. Premium accepted for quick delivery.',
                    'public_rfq': False
                }
            ]

            created_rfqs = []
            for rfq_data in rfqs_data:
                rfq = RFQ.objects.create(
                    organization=self.org,
                    created_by=self.user,
                    **rfq_data
                )
                # Add suppliers to RFQ
                rfq.suppliers.set(suppliers[:2])  # Add first 2 suppliers
                created_rfqs.append(rfq)

            self.log_result("RFQ Creation", True,
                           f"Created {len(created_rfqs)} RFQs with real-world data")
            return created_rfqs

        except Exception as e:
            self.log_result("RFQ Creation", False, str(e))
            return []

    def test_4_duplicate_rfq(self):
        """Test 4: Test RFQ duplication"""
        try:
            # Get an existing RFQ
            original_rfq = RFQ.objects.filter(organization=self.org).first()

            if not original_rfq:
                self.log_result("RFQ Duplication", False, "No RFQ found to duplicate")
                return None

            # Duplicate the RFQ
            duplicated_rfq = RFQ.objects.create(
                organization=original_rfq.organization,
                title=f"Copy of {original_rfq.title}",
                rfq_number=f"{original_rfq.rfq_number}-COPY",
                description=original_rfq.description,
                department=original_rfq.department,
                cost_center=original_rfq.cost_center,
                deadline=datetime.now() + timedelta(days=14),
                required_delivery_date=original_rfq.required_delivery_date,
                payment_terms=original_rfq.payment_terms,
                delivery_terms=original_rfq.delivery_terms,
                priority=original_rfq.priority,
                status='draft',
                evaluation_criteria=original_rfq.evaluation_criteria,
                terms_and_conditions=original_rfq.terms_and_conditions,
                public_rfq=original_rfq.public_rfq,
                created_by=self.user
            )

            # Copy suppliers
            duplicated_rfq.suppliers.set(original_rfq.suppliers.all())

            self.log_result("RFQ Duplication", True,
                           f"Duplicated: {original_rfq.title} -> {duplicated_rfq.title}")
            return duplicated_rfq

        except Exception as e:
            self.log_result("RFQ Duplication", False, str(e))
            return None

    def test_5_create_quotes(self):
        """Test 5: Create quotes from suppliers"""
        try:
            rfq = RFQ.objects.filter(
                organization=self.org,
                rfq_number='RFQ-2025-001'
            ).first()

            if not rfq:
                self.log_result("Quote Creation", False, "No RFQ found")
                return []

            supplier = Supplier.objects.filter(organization=self.org).first()

            # Create a quote
            quote = Quote.objects.create(
                rfq=rfq,
                supplier=supplier,
                organization=self.org,
                quote_number='QT-2025-001-AM',
                valid_until=datetime.now().date() + timedelta(days=30),
                currency='USD',
                payment_terms='NET30',
                delivery_terms='FOB Destination',
                notes='Competitive pricing for bulk order. Volume discounts available.',
                status='submitted',
                submitted_by=self.user
            )

            # Add quote items
            items_data = [
                ('W12x26 Steel Beam', 200, Decimal('125.50'), 'ton'),
                ('W14x30 Steel Beam', 180, Decimal('132.75'), 'ton'),
                ('W16x36 Steel Beam', 120, Decimal('145.00'), 'ton'),
            ]

            for description, qty, price, unit in items_data:
                QuoteItem.objects.create(
                    quote=quote,
                    description=description,
                    quantity=qty,
                    unit_price=price,
                    unit_of_measure=unit
                )

            total_value = sum(qty * price for _, qty, price, _ in items_data)
            self.log_result("Quote Creation", True,
                           f"Created quote {quote.quote_number} - Total: ${total_value:,.2f}")
            return [quote]

        except Exception as e:
            self.log_result("Quote Creation", False, str(e))
            return []

    def test_6_data_verification(self):
        """Test 6: Verify all data persisted correctly"""
        try:
            # Count records
            counts = {
                'Organizations': Organization.objects.count(),
                'Suppliers': Supplier.objects.filter(organization=self.org).count(),
                'RFQs': RFQ.objects.filter(organization=self.org).count(),
                'Quotes': Quote.objects.filter(organization=self.org).count(),
                'Quote Items': QuoteItem.objects.filter(
                    quote__organization=self.org
                ).count(),
            }

            for model, count in counts.items():
                self.log_result(f"Data Verification - {model}", count > 0,
                               f"Count: {count}")

            return all(count > 0 for count in counts.values())

        except Exception as e:
            self.log_result("Data Verification", False, str(e))
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("PROCUREMENT MODULE END-TO-END TESTING")
        print("="*60 + "\n")

        # Run tests
        self.test_1_login_setup()
        suppliers = self.test_2_create_suppliers()
        rfqs = self.test_3_create_rfqs()
        duplicated = self.test_4_duplicate_rfq()
        quotes = self.test_5_create_quotes()
        verified = self.test_6_data_verification()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for _, status, _ in self.test_results if status)
        total = len(self.test_results)

        print(f"\nTests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")

        if passed == total:
            print("\n*** All tests passed successfully! ***")
        else:
            print("\n*** WARNING: Some tests failed. Review the results above. ***")

        # Display sample data for manual verification
        print("\n" + "="*60)
        print("SAMPLE DATA CREATED FOR MANUAL TESTING")
        print("="*60)
        print(f"""
Login Credentials:
- Username: bomino
- Password: admin123

Organization: VSTX Manufacturing Corp

Sample RFQs Created:
1. Q1 2025 Steel Beam Procurement (High Priority)
2. Industrial Fasteners Annual Contract 2025 (Medium Priority)
3. Emergency Rebar Supply - Project Phoenix (Urgent)

Sample Suppliers:
1. ArcelorMittal Steel Solutions
2. Nucor Corporation
3. Fastenal Company

Sample Quote:
- Quote #: QT-2025-001-AM
- Total Value: ~$70,000
        """)

        return passed == total


if __name__ == '__main__':
    tester = ProcurementE2ETest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
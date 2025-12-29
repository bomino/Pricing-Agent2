"""
Management command to load sample data for development and testing
"""
import random
from decimal import Decimal
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from faker import Faker

from apps.core.models import Organization
from apps.accounts.models import UserProfile
from apps.procurement.models import Supplier, RFQ, Quote, RFQItem, QuoteItem, Contract
from apps.pricing.models import Category, Material, Price, PriceAlert, PriceBenchmark

fake = Faker()


class Command(BaseCommand):
    help = 'Loads sample data for development and testing'

    def handle(self, *args, **kwargs):
        self.stdout.write('Loading sample data...')
        
        # Create organizations
        orgs = self.create_organizations()
        self.stdout.write(self.style.SUCCESS(f'Created {len(orgs)} organizations'))
        
        # Create users
        users = self.create_users(orgs[0])
        self.stdout.write(self.style.SUCCESS(f'Created {len(users)} users'))
        
        # Create categories
        categories = self.create_categories(orgs[0])
        self.stdout.write(self.style.SUCCESS(f'Created {len(categories)} categories'))
        
        # Create suppliers
        suppliers = self.create_suppliers(orgs[0])
        self.stdout.write(self.style.SUCCESS(f'Created {len(suppliers)} suppliers'))
        
        # Create materials
        materials = self.create_materials(orgs[0], categories)
        self.stdout.write(self.style.SUCCESS(f'Created {len(materials)} materials'))
        
        # Create price history
        self.create_price_history(orgs[0], materials, suppliers)
        self.stdout.write(self.style.SUCCESS('Created price history'))
        
        # Create RFQs and Quotes
        rfqs = self.create_rfqs(orgs[0], users[0], materials, suppliers)
        self.stdout.write(self.style.SUCCESS(f'Created {len(rfqs)} RFQs with quotes'))
        
        # Create price alerts
        alerts = self.create_price_alerts(orgs[0], materials, users[0])
        self.stdout.write(self.style.SUCCESS(f'Created {len(alerts)} price alerts'))
        
        self.stdout.write(self.style.SUCCESS('Sample data loaded successfully!'))

    def create_organizations(self):
        """Create sample organizations"""
        orgs = []
        
        org_data = [
            {
                'name': 'ACME Construction Corp',
                'code': 'ACME',
                'type': 'buyer',
                'description': 'Leading construction company specializing in commercial and residential projects',
                'website': 'https://acmeconstruction.com',
                'address': '123 Construction Ave, New York, NY 10001',
                'phone': '+1-555-0100',
                'email': 'info@acmeconstruction.com',
                'is_active': True,
            },
            {
                'name': 'Global Manufacturing Inc',
                'code': 'GMI',
                'type': 'buyer',
                'description': 'Enterprise manufacturing company with operations worldwide',
                'website': 'https://globalmanufacturing.com',
                'address': '456 Industrial Blvd, Chicago, IL 60601',
                'phone': '+1-555-0200',
                'email': 'info@globalmanufacturing.com',
                'is_active': True,
            }
        ]
        
        for data in org_data:
            org, created = Organization.objects.get_or_create(
                code=data['code'],
                defaults=data
            )
            orgs.append(org)
        
        return orgs

    def create_users(self, organization):
        """Create sample users with profiles"""
        users = []
        
        # Get or create admin user
        admin_user = User.objects.filter(username='admin').first()
        if admin_user:
            users.append(admin_user)
            # Create profile if doesn't exist
            UserProfile.objects.get_or_create(
                user=admin_user,
                defaults={
                    'organization': organization,
                    'role': 'admin',
                    'department': 'IT',
                    'job_title': 'System Administrator',
                    'phone': '+1-555-0001',
                }
            )
        
        # Create additional users
        user_data = [
            {
                'username': 'john.doe',
                'email': 'john.doe@acme.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'profile': {
                    'role': 'manager',
                    'department': 'Procurement',
                    'job_title': 'Procurement Manager',
                    'phone': '+1-555-0002',
                }
            },
            {
                'username': 'jane.smith',
                'email': 'jane.smith@acme.com',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'profile': {
                    'role': 'buyer',
                    'department': 'Procurement',
                    'job_title': 'Senior Buyer',
                    'phone': '+1-555-0003',
                }
            },
            {
                'username': 'bob.wilson',
                'email': 'bob.wilson@acme.com',
                'first_name': 'Bob',
                'last_name': 'Wilson',
                'profile': {
                    'role': 'analyst',
                    'department': 'Finance',
                    'job_title': 'Cost Analyst',
                    'phone': '+1-555-0004',
                }
            }
        ]
        
        for data in user_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                }
            )
            if created:
                user.set_password('password123')
                user.save()
            
            # Create profile
            profile_data = data['profile']
            profile_data['organization'] = organization
            UserProfile.objects.get_or_create(
                user=user,
                defaults=profile_data
            )
            users.append(user)
        
        return users

    def create_categories(self, organization):
        """Create material categories"""
        categories = []
        
        category_data = [
            ('STEEL', 'Steel Products', 'All steel-based materials'),
            ('CONCRETE', 'Concrete & Cement', 'Concrete, cement, and related products'),
            ('ELECTRICAL', 'Electrical Components', 'Electrical equipment and components'),
            ('PLUMBING', 'Plumbing Materials', 'Pipes, fixtures, and plumbing supplies'),
            ('LUMBER', 'Lumber & Wood', 'Wood products and lumber'),
            ('HARDWARE', 'Hardware & Tools', 'General hardware and tools'),
            ('SAFETY', 'Safety Equipment', 'PPE and safety supplies'),
            ('CHEMICALS', 'Chemicals & Adhesives', 'Industrial chemicals and adhesives'),
        ]
        
        for code, name, description in category_data:
            # Use unique together constraint for organization and name
            cat, created = Category.objects.get_or_create(
                organization=organization,
                name=name,
                defaults={
                    'description': description,
                }
            )
            categories.append(cat)
        
        return categories

    def create_suppliers(self, organization):
        """Create sample suppliers"""
        suppliers = []
        
        supplier_types = [
            ('Steel', 'manufacturer'),
            ('Concrete', 'manufacturer'),
            ('Electrical', 'distributor'),
            ('Plumbing', 'distributor'),
            ('General', 'reseller'),
        ]
        
        for i, (type_name, sup_type) in enumerate(supplier_types):
            for j in range(3):  # 3 suppliers per category
                supplier_num = i * 3 + j + 1
                supplier, created = Supplier.objects.get_or_create(
                    organization=organization,
                    code=f'SUP{supplier_num:03d}',
                    defaults={
                        'name': f'{type_name} Supplier {j+1}',
                        'supplier_type': sup_type,
                        'primary_contact_name': fake.name(),
                        'primary_contact_email': f'sales{supplier_num}@supplier.com',
                        'primary_contact_phone': f'+155510{supplier_num:02d}',
                        'address': {
                            'street': fake.street_address(),
                            'city': fake.city(),
                            'state': fake.state_abbr(),
                            'postal_code': fake.postcode(),
                            'country': 'US'
                        },
                        'country': 'US',
                        'website': f'https://supplier{supplier_num}.com',
                        'tax_id': f'US{random.randint(100000000, 999999999)}',
                        'status': 'active',
                        'rating': Decimal(str(round(random.uniform(3.5, 5.0), 1))),
                        'payment_terms': random.choice(['Net 30', 'Net 45', 'Net 60']),
                        'currency': 'USD',
                        'on_time_delivery_rate': Decimal(str(round(random.uniform(85, 99), 1))),
                        'quality_score': Decimal(str(round(random.uniform(90, 99), 1))),
                        'risk_level': random.choice(['low', 'medium']),
                    }
                )
                suppliers.append(supplier)
        
        return suppliers

    def create_materials(self, organization, categories):
        """Create sample materials"""
        materials = []
        
        # Steel products
        steel_cat = next((c for c in categories if 'Steel' in c.name), None)
        if steel_cat:
            steel_materials = [
                ('MAT001', 'Steel Rebar 12mm', 'High-strength steel reinforcement bar', 'ton', {'diameter': '12mm', 'grade': 'Fe500'}),
                ('MAT002', 'Steel Rebar 16mm', 'High-strength steel reinforcement bar', 'ton', {'diameter': '16mm', 'grade': 'Fe500'}),
                ('MAT003', 'Steel Beam I-Section 200mm', 'Structural steel I-beam', 'piece', {'height': '200mm', 'weight': '25.3 kg/m'}),
                ('MAT004', 'Steel Plate 10mm', 'Mild steel plate', 'sqm', {'thickness': '10mm', 'grade': 'S275'}),
                ('MAT005', 'Steel Pipe 2 inch', 'Galvanized steel pipe', 'meter', {'diameter': '2 inch', 'wall': '3mm'}),
            ]
            
            for code, name, desc, uom, specs in steel_materials:
                mat, created = Material.objects.get_or_create(
                    organization=organization,
                    code=code,
                    defaults={
                        'category': steel_cat,
                        'name': name,
                        'description': desc,
                        'material_type': 'raw_material',
                        'unit_of_measure': uom,
                        'specifications': specs,
                        'status': 'active',
                    }
                )
                materials.append(mat)
        
        # Concrete products
        concrete_cat = next((c for c in categories if 'Concrete' in c.name), None)
        if concrete_cat:
            concrete_materials = [
                ('MAT006', 'Ready Mix Concrete C25', 'Standard concrete mix', 'cum', {'strength': '25 MPa', 'slump': '100mm'}),
                ('MAT007', 'Ready Mix Concrete C30', 'High-strength concrete mix', 'cum', {'strength': '30 MPa', 'slump': '100mm'}),
                ('MAT008', 'Portland Cement Type I', 'General purpose cement', 'bag', {'weight': '50kg', 'type': 'Type I'}),
                ('MAT009', 'Concrete Block 8 inch', 'Standard concrete block', 'piece', {'size': '8x8x16 inch', 'weight': '28 lbs'}),
            ]
            
            for code, name, desc, uom, specs in concrete_materials:
                mat, created = Material.objects.get_or_create(
                    organization=organization,
                    code=code,
                    defaults={
                        'category': concrete_cat,
                        'name': name,
                        'description': desc,
                        'material_type': 'raw_material',
                        'unit_of_measure': uom,
                        'specifications': specs,
                        'status': 'active',
                    }
                )
                materials.append(mat)
        
        # Electrical components
        electrical_cat = next((c for c in categories if 'Electrical' in c.name), None)
        if electrical_cat:
            electrical_materials = [
                ('MAT010', 'Copper Wire 2.5mm', 'Electrical copper wire', 'meter', {'size': '2.5mm²', 'insulation': 'PVC'}),
                ('MAT011', 'Circuit Breaker 20A', 'Single pole circuit breaker', 'piece', {'rating': '20A', 'poles': '1'}),
                ('MAT012', 'LED Panel Light 40W', 'Ceiling panel light', 'piece', {'power': '40W', 'size': '600x600mm'}),
            ]
            
            for code, name, desc, uom, specs in electrical_materials:
                mat, created = Material.objects.get_or_create(
                    organization=organization,
                    code=code,
                    defaults={
                        'category': electrical_cat,
                        'name': name,
                        'description': desc,
                        'material_type': 'component',
                        'unit_of_measure': uom,
                        'specifications': specs,
                        'status': 'active',
                    }
                )
                materials.append(mat)
        
        return materials

    def create_price_history(self, organization, materials, suppliers):
        """Create historical price data"""
        today = timezone.now()
        
        for material in materials[:10]:  # Create history for first 10 materials
            # Random supplier for this material
            supplier = random.choice(suppliers)
            
            # Generate prices for last 90 days
            for days_ago in range(90, 0, -7):  # Weekly prices
                price_date = today - timedelta(days=days_ago)
                base_price = Decimal(random.uniform(100, 1000))
                
                # Add some price variation
                variation = Decimal(random.uniform(-5, 5)) / 100
                price_value = base_price * (1 + variation)
                
                Price.objects.create(
                    organization=organization,
                    material=material,
                    supplier=supplier,
                    price=price_value.quantize(Decimal('0.01')),
                    currency='USD',
                    valid_from=price_date.date(),
                    valid_to=(price_date + timedelta(days=30)).date(),
                    source='quote',
                    confidence_score=random.uniform(0.7, 1.0),
                    time=price_date,
                )

    def create_rfqs(self, organization, user, materials, suppliers):
        """Create sample RFQs with quotes"""
        rfqs = []
        
        for i in range(5):  # Create 5 RFQs
            rfq, created = RFQ.objects.get_or_create(
                organization=organization,
                rfq_number=f'RFQ-2025-{1000+i}',
                defaults={
                    'title': f'Q4 2025 Materials Order {i+1}',
                    'description': f'Quarterly material procurement for Project {i+1}',
                    'status': random.choice(['draft', 'published', 'closed', 'awarded']),
                    'priority': random.choice(['low', 'medium', 'high']),
                    'deadline': timezone.now() + timedelta(days=random.randint(7, 30)),
                    'delivery_terms': random.choice(['FOB', 'CIF', 'EXW']),
                    'payment_terms': random.choice(['Net 30', 'Net 45', 'Net 60']),
                    'created_by': user,
                }
            )
            
            # Get random suppliers for later use with quotes
            selected_suppliers = random.sample(suppliers, k=min(3, len(suppliers)))
            
            # Add items to RFQ
            selected_materials = random.sample(materials, k=min(3, len(materials)))
            for material in selected_materials:
                RFQItem.objects.create(
                    rfq=rfq,
                    material=material,
                    quantity=Decimal(random.randint(10, 100)),
                    unit_of_measure=material.unit_of_measure,
                    required_delivery_date=timezone.now().date() + timedelta(days=random.randint(30, 60)),
                    notes='As per standard specifications',
                )
            
            # Create quotes from suppliers (simplified for now)
            # We'll skip quotes for now as they have complex relationships
            
            rfqs.append(rfq)
        
        return rfqs

    def create_price_alerts(self, organization, materials, user):
        """Create price alerts"""
        alerts = []
        
        for i, material in enumerate(materials[:5]):  # Create alerts for first 5 materials
            alert, created = PriceAlert.objects.get_or_create(
                organization=organization,
                material=material,
                user=user,
                name=f'Price Alert for {material.name}',
                defaults={
                    'alert_type': random.choice(['threshold', 'anomaly', 'trend']),
                    'condition_type': random.choice(['above', 'below']),
                    'threshold_value': Decimal(random.randint(500, 1500)),
                    'status': 'active',
                }
            )
            alerts.append(alert)
        
        return alerts
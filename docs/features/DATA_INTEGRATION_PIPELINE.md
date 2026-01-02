# Data Integration Pipeline - Critical Implementation Requirements

## Executive Summary

**CRITICAL GAP**: The uploaded procurement data is currently isolated in staging tables and NOT integrated with the main business logic or analytics. This document outlines the required data processing pipeline to connect uploaded data with the rest of the system.

## Current State vs Required State

### Current State (As of Phase 0.5)
```
✅ File Upload → ✅ Staging Table → ❌ [NO PROCESSING] → ❌ [NO INTEGRATION]
```

### Required State
```
✅ File Upload → ✅ Staging Table → ✅ Processing Pipeline → ✅ Main Tables → ✅ Analytics
```

## Data Flow Architecture

### 1. Staging Layer (COMPLETE)
```python
ProcurementDataStaging (django_app.apps.data_ingestion.models)
├── Raw uploaded data
├── Validation status
├── Mapped fields (supplier, material, pricing)
└── Processing flags
```

### 2. Processing Pipeline (REQUIRED - NOT IMPLEMENTED)

#### 2.1 Data Processing Service
```python
# Required implementation in apps/data_ingestion/services/data_processor.py

class DataProcessor:
    def process_upload(self, upload_id):
        """Main processing pipeline"""
        # 1. Fetch staging records
        # 2. Process suppliers
        # 3. Process materials
        # 4. Create purchase orders
        # 5. Record price history
        # 6. Update metrics
        
    def match_or_create_supplier(self, staging_record):
        """Intelligent supplier matching"""
        # Match by: code, tax_id, name similarity
        # Create if no match found
        # Update supplier metrics
        
    def match_or_create_material(self, staging_record):
        """Intelligent material matching"""
        # Match by: code, description similarity
        # Create if no match found
        # Update material catalog
        
    def create_purchase_order(self, staging_record, supplier, material):
        """Create PO from staging data"""
        # Check for duplicates
        # Create PO with line items
        # Link to supplier and material
        
    def record_price_history(self, staging_record, material, supplier):
        """Populate TimescaleDB price history"""
        # Create time-series entry
        # Calculate price trends
        # Trigger alerts if needed
```

### 3. Main Business Tables (EXISTING - NOT CONNECTED)

#### Procurement Module Tables
- `Supplier` - Supplier master records
- `PurchaseOrder` - Purchase order records
- `RFQ` - Request for quotation records

#### Pricing Module Tables
- `Material` - Material/product catalog
- `Price` - Time-series pricing data (TimescaleDB)
- `PriceAlert` - Price threshold alerts

#### Analytics Module Tables
- `DashboardMetric` - Real-time KPIs
- `Report` - Generated reports
- `Alert` - System notifications

## Implementation Roadmap

### Phase 1: Basic Integration (Week 1 - PRIORITY)

#### Day 1-2: Core Processing Pipeline
```python
# apps/data_ingestion/tasks.py
from celery import shared_task

@shared_task
def process_staging_data(upload_id):
    """Async task to process uploaded data"""
    processor = DataProcessor()
    processor.process_upload(upload_id)
```

#### Day 3-4: Supplier & Material Matching
```python
# apps/data_ingestion/services/matching.py
class EntityMatcher:
    def match_supplier(self, name, code, tax_id):
        # Exact match by code
        # Fuzzy match by name (>80% similarity)
        # Match by tax_id
        return supplier or None
    
    def match_material(self, code, description):
        # Exact match by code
        # Fuzzy match by description
        return material or None
```

#### Day 5: Data Validation & Deduplication
```python
# apps/data_ingestion/services/validation.py
class DataValidator:
    def check_duplicate_po(self, po_number):
        # Check if PO already exists
        
    def validate_pricing(self, price, material):
        # Check against historical ranges
        # Flag anomalies
```

### Phase 2: Advanced Features (Week 2)

#### Conflict Resolution UI
```html
<!-- templates/data_ingestion/conflict_resolution.html -->
<div class="conflict-resolver">
    <h3>Supplier Match Conflict</h3>
    <p>Uploaded: "ACME Corp" (Code: ACME001)</p>
    <p>Possible matches:</p>
    <ul>
        <li>[Select] ACME Corporation (95% match)</li>
        <li>[Select] Acme Industries (82% match)</li>
        <li>[Create New] Create as new supplier</li>
    </ul>
</div>
```

#### Batch Processing Management
```python
# apps/data_ingestion/views.py
@login_required
def process_upload_batch(request, upload_id):
    """Process uploaded data with user confirmations"""
    # Show conflicts
    # Get user decisions
    # Process with decisions
    # Show results
```

### Phase 3: Analytics Integration (Week 3)

#### Connect to Dashboard Metrics
```python
# apps/analytics/services/metric_calculator.py
def calculate_spend_metrics():
    """Include processed upload data in metrics"""
    # Query from main tables (now includes uploaded data)
    # Calculate KPIs
    # Update dashboard
```

#### Enable ML Predictions
```python
# fastapi_ml/services/price_predictor.py
def get_historical_prices(material_id):
    """Get prices including uploaded historical data"""
    # Query Price table (now has uploaded history)
    # Return time-series for ML model
```

## Database Migrations Required

### 1. Add Foreign Keys to Staging Table
```python
# apps/data_ingestion/migrations/0002_add_processing_fields.py
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='procurementdatastaging',
            name='matched_supplier',
            field=models.ForeignKey('procurement.Supplier', null=True)
        ),
        migrations.AddField(
            model_name='procurementdatastaging',
            name='matched_material',
            field=models.ForeignKey('pricing.Material', null=True)
        ),
        migrations.AddField(
            model_name='procurementdatastaging',
            name='created_po',
            field=models.ForeignKey('procurement.PurchaseOrder', null=True)
        ),
    ]
```

### 2. Add Processing Status to Upload
```python
migrations.AddField(
    model_name='dataupload',
    name='processing_method',
    field=models.CharField(choices=[
        ('auto', 'Automatic'),
        ('manual', 'Manual Review'),
        ('hybrid', 'Partial Manual')
    ])
)
```

## API Endpoints Required

### Processing Control
```python
# apps/data_ingestion/api/views.py

@api_view(['POST'])
def start_processing(request, upload_id):
    """Start processing uploaded data"""
    # Validate upload status
    # Start async processing
    # Return task ID
    
@api_view(['GET'])
def processing_status(request, task_id):
    """Check processing status"""
    # Get Celery task status
    # Return progress
    
@api_view(['POST'])
def resolve_conflicts(request, upload_id):
    """Submit conflict resolutions"""
    # Get user decisions
    # Apply to staging records
    # Continue processing
```

## Testing Requirements

### Unit Tests
```python
# apps/data_ingestion/tests/test_processor.py
class TestDataProcessor(TestCase):
    def test_supplier_matching(self):
        # Test exact match
        # Test fuzzy match
        # Test no match creates new
        
    def test_duplicate_detection(self):
        # Test PO duplicate check
        # Test invoice duplicate check
```

### Integration Tests
```python
# apps/data_ingestion/tests/test_integration.py
class TestDataIntegration(TestCase):
    def test_full_pipeline(self):
        # Upload file
        # Process staging
        # Verify main tables populated
        # Check analytics updated
```

## Performance Considerations

### Batch Processing
- Process in chunks of 1000 records
- Use bulk_create for efficiency
- Implement progress tracking

### Caching
- Cache supplier/material lookups
- Use Redis for processing state
- Implement match result caching

### Database Optimization
```sql
-- Add indexes for matching
CREATE INDEX idx_supplier_code ON suppliers(code);
CREATE INDEX idx_supplier_tax_id ON suppliers(tax_id);
CREATE INDEX idx_material_code ON materials(code);

-- Add indexes for staging queries
CREATE INDEX idx_staging_upload_status ON procurement_data_staging(upload_id, validation_status);
```

## Monitoring & Alerting

### Processing Metrics
- Records processed per minute
- Match success rate
- Error rate
- Processing time per upload

### Alert Triggers
- Processing failures
- Low match rates (<70%)
- Duplicate rate >10%
- Price anomalies detected

## Security Considerations

### Data Validation
- Sanitize all input data
- Validate against SQL injection
- Check file integrity
- Verify data ownership

### Audit Trail
- Log all processing decisions
- Track user overrides
- Record data transformations
- Maintain compliance trail

## Success Criteria

### Week 1 Deliverables
- [ ] Basic processing pipeline operational
- [ ] Staging data flows to main tables
- [ ] Suppliers and materials created/matched
- [ ] Purchase orders created from uploads

### Week 2 Deliverables
- [ ] Conflict resolution UI
- [ ] Fuzzy matching algorithms
- [ ] Batch processing controls
- [ ] Data quality scoring

### Week 3 Deliverables
- [ ] Analytics include uploaded data
- [ ] ML models use historical uploads
- [ ] Automated insights generation
- [ ] Real-time monitoring dashboard

## Priority Actions

### Immediate (Day 1)
1. Create `DataProcessor` service class
2. Implement basic supplier matching
3. Add processing endpoint to views
4. Create Celery task for async processing

### Short-term (Week 1)
1. Complete material matching logic
2. Implement PO creation from staging
3. Add price history recording
4. Basic deduplication checks

### Medium-term (Week 2-3)
1. Build conflict resolution UI
2. Implement fuzzy matching
3. Connect to analytics
4. Enable ML predictions

## Code Examples

### Example: Processing Pipeline
```python
# apps/data_ingestion/services/processor.py
from django.db import transaction
from apps.procurement.models import Supplier, PurchaseOrder
from apps.pricing.models import Material, Price

class DataProcessor:
    @transaction.atomic
    def process_upload(self, upload_id):
        upload = DataUpload.objects.get(id=upload_id)
        staging_records = ProcurementDataStaging.objects.filter(
            upload=upload,
            validation_status='valid',
            is_processed=False
        )
        
        for record in staging_records:
            # Match or create supplier
            supplier = self.match_or_create_supplier(record)
            record.matched_supplier = supplier
            
            # Match or create material
            material = self.match_or_create_material(record)
            record.matched_material = material
            
            # Create purchase order
            if not self.is_duplicate_po(record.po_number):
                po = self.create_purchase_order(record, supplier, material)
                record.created_po = po
            
            # Record price history
            self.record_price(record, material, supplier)
            
            # Mark as processed
            record.is_processed = True
            record.processed_at = timezone.now()
            record.save()
        
        # Update upload status
        upload.status = 'completed'
        upload.processing_completed_at = timezone.now()
        upload.save()
```

### Example: Supplier Matching
```python
from django.db.models import Q
from fuzzywuzzy import fuzz

def match_or_create_supplier(self, record):
    # Try exact match by code
    if record.supplier_code:
        supplier = Supplier.objects.filter(
            organization=record.organization,
            code=record.supplier_code
        ).first()
        if supplier:
            return supplier
    
    # Try fuzzy match by name
    if record.supplier_name:
        suppliers = Supplier.objects.filter(
            organization=record.organization
        )
        for supplier in suppliers:
            if fuzz.ratio(supplier.name.lower(), 
                         record.supplier_name.lower()) > 85:
                return supplier
    
    # Create new supplier
    return Supplier.objects.create(
        organization=record.organization,
        code=record.supplier_code or f"AUTO_{uuid.uuid4().hex[:8]}",
        name=record.supplier_name,
        supplier_type='distributor',
        status='pending_approval'
    )
```

## Conclusion

The data integration pipeline is the **critical missing component** that will enable the AI Pricing Agent to deliver value from uploaded data. Without this pipeline, the system cannot:
- Analyze uploaded procurement data
- Generate insights from historical uploads
- Make ML predictions based on real data
- Provide accurate cost benchmarking

**Priority**: Implement Phase 1 (Basic Integration) immediately to unblock analytics and ML capabilities.
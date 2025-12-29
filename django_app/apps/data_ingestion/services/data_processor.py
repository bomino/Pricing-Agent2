"""
Data Processing Pipeline for moving staging data to main business tables
"""
import uuid
import datetime
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from fuzzywuzzy import fuzz
import logging

from apps.data_ingestion.models import (
    DataUpload, 
    ProcurementDataStaging, 
    DataIngestionLog
)
from apps.procurement.models import Supplier, PurchaseOrder, PurchaseOrderLine
from apps.pricing.models import Material, Price, Category
from apps.core.models import Organization

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Main processor for moving data from staging to production tables
    """
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.created_suppliers = []
        self.matched_suppliers = []
        self.created_materials = []
        self.matched_materials = []
        self.created_pos = []
        
    @transaction.atomic
    def process_upload(self, upload_id: str) -> Dict[str, Any]:
        """
        Process all staging records for an upload
        
        Args:
            upload_id: UUID of the DataUpload record
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Get upload record
            upload = DataUpload.objects.get(id=upload_id)
            upload.status = 'processing'
            upload.processing_started_at = timezone.now()
            upload.save()
            
            # Log processing start
            self._log_action(upload, 'processing_started', 
                           f'Started processing {upload.total_rows} records')
            
            # Get staging records
            staging_records = ProcurementDataStaging.objects.filter(
                upload=upload,
                validation_status='valid',
                is_processed=False
            ).order_by('row_number')
            
            # Process each record
            for record in staging_records:
                try:
                    self._process_single_record(record)
                    self.processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing record {record.id}: {str(e)}")
                    self.error_count += 1
                    record.validation_status = 'invalid'
                    record.validation_errors.append(str(e))
                    record.save()
            
            # Update upload status
            upload.status = 'completed' if self.error_count == 0 else 'partial'
            upload.processing_completed_at = timezone.now()
            upload.processed_rows = self.processed_count
            upload.failed_rows = self.error_count
            upload.duplicate_rows = self.duplicate_count
            
            duration = (upload.processing_completed_at - upload.processing_started_at).total_seconds()
            upload.processing_duration_seconds = int(duration)
            upload.save()
            
            # Log completion
            self._log_action(upload, 'processing_completed',
                           f'Processed {self.processed_count} records successfully',
                           {'errors': self.error_count, 'duplicates': self.duplicate_count})
            
            return {
                'success': True,
                'processed': self.processed_count,
                'errors': self.error_count,
                'duplicates': self.duplicate_count,
                'created_suppliers': len(self.created_suppliers),
                'matched_suppliers': len(self.matched_suppliers),
                'created_materials': len(self.created_materials),
                'matched_materials': len(self.matched_materials),
                'created_pos': len(self.created_pos),
                'skipped': self.duplicate_count
            }
            
        except Exception as e:
            logger.error(f"Fatal error processing upload {upload_id}: {str(e)}")
            if 'upload' in locals():
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
                self._log_action(upload, 'error_occurred', str(e))
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_single_record(self, record: ProcurementDataStaging) -> None:
        """
        Process a single staging record
        """
        # Match or create supplier
        supplier = self._match_or_create_supplier(record)
        record.matched_supplier = supplier
        
        # Match or create material
        material = self._match_or_create_material(record)
        record.matched_material = material
        
        # Check for duplicate PO
        if record.po_number and not self._is_duplicate_po(record):
            # Create or update purchase order
            po = self._create_or_update_purchase_order(record, supplier, material)
            record.created_po = po
        else:
            self.duplicate_count += 1
            record.is_duplicate = True
        
        # Record price history
        if material and record.unit_price:
            self._record_price_history(record, material, supplier)
        
        # Mark record as processed
        record.is_processed = True
        record.processed_at = timezone.now()
        record.save()
    
    def _match_or_create_supplier(self, record: ProcurementDataStaging) -> Optional[Supplier]:
        """
        Match existing supplier or create new one
        """
        if not record.supplier_name and not record.supplier_code:
            return None
        
        organization = record.upload.organization
        
        # Try exact match by code
        if record.supplier_code:
            supplier = Supplier.objects.filter(
                organization=organization,
                code=record.supplier_code
            ).first()
            if supplier:
                self.matched_suppliers.append(supplier)
                return supplier
        
        # Try fuzzy match by name
        if record.supplier_name:
            suppliers = Supplier.objects.filter(organization=organization)
            for supplier in suppliers:
                similarity = fuzz.ratio(
                    supplier.name.lower(), 
                    record.supplier_name.lower()
                )
                if similarity > 85:  # 85% similarity threshold
                    self.matched_suppliers.append(supplier)
                    return supplier
        
        # Create new supplier
        supplier = Supplier.objects.create(
            organization=organization,
            code=record.supplier_code or f"AUTO_{uuid.uuid4().hex[:8].upper()}",
            name=record.supplier_name or "Unknown Supplier",
            supplier_type='distributor',
            status='pending_approval',
            country=record.raw_data.get('country', ''),
            notes=f"Auto-created from upload: {record.upload.original_filename}"
        )
        
        self.created_suppliers.append(supplier)
        logger.info(f"Created new supplier: {supplier.code} - {supplier.name}")
        
        return supplier
    
    def _match_or_create_material(self, record: ProcurementDataStaging) -> Optional[Material]:
        """
        Match existing material or create new one
        """
        if not record.material_code and not record.material_description:
            return None
        
        organization = record.upload.organization
        
        # Try exact match by code
        if record.material_code:
            material = Material.objects.filter(
                organization=organization,
                code=record.material_code
            ).first()
            if material:
                self.matched_materials.append(material)
                return material
        
        # Try fuzzy match by description
        if record.material_description:
            materials = Material.objects.filter(organization=organization)
            for material in materials:
                similarity = fuzz.token_sort_ratio(
                    material.description.lower(),
                    record.material_description.lower()
                )
                if similarity > 80:  # 80% similarity threshold
                    self.matched_materials.append(material)
                    return material
        
        # Get or create category
        category = None
        if record.material_category:
            category, _ = Category.objects.get_or_create(
                organization=organization,
                name=record.material_category,
                defaults={'description': f"Auto-created from upload"}
            )
        
        # Create new material
        material = Material.objects.create(
            organization=organization,
            code=record.material_code or f"MAT_{uuid.uuid4().hex[:8].upper()}",
            name=record.material_description[:255] if record.material_description else "Unknown Material",
            description=record.material_description or "",
            material_type='raw_material',
            category=category,
            unit_of_measure=record.unit_of_measure or 'EA',
            status='active',
            currency=record.currency or 'USD'
        )
        
        self.created_materials.append(material)
        logger.info(f"Created new material: {material.code} - {material.name}")
        
        return material
    
    def _is_duplicate_po(self, record: ProcurementDataStaging) -> bool:
        """
        Check if PO already exists
        """
        if not record.po_number:
            return False
        
        return PurchaseOrder.objects.filter(
            organization=record.upload.organization,
            po_number=record.po_number
        ).exists()
    
    def _create_or_update_purchase_order(self, record: ProcurementDataStaging,
                                        supplier: Optional[Supplier],
                                        material: Optional[Material]) -> Optional[PurchaseOrder]:
        """
        Create or update purchase order from staging record
        """
        if not record.po_number:
            return None
        
        organization = record.upload.organization
        
        # Get or create PO header
        po, created = PurchaseOrder.objects.get_or_create(
            organization=organization,
            po_number=record.po_number,
            defaults={
                'supplier': supplier,
                'order_date': record.purchase_date or timezone.now().date(),
                'delivery_date': record.delivery_date,
                'status': 'completed',  # Historical data is completed
                'total_amount': Decimal('0'),
                'currency': record.currency or 'USD',
                'created_by': record.upload.uploaded_by,
            }
        )
        
        # Create or update line item
        if material and record.quantity and record.unit_price:
            line, line_created = PurchaseOrderLine.objects.get_or_create(
                purchase_order=po,
                line_number=record.line_item_number or '1',
                defaults={
                    'material': material,
                    'quantity': record.quantity,
                    'unit_price': record.unit_price,
                    'total_price': record.total_price or (record.quantity * record.unit_price),
                    'delivery_date': record.delivery_date or po.delivery_date,
                }
            )
            
            # Update PO total
            po.total_amount = sum(
                line.total_price for line in po.lines.all()
            )
            po.save()
        
        if created:
            self.created_pos.append(po)
            logger.info(f"Created new PO: {po.po_number}")
        
        return po
    
    def _record_price_history(self, record: ProcurementDataStaging,
                             material: Material,
                             supplier: Optional[Supplier]) -> None:
        """
        Record price in time-series table
        """
        if not record.unit_price or not record.purchase_date:
            return
        
        # Check if price already exists for this date/material/supplier combo
        existing = Price.objects.filter(
            time=record.purchase_date,
            material=material,
            supplier=supplier,
            price_type='historical'
        ).first()
        
        if not existing:
            Price.objects.create(
                organization=record.upload.organization,
                time=datetime.datetime.combine(
                    record.purchase_date, datetime.time.min, tzinfo=timezone.get_current_timezone()
                ) if record.purchase_date else timezone.now(),
                material=material,
                supplier=supplier,
                price=record.unit_price,
                price_type='historical',
                quantity=record.quantity,
                currency=record.currency or 'USD',
                source='upload',
                metadata={
                    'upload_id': str(record.upload.id),
                    'po_number': record.po_number,
                    'original_filename': record.upload.original_filename
                }
            )
            logger.debug(f"Recorded price history: {material.code} @ {record.unit_price}")
    
    def _log_action(self, upload: DataUpload, action: str, message: str, 
                   details: Dict[str, Any] = None) -> None:
        """
        Create audit log entry
        """
        DataIngestionLog.objects.create(
            upload=upload,
            action=action,
            user=upload.uploaded_by,
            message=message,
            details=details or {},
            rows_affected=self.processed_count
        )


class EntityMatcher:
    """
    Advanced matching algorithms for suppliers and materials
    """
    
    @staticmethod
    def match_supplier_advanced(organization: Organization, 
                               name: str = None,
                               code: str = None,
                               tax_id: str = None) -> Optional[Supplier]:
        """
        Advanced supplier matching with multiple criteria
        """
        query = Q(organization=organization)
        
        # Build query based on available fields
        if code:
            query &= Q(code__iexact=code)
        if tax_id:
            query &= Q(tax_id=tax_id)
        
        # Try exact matches first
        exact_match = Supplier.objects.filter(query).first()
        if exact_match:
            return exact_match
        
        # Try fuzzy name matching
        if name:
            suppliers = Supplier.objects.filter(organization=organization)
            best_match = None
            best_score = 0
            
            for supplier in suppliers:
                # Multiple matching algorithms
                simple_ratio = fuzz.ratio(supplier.name.lower(), name.lower())
                partial_ratio = fuzz.partial_ratio(supplier.name.lower(), name.lower())
                token_sort = fuzz.token_sort_ratio(supplier.name.lower(), name.lower())
                
                # Weighted average
                score = (simple_ratio * 0.4 + partial_ratio * 0.3 + token_sort * 0.3)
                
                if score > best_score and score > 75:  # 75% threshold
                    best_score = score
                    best_match = supplier
            
            return best_match
        
        return None
    
    @staticmethod
    def match_material_advanced(organization: Organization,
                               code: str = None,
                               description: str = None,
                               category: str = None) -> Optional[Material]:
        """
        Advanced material matching with multiple criteria
        """
        # Try exact code match
        if code:
            material = Material.objects.filter(
                organization=organization,
                code__iexact=code
            ).first()
            if material:
                return material
        
        # Try description matching
        if description:
            materials = Material.objects.filter(organization=organization)
            
            # If category provided, filter by it
            if category:
                materials = materials.filter(
                    Q(category__name__icontains=category) |
                    Q(attributes__category__icontains=category)
                )
            
            best_match = None
            best_score = 0
            
            for material in materials:
                # Compare descriptions
                desc_score = fuzz.token_set_ratio(
                    material.description.lower(),
                    description.lower()
                )
                
                # Compare names
                name_score = fuzz.token_sort_ratio(
                    material.name.lower(),
                    description.lower()
                )
                
                # Best of both scores
                score = max(desc_score, name_score)
                
                if score > best_score and score > 70:  # 70% threshold for materials
                    best_score = score
                    best_match = material
            
            return best_match
        
        return None
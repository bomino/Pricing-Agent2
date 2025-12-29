"""
Optimized Data Processing Pipeline with caching and bulk operations
Performance improvements:
- Caches entities once at start
- Uses indexed fuzzy matching
- Bulk creates records
- Batch processing
"""
import uuid
import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Set, Tuple
from collections import defaultdict
from django.db import transaction, connection
from django.utils import timezone
from django.db.models import Q
from fuzzywuzzy import fuzz, process
import logging

from apps.data_ingestion.models import (
    DataUpload,
    ProcurementDataStaging,
    DataIngestionLog,
    MatchingConflict
)
from apps.procurement.models import Supplier, PurchaseOrder, PurchaseOrderLine
from apps.pricing.models import Material, Price, Category
from apps.core.models import Organization

logger = logging.getLogger(__name__)


class OptimizedDataProcessor:
    """
    Optimized processor with caching and bulk operations
    """
    
    # Batch size for bulk operations
    BATCH_SIZE = 500
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.duplicate_count = 0

        # Track created entities
        self.created_suppliers = []
        self.matched_suppliers = []
        self.created_materials = []
        self.matched_materials = []
        self.created_pos = []
        self.created_po_lines = []
        self.created_prices = []  # Track created price records
        self.created_conflicts = []  # Track matching conflicts

        # Caches for fast lookup
        self.supplier_cache = {}  # code -> supplier
        self.supplier_name_cache = {}  # normalized_name -> supplier
        self.material_cache = {}  # code -> material
        self.material_desc_cache = {}  # normalized_desc -> material
        self.po_cache = set()  # po_numbers

        # Fuzzy matching indexes
        self.supplier_names_index = []
        self.material_descs_index = []

        # Conflict resolution threshold settings
        self.auto_resolve_threshold = 0.95  # Above this, auto-match
        self.conflict_threshold = 0.75      # Between this and auto_resolve, create conflict

        # Progress callback for UI updates
        self.progress_callback = None
    
    def _initialize_caches(self, organization: Organization):
        """
        Pre-load all entities into memory for fast lookup
        """
        logger.info("Initializing caches...")
        
        # Cache suppliers
        suppliers = Supplier.objects.filter(organization=organization).only(
            'id', 'code', 'name'
        )
        
        for supplier in suppliers:
            if supplier.code:
                self.supplier_cache[supplier.code.upper()] = supplier
            
            normalized_name = supplier.name.upper().strip()
            self.supplier_name_cache[normalized_name] = supplier
            self.supplier_names_index.append((normalized_name, supplier))
        
        logger.info(f"Cached {len(suppliers)} suppliers")
        
        # Cache materials
        materials = Material.objects.filter(organization=organization).only(
            'id', 'code', 'name', 'description'
        )
        
        for material in materials:
            if material.code:
                self.material_cache[material.code.upper()] = material
            
            # Use description for fuzzy matching
            desc = (material.description or material.name or '').upper().strip()
            if desc:
                self.material_desc_cache[desc] = material
                self.material_descs_index.append((desc, material))
        
        logger.info(f"Cached {len(materials)} materials")
        
        # Cache existing PO numbers
        existing_pos = PurchaseOrder.objects.filter(
            organization=organization
        ).values_list('po_number', flat=True)
        
        self.po_cache = set(existing_pos)
        logger.info(f"Cached {len(self.po_cache)} PO numbers")
    
    @transaction.atomic
    def process_upload(self, upload_id: str) -> Dict[str, Any]:
        """
        Process upload with optimized batch operations
        """
        try:
            upload = DataUpload.objects.select_related('organization').get(id=upload_id)
            upload.processing_started_at = timezone.now()
            upload.status = 'processing'
            upload.save()
            
            # Initialize caches
            self._initialize_caches(upload.organization)
            
            # Get all staging records at once
            staging_records = list(
                ProcurementDataStaging.objects.filter(
                    upload=upload,
                    validation_status='valid',
                    is_processed=False
                ).order_by('row_number')
            )
            
            total_records = len(staging_records)
            logger.info(f"Processing {total_records} records in batches of {self.BATCH_SIZE}")
            
            # Process in batches
            for i in range(0, total_records, self.BATCH_SIZE):
                batch = staging_records[i:i + self.BATCH_SIZE]
                self._process_batch(batch, upload.organization, upload.uploaded_by, upload)
                
                # Update progress
                progress = min(100, int((i + len(batch)) / total_records * 100))
                upload.processing_progress = progress
                upload.save(update_fields=['processing_progress'])
                
                # Call progress callback if provided
                if self.progress_callback:
                    self.progress_callback(i + len(batch), total_records)
                
                logger.info(f"Processed batch {i//self.BATCH_SIZE + 1}, progress: {progress}%")
            
            # Bulk create conflicts if any were detected
            if self.created_conflicts:
                created_conflicts = MatchingConflict.objects.bulk_create(self.created_conflicts)
                logger.info(f"Created {len(created_conflicts)} matching conflicts for user resolution")

            # Bulk update staging records as processed
            staging_ids = [r.id for r in staging_records]
            ProcurementDataStaging.objects.filter(id__in=staging_ids).update(
                is_processed=True,
                processed_at=timezone.now()
            )
            
            # Update upload status
            upload.status = 'completed' if self.error_count == 0 else 'partial'
            upload.processing_completed_at = timezone.now()
            upload.processed_rows = self.processed_count
            upload.failed_rows = self.error_count
            upload.duplicate_rows = self.duplicate_count
            
            duration = (upload.processing_completed_at - upload.processing_started_at).total_seconds()
            upload.processing_duration_seconds = int(duration)
            upload.save()
            
            logger.info(f"Processing completed in {duration:.2f} seconds")
            
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
                'created_po_lines': len(self.created_po_lines),
                'created_prices': len(self.created_prices),
                'created_conflicts': len(self.created_conflicts),
                'skipped': self.duplicate_count,
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"Fatal error processing upload {upload_id}: {str(e)}")
            if 'upload' in locals():
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_batch(self, batch: List[ProcurementDataStaging],
                      organization: Organization, user, upload: DataUpload):
        """
        Process a batch of records with bulk operations
        """
        # Prepare bulk create lists
        new_suppliers = []
        new_materials = []
        new_pos = []
        new_po_lines = []
        new_prices = []
        
        # Track what needs to be created
        suppliers_to_create = {}  # temp_key -> supplier_data
        materials_to_create = {}  # temp_key -> material_data
        
        # Process each record in batch
        for record in batch:
            try:
                # Skip duplicates
                if record.po_number and record.po_number in self.po_cache:
                    self.duplicate_count += 1
                    continue
                
                # Match or prepare supplier
                supplier = self._fast_match_supplier(record, upload)
                if not supplier and record.supplier_name:
                    # Prepare for bulk create
                    supplier_key = record.supplier_name.upper().strip()
                    if supplier_key not in suppliers_to_create:
                        suppliers_to_create[supplier_key] = {
                            'organization': organization,
                            'code': record.supplier_code or f"AUTO_{uuid.uuid4().hex[:8].upper()}",
                            'name': record.supplier_name,
                            'supplier_type': 'distributor',
                            'status': 'active',  # Set as active by default for uploaded data
                        }
                
                # Match or prepare material
                material = self._fast_match_material(record, upload)
                if not material and record.material_description:
                    # Prepare for bulk create
                    material_key = record.material_description.upper().strip()
                    if material_key not in materials_to_create:
                        materials_to_create[material_key] = {
                            'organization': organization,
                            'code': record.material_code or f"MAT_{uuid.uuid4().hex[:8].upper()}",
                            'name': record.material_description[:255],
                            'description': record.material_description,
                            'material_type': 'raw_material',
                            'status': 'active',
                            'currency': record.currency or 'USD'
                        }
                
                self.processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing record {record.id}: {str(e)}")
                self.error_count += 1
        
        # Bulk create new suppliers
        if suppliers_to_create:
            created = Supplier.objects.bulk_create([
                Supplier(**data) for data in suppliers_to_create.values()
            ])
            self.created_suppliers.extend(created)
            
            # Update cache
            for supplier in created:
                if supplier.code:
                    self.supplier_cache[supplier.code.upper()] = supplier
                self.supplier_name_cache[supplier.name.upper().strip()] = supplier
            
            logger.info(f"Bulk created {len(created)} suppliers")
        
        # Bulk create new materials
        if materials_to_create:
            created = Material.objects.bulk_create([
                Material(**data) for data in materials_to_create.values()
            ])
            self.created_materials.extend(created)
            
            # Update cache
            for material in created:
                if material.code:
                    self.material_cache[material.code.upper()] = material
                desc = (material.description or material.name).upper().strip()
                self.material_desc_cache[desc] = material
            
            logger.info(f"Bulk created {len(created)} materials")
        
        # Now create POs with resolved suppliers/materials
        # Group records by PO number to aggregate totals
        po_groups = {}
        for record in batch:
            if record.po_number and record.po_number not in self.po_cache:
                if record.po_number not in po_groups:
                    po_groups[record.po_number] = {
                        'supplier': self._fast_match_supplier(record),
                        'order_date': record.purchase_date or timezone.now().date(),
                        'delivery_date': record.delivery_date,
                        'currency': record.currency or 'USD',
                        'lines': [],
                        'total': Decimal('0')
                    }
                
                # Add line item data
                material = self._fast_match_material(record)
                if material:
                    line_data = {
                        'material': material,
                        'quantity': record.quantity or Decimal('1'),
                        'unit_price': record.unit_price or Decimal('0'),
                        'total_price': record.total_price or Decimal('0'),
                        'unit_of_measure': record.unit_of_measure or 'EA',
                        'record': record
                    }
                    po_groups[record.po_number]['lines'].append(line_data)
                    po_groups[record.po_number]['total'] += line_data['total_price']
        
        # Bulk create POs
        pos_to_create = []
        for po_number, po_data in po_groups.items():
            po = PurchaseOrder(
                organization=organization,
                po_number=po_number,
                supplier=po_data['supplier'],
                order_date=po_data['order_date'],
                delivery_date=po_data['delivery_date'],
                status='completed',
                total_amount=po_data['total'],
                currency=po_data['currency'],
                created_by=user
            )
            pos_to_create.append(po)
            self.po_cache.add(po_number)
        
        if pos_to_create:
            created_pos = PurchaseOrder.objects.bulk_create(pos_to_create)
            self.created_pos.extend(created_pos)
            logger.info(f"Bulk created {len(created_pos)} purchase orders")
            
            # Create PO lines
            po_lines_to_create = []
            po_map = {po.po_number: po for po in created_pos}
            
            for po_number, po_data in po_groups.items():
                if po_number in po_map:
                    po = po_map[po_number]
                    line_num = 1
                    for line_data in po_data['lines']:
                        po_line = PurchaseOrderLine(
                            purchase_order=po,
                            line_number=str(line_num),  # Line number per PO
                            material=line_data['material'],
                            quantity=line_data['quantity'],
                            unit_price=line_data['unit_price'],
                            total_price=line_data['total_price']
                        )
                        po_lines_to_create.append(po_line)
                        line_num += 1
            
            if po_lines_to_create:
                created_lines = PurchaseOrderLine.objects.bulk_create(po_lines_to_create)
                self.created_po_lines.extend(created_lines)
                logger.info(f"Bulk created {len(created_lines)} purchase order lines")

            # Create price history records for analytics and ML
            price_records_to_create = []
            for record in batch:
                if record.unit_price:
                    # Get the matched/created material and supplier using fast match methods
                    material = self._fast_match_material(record, upload)
                    supplier = self._fast_match_supplier(record, upload)

                    # Create price record if we have the material
                    if material:
                        price_date = record.purchase_date or upload.created_at.date()

                        price = Price(
                            time=timezone.make_aware(
                                datetime.datetime.combine(price_date, datetime.time.min)
                            ),
                            material=material,
                            supplier=supplier,
                            organization=organization,
                            price=record.unit_price,
                            currency=record.currency or 'USD',
                            quantity=record.quantity or 1,
                            unit_of_measure=record.unit_of_measure or 'EA',
                            price_type='historical',
                            source='upload',
                            confidence_score=Decimal('0.95'),
                            metadata={
                                'upload_id': str(upload.id),
                                'po_number': record.po_number,
                                'staging_record_id': str(record.id)
                            }
                        )
                        price_records_to_create.append(price)

            # Bulk create price records
            if price_records_to_create:
                created_prices = Price.objects.bulk_create(price_records_to_create)
                self.created_prices.extend(created_prices)
                logger.info(f"Bulk created {len(created_prices)} price history records")

    def _fast_match_supplier(self, record: ProcurementDataStaging, upload: DataUpload = None) -> Optional[Supplier]:
        """
        Fast supplier matching using cached data with conflict detection
        """
        # Try exact code match from cache
        if record.supplier_code:
            supplier = self.supplier_cache.get(record.supplier_code.upper())
            if supplier:
                return supplier

        # Try exact name match from cache
        if record.supplier_name:
            normalized_name = record.supplier_name.upper().strip()
            supplier = self.supplier_name_cache.get(normalized_name)
            if supplier:
                return supplier

            # Use fuzzy matching with conflict detection
            if self.supplier_names_index:
                # Get top matches for conflict detection
                matches = process.extract(
                    normalized_name,
                    [name for name, _ in self.supplier_names_index],
                    scorer=fuzz.ratio,
                    limit=5
                )

                if matches:
                    best_match = matches[0]
                    similarity_pct = best_match[1] / 100.0

                    # Auto-resolve if very high confidence
                    if similarity_pct >= self.auto_resolve_threshold:
                        for name, supplier in self.supplier_names_index:
                            if name == best_match[0]:
                                self.matched_suppliers.append(supplier)
                                return supplier

                    # Create conflict if in the uncertain range
                    elif similarity_pct >= self.conflict_threshold and upload:
                        # Prepare potential matches data
                        potential_matches = []
                        for match_name, score in matches[:3]:  # Top 3 matches
                            if score >= self.conflict_threshold * 100:
                                for name, supplier in self.supplier_names_index:
                                    if name == match_name:
                                        potential_matches.append({
                                            'id': str(supplier.id),
                                            'name': supplier.name,
                                            'code': supplier.code,
                                            'similarity': score
                                        })
                                        break

                        if potential_matches:
                            # Create conflict record
                            conflict = MatchingConflict(
                                upload=upload,
                                staging_record=record,
                                conflict_type='supplier',
                                incoming_value=record.supplier_name,
                                incoming_code=record.supplier_code,
                                potential_matches=potential_matches,
                                highest_similarity=best_match[1] / 100.0
                            )
                            self.created_conflicts.append(conflict)
                            # Return None to indicate conflict needs resolution
                            return None

        return None
    
    def _fast_match_material(self, record: ProcurementDataStaging, upload: DataUpload = None) -> Optional[Material]:
        """
        Fast material matching using cached data with conflict detection
        """
        # Try exact code match from cache
        if record.material_code:
            material = self.material_cache.get(record.material_code.upper())
            if material:
                return material

        # Try exact description match from cache
        if record.material_description:
            normalized_desc = record.material_description.upper().strip()
            material = self.material_desc_cache.get(normalized_desc)
            if material:
                return material

            # Use fuzzy matching with conflict detection
            if self.material_descs_index:
                # Get top matches for conflict detection
                matches = process.extract(
                    normalized_desc,
                    [desc for desc, _ in self.material_descs_index],
                    scorer=fuzz.token_sort_ratio,
                    limit=5
                )

                if matches:
                    best_match = matches[0]
                    similarity_pct = best_match[1] / 100.0

                    # Auto-resolve if very high confidence
                    if similarity_pct >= self.auto_resolve_threshold:
                        for desc, material in self.material_descs_index:
                            if desc == best_match[0]:
                                self.matched_materials.append(material)
                                return material

                    # Create conflict if in the uncertain range
                    elif similarity_pct >= self.conflict_threshold and upload:
                        # Prepare potential matches data
                        potential_matches = []
                        for match_desc, score in matches[:3]:  # Top 3 matches
                            if score >= self.conflict_threshold * 100:
                                for desc, material in self.material_descs_index:
                                    if desc == match_desc:
                                        potential_matches.append({
                                            'id': str(material.id),
                                            'name': material.name,
                                            'code': material.code,
                                            'similarity': score
                                        })
                                        break

                        if potential_matches:
                            # Create conflict record
                            conflict = MatchingConflict(
                                upload=upload,
                                staging_record=record,
                                conflict_type='material',
                                incoming_value=record.material_description,
                                incoming_code=record.material_code,
                                potential_matches=potential_matches,
                                highest_similarity=best_match[1] / 100.0
                            )
                            self.created_conflicts.append(conflict)
                            # Return None to indicate conflict needs resolution
                            return None

        return None
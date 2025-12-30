# PHASE 4-5: ENTERPRISE FEATURES & ADVANCED ANALYTICS
## Detailed Technical Implementation Plan
### Q2-Q3 2025

---

## PHASE 4: ENTERPRISE FEATURES
### Q2 2025 (April - June)

## 4.1 ERP INTEGRATION SUITE
### Week 1-4: Enterprise System Connectors

#### 4.1.1 SAP Integration

**File: `django_app/apps/integrations/sap/connector.py`**
```python
import requests
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
from django.conf import settings
import zeep
from zeep.transports import Transport

logger = logging.getLogger(__name__)

class SAPConnector:
    """SAP ERP Integration Connector"""

    def __init__(self):
        self.base_url = settings.SAP_BASE_URL
        self.client_id = settings.SAP_CLIENT_ID
        self.client_secret = settings.SAP_CLIENT_SECRET
        self.system_id = settings.SAP_SYSTEM_ID
        self.session = requests.Session()
        self.soap_client = None
        self.token = None

    def authenticate(self) -> bool:
        """Authenticate with SAP system"""
        try:
            auth_url = f"{self.base_url}/oauth/token"
            response = self.session.post(
                auth_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
            )

            if response.status_code == 200:
                self.token = response.json()['access_token']
                self.session.headers.update({
                    'Authorization': f'Bearer {self.token}'
                })

                # Initialize SOAP client for certain operations
                wsdl_url = f"{self.base_url}/sap/bc/srt/wsdl/flv_10002A111AD1/bndg_url/sap/bc/srt/rfc/sap/zpricing_agent/001/zpricing/zpricing_binding?sap-client={self.system_id}"
                self.soap_client = zeep.Client(wsdl_url, transport=Transport(session=self.session))

                return True
            return False

        except Exception as e:
            logger.error(f"SAP authentication failed: {e}")
            return False

    async def sync_purchase_orders(self, date_from: datetime = None) -> List[Dict]:
        """Sync purchase orders from SAP"""
        try:
            # Build OData query
            query_params = {
                "$select": "PurchaseOrder,Supplier,PurchaseOrderDate,DocumentCurrency,PurchaseOrderNetAmount",
                "$expand": "to_PurchaseOrderItem",
                "$top": 1000
            }

            if date_from:
                query_params["$filter"] = f"PurchaseOrderDate ge datetime'{date_from.isoformat()}'"

            # Call SAP OData API
            response = self.session.get(
                f"{self.base_url}/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder",
                params=query_params
            )

            if response.status_code == 200:
                data = response.json()
                purchase_orders = []

                for po in data.get('d', {}).get('results', []):
                    # Process PO header
                    po_data = {
                        'po_number': po['PurchaseOrder'],
                        'supplier': po['Supplier'],
                        'order_date': po['PurchaseOrderDate'],
                        'currency': po['DocumentCurrency'],
                        'total_amount': po['PurchaseOrderNetAmount'],
                        'lines': []
                    }

                    # Process PO lines
                    for item in po.get('to_PurchaseOrderItem', {}).get('results', []):
                        line_data = {
                            'line_number': item['PurchaseOrderItem'],
                            'material': item['Material'],
                            'material_text': item['PurchaseOrderItemText'],
                            'quantity': item['OrderQuantity'],
                            'unit': item['OrderPriceUnit'],
                            'unit_price': item['NetPriceAmount'],
                            'delivery_date': item['ScheduleLineDeliveryDate']
                        }
                        po_data['lines'].append(line_data)

                    purchase_orders.append(po_data)

                return purchase_orders

            logger.error(f"SAP API returned status {response.status_code}")
            return []

        except Exception as e:
            logger.error(f"Error syncing SAP purchase orders: {e}")
            return []

    async def sync_materials(self) -> List[Dict]:
        """Sync material master data from SAP"""
        try:
            # Call SAP Material API
            response = self.session.get(
                f"{self.base_url}/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_Product",
                params={
                    "$select": "Product,ProductDescription,BaseUnit,ProductGroup,ProductType",
                    "$top": 5000
                }
            )

            if response.status_code == 200:
                data = response.json()
                materials = []

                for mat in data.get('d', {}).get('results', []):
                    material_data = {
                        'material_code': mat['Product'],
                        'description': mat['ProductDescription'],
                        'unit': mat['BaseUnit'],
                        'group': mat['ProductGroup'],
                        'type': mat['ProductType']
                    }
                    materials.append(material_data)

                return materials

            return []

        except Exception as e:
            logger.error(f"Error syncing SAP materials: {e}")
            return []

    async def sync_suppliers(self) -> List[Dict]:
        """Sync vendor master data from SAP"""
        try:
            # Call SAP Supplier API
            response = self.session.get(
                f"{self.base_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_Supplier",
                params={
                    "$select": "Supplier,SupplierName,SupplierAccountGroup,Country,Region",
                    "$top": 5000
                }
            )

            if response.status_code == 200:
                data = response.json()
                suppliers = []

                for sup in data.get('d', {}).get('results', []):
                    supplier_data = {
                        'supplier_code': sup['Supplier'],
                        'name': sup['SupplierName'],
                        'account_group': sup['SupplierAccountGroup'],
                        'country': sup['Country'],
                        'region': sup['Region']
                    }
                    suppliers.append(supplier_data)

                return suppliers

            return []

        except Exception as e:
            logger.error(f"Error syncing SAP suppliers: {e}")
            return []

    async def create_purchase_requisition(self, requisition_data: Dict) -> Optional[str]:
        """Create purchase requisition in SAP"""
        try:
            # Use SOAP for creating PR
            if not self.soap_client:
                logger.error("SOAP client not initialized")
                return None

            # Call BAPI_PR_CREATE
            result = self.soap_client.service.BAPI_PR_CREATE(
                PRHEADER={
                    'PR_TYPE': requisition_data.get('pr_type', 'NB'),
                    'CURRENCY': requisition_data.get('currency', 'USD'),
                    'DOC_DATE': datetime.now().strftime('%Y%m%d')
                },
                PRITEM=[
                    {
                        'PREQ_ITEM': str(i+1).zfill(5),
                        'MATERIAL': item['material'],
                        'QUANTITY': item['quantity'],
                        'UNIT': item['unit'],
                        'DELIV_DATE': item['delivery_date'],
                        'PLANT': item.get('plant', '1000')
                    }
                    for i, item in enumerate(requisition_data.get('items', []))
                ]
            )

            if result['RETURN'][0]['TYPE'] == 'S':
                pr_number = result['PURCHASEREQUISITION']
                logger.info(f"Created SAP PR: {pr_number}")
                return pr_number
            else:
                logger.error(f"SAP PR creation failed: {result['RETURN'][0]['MESSAGE']}")
                return None

        except Exception as e:
            logger.error(f"Error creating SAP PR: {e}")
            return None

    async def update_contract_price(self, contract_number: str, new_price: float) -> bool:
        """Update contract price in SAP"""
        try:
            # Build update payload
            payload = {
                'ContractNumber': contract_number,
                'NetPrice': new_price,
                'ValidFrom': datetime.now().isoformat()
            }

            response = self.session.patch(
                f"{self.base_url}/sap/opu/odata/sap/API_PURCHASECONTRACT_PROCESS_SRV/A_PurchaseContract('{contract_number}')",
                json=payload
            )

            return response.status_code == 204

        except Exception as e:
            logger.error(f"Error updating SAP contract: {e}")
            return False
```

#### 4.1.2 Oracle EBS Integration

**File: `django_app/apps/integrations/oracle/connector.py`**
```python
import cx_Oracle
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class OracleEBSConnector:
    """Oracle E-Business Suite Integration Connector"""

    def __init__(self):
        self.db_host = settings.ORACLE_HOST
        self.db_port = settings.ORACLE_PORT
        self.db_service = settings.ORACLE_SERVICE
        self.db_user = settings.ORACLE_USER
        self.db_password = settings.ORACLE_PASSWORD
        self.rest_base_url = settings.ORACLE_REST_URL
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        """Establish database connection to Oracle EBS"""
        try:
            dsn = cx_Oracle.makedsn(
                self.db_host,
                self.db_port,
                service_name=self.db_service
            )

            self.connection = cx_Oracle.connect(
                user=self.db_user,
                password=self.db_password,
                dsn=dsn
            )

            self.cursor = self.connection.cursor()
            logger.info("Connected to Oracle EBS")
            return True

        except Exception as e:
            logger.error(f"Oracle connection failed: {e}")
            return False

    async def sync_purchase_orders(self, date_from: datetime = None) -> List[Dict]:
        """Sync purchase orders from Oracle EBS"""
        try:
            query = """
                SELECT
                    poh.po_header_id,
                    poh.segment1 as po_number,
                    poh.vendor_id,
                    pov.vendor_name,
                    poh.currency_code,
                    poh.rate,
                    poh.creation_date,
                    pol.po_line_id,
                    pol.line_num,
                    pol.item_id,
                    msi.segment1 as item_number,
                    pol.item_description,
                    pol.quantity,
                    pol.unit_price,
                    pol.unit_meas_lookup_code,
                    pll.need_by_date
                FROM
                    po_headers_all poh
                    JOIN po_lines_all pol ON poh.po_header_id = pol.po_header_id
                    JOIN po_line_locations_all pll ON pol.po_line_id = pll.po_line_id
                    JOIN po_vendors pov ON poh.vendor_id = pov.vendor_id
                    LEFT JOIN mtl_system_items_b msi ON pol.item_id = msi.inventory_item_id
                WHERE
                    poh.type_lookup_code = 'STANDARD'
                    AND poh.authorization_status = 'APPROVED'
            """

            if date_from:
                query += f" AND poh.creation_date >= TO_DATE('{date_from.strftime('%Y-%m-%d')}', 'YYYY-MM-DD')"

            query += " ORDER BY poh.po_header_id, pol.line_num"

            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            # Process results into structured format
            purchase_orders = {}
            for row in rows:
                po_id = row[0]

                if po_id not in purchase_orders:
                    purchase_orders[po_id] = {
                        'po_number': row[1],
                        'vendor_id': row[2],
                        'vendor_name': row[3],
                        'currency': row[4],
                        'exchange_rate': row[5],
                        'creation_date': row[6],
                        'lines': []
                    }

                line_data = {
                    'line_id': row[7],
                    'line_number': row[8],
                    'item_id': row[9],
                    'item_number': row[10],
                    'description': row[11],
                    'quantity': row[12],
                    'unit_price': row[13],
                    'unit': row[14],
                    'need_by_date': row[15]
                }
                purchase_orders[po_id]['lines'].append(line_data)

            return list(purchase_orders.values())

        except Exception as e:
            logger.error(f"Error syncing Oracle purchase orders: {e}")
            return []

    async def sync_materials(self) -> List[Dict]:
        """Sync item master from Oracle EBS"""
        try:
            query = """
                SELECT
                    msi.inventory_item_id,
                    msi.segment1 as item_number,
                    msi.description,
                    msi.primary_uom_code,
                    mic.segment1 as category,
                    msi.list_price_per_unit,
                    msi.item_type,
                    msi.purchasing_enabled_flag,
                    msi.customer_order_enabled_flag
                FROM
                    mtl_system_items_b msi
                    LEFT JOIN mtl_item_categories mic ON msi.inventory_item_id = mic.inventory_item_id
                WHERE
                    msi.organization_id = :org_id
                    AND msi.enabled_flag = 'Y'
            """

            self.cursor.execute(query, org_id=settings.ORACLE_ORG_ID)
            rows = self.cursor.fetchall()

            materials = []
            for row in rows:
                material_data = {
                    'item_id': row[0],
                    'item_number': row[1],
                    'description': row[2],
                    'uom': row[3],
                    'category': row[4],
                    'list_price': row[5],
                    'item_type': row[6],
                    'purchasable': row[7] == 'Y',
                    'sellable': row[8] == 'Y'
                }
                materials.append(material_data)

            return materials

        except Exception as e:
            logger.error(f"Error syncing Oracle materials: {e}")
            return []

    async def sync_suppliers(self) -> List[Dict]:
        """Sync vendor master from Oracle EBS"""
        try:
            query = """
                SELECT
                    pov.vendor_id,
                    pov.segment1 as vendor_number,
                    pov.vendor_name,
                    pov.vendor_type_lookup_code,
                    povs.vendor_site_id,
                    povs.vendor_site_code,
                    povs.address_line1,
                    povs.city,
                    povs.state,
                    povs.country,
                    povs.zip,
                    pov.payment_method_lookup_code,
                    pov.payment_priority,
                    pov.terms_id
                FROM
                    po_vendors pov
                    JOIN po_vendor_sites_all povs ON pov.vendor_id = povs.vendor_id
                WHERE
                    pov.enabled_flag = 'Y'
                    AND povs.inactive_date IS NULL
            """

            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            suppliers = []
            for row in rows:
                supplier_data = {
                    'vendor_id': row[0],
                    'vendor_number': row[1],
                    'vendor_name': row[2],
                    'vendor_type': row[3],
                    'site_id': row[4],
                    'site_code': row[5],
                    'address': row[6],
                    'city': row[7],
                    'state': row[8],
                    'country': row[9],
                    'postal_code': row[10],
                    'payment_method': row[11],
                    'payment_priority': row[12],
                    'payment_terms_id': row[13]
                }
                suppliers.append(supplier_data)

            return suppliers

        except Exception as e:
            logger.error(f"Error syncing Oracle suppliers: {e}")
            return []

    async def create_requisition(self, requisition_data: Dict) -> Optional[int]:
        """Create requisition in Oracle EBS"""
        try:
            # Call Oracle API or stored procedure
            self.cursor.callproc(
                'PO_REQUISITIONS_PKG.CREATE_REQUISITION',
                [
                    requisition_data.get('description'),
                    requisition_data.get('requestor_id'),
                    requisition_data.get('need_by_date'),
                    requisition_data.get('charge_account_id')
                ]
            )

            # Get the created requisition ID
            self.cursor.execute(
                "SELECT PO_REQUISITION_HEADERS_S.CURRVAL FROM DUAL"
            )
            req_id = self.cursor.fetchone()[0]

            # Add requisition lines
            for line in requisition_data.get('lines', []):
                self.cursor.execute("""
                    INSERT INTO po_requisition_lines_all (
                        requisition_header_id,
                        line_num,
                        item_id,
                        quantity,
                        unit_price,
                        need_by_date
                    ) VALUES (:1, :2, :3, :4, :5, :6)
                """, (
                    req_id,
                    line['line_number'],
                    line['item_id'],
                    line['quantity'],
                    line['unit_price'],
                    line['need_by_date']
                ))

            self.connection.commit()
            logger.info(f"Created Oracle requisition: {req_id}")
            return req_id

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error creating Oracle requisition: {e}")
            return None

    def disconnect(self):
        """Close Oracle database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Disconnected from Oracle EBS")
```

#### 4.1.3 Microsoft Dynamics 365 Integration

**File: `django_app/apps/integrations/dynamics/connector.py`**
```python
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from django.conf import settings
from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)

class Dynamics365Connector:
    """Microsoft Dynamics 365 Integration Connector"""

    def __init__(self):
        self.tenant_id = settings.DYNAMICS_TENANT_ID
        self.client_id = settings.DYNAMICS_CLIENT_ID
        self.client_secret = settings.DYNAMICS_CLIENT_SECRET
        self.resource_url = settings.DYNAMICS_RESOURCE_URL
        self.api_version = "v9.2"
        self.credential = None
        self.session = requests.Session()
        self.base_url = f"{self.resource_url}/api/data/{self.api_version}"

    def authenticate(self) -> bool:
        """Authenticate with Dynamics 365"""
        try:
            self.credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            token = self.credential.get_token(f"{self.resource_url}/.default")
            self.session.headers.update({
                'Authorization': f'Bearer {token.token}',
                'OData-MaxVersion': '4.0',
                'OData-Version': '4.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })

            # Test connection
            response = self.session.get(f"{self.base_url}/WhoAmI")
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Dynamics 365 authentication failed: {e}")
            return False

    async def sync_purchase_orders(self, date_from: datetime = None) -> List[Dict]:
        """Sync purchase orders from Dynamics 365"""
        try:
            # Build OData query
            query = "$select=purchaseorderid,name,vendorid,totalamount,currencyid,createdon&$expand=PurchaseOrder_PurchaseOrderDetail"

            if date_from:
                query += f"&$filter=createdon ge {date_from.isoformat()}"

            response = self.session.get(
                f"{self.base_url}/purchaseorders?{query}"
            )

            if response.status_code == 200:
                data = response.json()
                purchase_orders = []

                for po in data.get('value', []):
                    po_data = {
                        'po_id': po['purchaseorderid'],
                        'po_number': po['name'],
                        'vendor_id': po['_vendorid_value'],
                        'total_amount': po['totalamount'],
                        'currency': po['_currencyid_value'],
                        'created_date': po['createdon'],
                        'lines': []
                    }

                    # Get PO details
                    details_response = self.session.get(
                        f"{self.base_url}/purchaseorderdetails?$filter=_purchaseorderid_value eq {po['purchaseorderid']}"
                    )

                    if details_response.status_code == 200:
                        details = details_response.json()
                        for detail in details.get('value', []):
                            line_data = {
                                'line_id': detail['purchaseorderdetailid'],
                                'product_id': detail['_productid_value'],
                                'quantity': detail['quantity'],
                                'unit_price': detail['priceperunit'],
                                'extended_amount': detail['extendedamount']
                            }
                            po_data['lines'].append(line_data)

                    purchase_orders.append(po_data)

                return purchase_orders

            return []

        except Exception as e:
            logger.error(f"Error syncing Dynamics purchase orders: {e}")
            return []

    async def sync_products(self) -> List[Dict]:
        """Sync products from Dynamics 365"""
        try:
            response = self.session.get(
                f"{self.base_url}/products?$select=productid,productnumber,name,description,defaultuomid,currentcost"
            )

            if response.status_code == 200:
                data = response.json()
                products = []

                for product in data.get('value', []):
                    product_data = {
                        'product_id': product['productid'],
                        'product_number': product['productnumber'],
                        'name': product['name'],
                        'description': product.get('description', ''),
                        'unit_id': product['_defaultuomid_value'],
                        'current_cost': product.get('currentcost', 0)
                    }
                    products.append(product_data)

                return products

            return []

        except Exception as e:
            logger.error(f"Error syncing Dynamics products: {e}")
            return []

    async def create_purchase_order(self, po_data: Dict) -> Optional[str]:
        """Create purchase order in Dynamics 365"""
        try:
            # Create PO header
            po_payload = {
                'name': po_data['po_number'],
                'vendorid@odata.bind': f"/accounts({po_data['vendor_id']})",
                'currencyid@odata.bind': f"/transactioncurrencies({po_data['currency_id']})",
                'requesteddeliverydate': po_data['delivery_date'],
                'description': po_data.get('description', '')
            }

            response = self.session.post(
                f"{self.base_url}/purchaseorders",
                json=po_payload
            )

            if response.status_code == 201:
                created_po = response.json()
                po_id = created_po['purchaseorderid']

                # Create PO lines
                for line in po_data.get('lines', []):
                    line_payload = {
                        'purchaseorderid@odata.bind': f"/purchaseorders({po_id})",
                        'productid@odata.bind': f"/products({line['product_id']})",
                        'quantity': line['quantity'],
                        'priceperunit': line['unit_price'],
                        'extendedamount': line['quantity'] * line['unit_price']
                    }

                    line_response = self.session.post(
                        f"{self.base_url}/purchaseorderdetails",
                        json=line_payload
                    )

                    if line_response.status_code != 201:
                        logger.error(f"Failed to create PO line: {line_response.text}")

                logger.info(f"Created Dynamics PO: {po_id}")
                return po_id

            return None

        except Exception as e:
            logger.error(f"Error creating Dynamics PO: {e}")
            return None
```

## 4.2 SUPPLIER COLLABORATION PORTAL
### Week 5-8: Portal Development

#### 4.2.1 Supplier Portal Backend

**File: `django_app/apps/supplier_portal/models.py`**
```python
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from apps.core.models import BaseModel
from apps.procurement.models import Supplier

class SupplierUser(AbstractUser):
    """User model for supplier portal access"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=50, choices=[
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('sales', 'Sales Representative'),
        ('viewer', 'Viewer')
    ])
    is_primary_contact = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'supplier_users'

class SupplierDocument(BaseModel):
    """Documents uploaded by suppliers"""

    DOCUMENT_TYPES = [
        ('certificate', 'Certificate'),
        ('insurance', 'Insurance'),
        ('compliance', 'Compliance'),
        ('catalog', 'Product Catalog'),
        ('quote', 'Quotation'),
        ('contract', 'Contract'),
        ('other', 'Other')
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(SupplierUser, on_delete=models.SET_NULL, null=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='supplier_documents/%Y/%m/')
    file_size = models.IntegerField()
    mime_type = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'supplier_documents'
        ordering = ['-created_at']

class RFQResponse(BaseModel):
    """Supplier responses to RFQs"""

    rfq = models.ForeignKey('procurement.RFQ', on_delete=models.CASCADE, related_name='responses')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    submitted_by = models.ForeignKey(SupplierUser, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn')
    ])
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    validity_days = models.IntegerField(default=30)
    delivery_days = models.IntegerField()
    payment_terms = models.CharField(max_length=100)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'rfq_responses'
        unique_together = [['rfq', 'supplier']]

class RFQResponseLine(BaseModel):
    """Line items in RFQ responses"""

    response = models.ForeignKey(RFQResponse, on_delete=models.CASCADE, related_name='lines')
    rfq_line = models.ForeignKey('procurement.RFQLine', on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    quantity = models.DecimalField(max_digits=15, decimal_places=3)
    lead_time_days = models.IntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'rfq_response_lines'

class SupplierMessage(BaseModel):
    """Communication between buyers and suppliers"""

    thread = models.ForeignKey('SupplierMessageThread', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(SupplierUser, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    buyer_sender = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='supplier_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'supplier_messages'
        ordering = ['created_at']

class SupplierMessageThread(BaseModel):
    """Message threads between buyers and suppliers"""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='message_threads')
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=[
        ('rfq', 'RFQ Discussion'),
        ('order', 'Order Related'),
        ('payment', 'Payment Query'),
        ('quality', 'Quality Issue'),
        ('general', 'General Inquiry')
    ])
    related_rfq = models.ForeignKey('procurement.RFQ', on_delete=models.SET_NULL, null=True, blank=True)
    related_order = models.ForeignKey('procurement.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('open', 'Open'),
        ('pending', 'Pending Response'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], default='open')
    priority = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')

    class Meta:
        db_table = 'supplier_message_threads'
        ordering = ['-updated_at']
```

#### 4.2.2 Supplier Portal Views

**File: `django_app/apps/supplier_portal/views.py`**
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import (
    SupplierUser, SupplierDocument, RFQResponse,
    RFQResponseLine, SupplierMessage, SupplierMessageThread
)
from .forms import RFQResponseForm, DocumentUploadForm, MessageForm
from apps.procurement.models import RFQ, PurchaseOrder
from apps.pricing.models import Price

class SupplierDashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard for supplier portal"""
    template_name = 'supplier_portal/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        supplier = user.supplier

        # Key metrics
        context['metrics'] = {
            'active_rfqs': RFQ.objects.filter(
                suppliers=supplier,
                status='open',
                closing_date__gte=timezone.now()
            ).count(),

            'pending_orders': PurchaseOrder.objects.filter(
                supplier=supplier,
                status='pending'
            ).count(),

            'total_revenue': PurchaseOrder.objects.filter(
                supplier=supplier,
                status='completed',
                created_at__gte=timezone.now() - timedelta(days=365)
            ).aggregate(total=Sum('total_amount'))['total'] or 0,

            'performance_score': self._calculate_performance_score(supplier),

            'unread_messages': SupplierMessage.objects.filter(
                thread__supplier=supplier,
                is_read=False,
                buyer_sender__isnull=False
            ).count()
        }

        # Recent RFQs
        context['recent_rfqs'] = RFQ.objects.filter(
            suppliers=supplier,
            status='open'
        ).order_by('-created_at')[:5]

        # Recent orders
        context['recent_orders'] = PurchaseOrder.objects.filter(
            supplier=supplier
        ).order_by('-created_at')[:5]

        # Performance trends
        context['performance_data'] = self._get_performance_trends(supplier)

        return context

    def _calculate_performance_score(self, supplier):
        """Calculate supplier performance score"""
        scores = {
            'on_time_delivery': 0,
            'quality_rating': 0,
            'response_time': 0,
            'price_competitiveness': 0
        }

        # On-time delivery
        completed_orders = PurchaseOrder.objects.filter(
            supplier=supplier,
            status='completed'
        ).count()

        if completed_orders > 0:
            on_time = PurchaseOrder.objects.filter(
                supplier=supplier,
                status='completed',
                actual_delivery_date__lte=models.F('expected_delivery_date')
            ).count()
            scores['on_time_delivery'] = (on_time / completed_orders) * 100

        # Quality rating (from feedback)
        # Implement based on quality feedback model

        # Response time
        responses = RFQResponse.objects.filter(supplier=supplier)
        if responses.exists():
            avg_response_time = responses.aggregate(
                avg_time=Avg(models.F('created_at') - models.F('rfq__created_at'))
            )['avg_time']
            # Convert to score (faster = higher score)
            if avg_response_time:
                hours = avg_response_time.total_seconds() / 3600
                scores['response_time'] = max(0, 100 - (hours * 2))  # Lose 2 points per hour

        # Price competitiveness
        # Compare average prices with market
        # Implement based on pricing analytics

        # Calculate weighted average
        weights = {
            'on_time_delivery': 0.35,
            'quality_rating': 0.30,
            'response_time': 0.20,
            'price_competitiveness': 0.15
        }

        total_score = sum(scores[key] * weights[key] for key in scores)
        return round(total_score, 1)

class RFQListView(LoginRequiredMixin, ListView):
    """List of RFQs for supplier"""
    model = RFQ
    template_name = 'supplier_portal/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 20

    def get_queryset(self):
        supplier = self.request.user.supplier
        queryset = RFQ.objects.filter(suppliers=supplier)

        # Filtering
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(rfq_number__icontains=search) |
                Q(title__icontains=search)
            )

        return queryset.order_by('-created_at')

class RFQResponseView(LoginRequiredMixin, CreateView):
    """Submit response to RFQ"""
    model = RFQResponse
    form_class = RFQResponseForm
    template_name = 'supplier_portal/rfq_response.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rfq'] = get_object_or_404(RFQ, pk=self.kwargs['rfq_id'])
        return context

    def form_valid(self, form):
        rfq = get_object_or_404(RFQ, pk=self.kwargs['rfq_id'])
        form.instance.rfq = rfq
        form.instance.supplier = self.request.user.supplier
        form.instance.submitted_by = self.request.user
        form.instance.status = 'submitted'

        response = form.save()

        # Create line items
        for rfq_line in rfq.lines.all():
            line_data = self.request.POST.get(f'line_{rfq_line.id}')
            if line_data:
                RFQResponseLine.objects.create(
                    response=response,
                    rfq_line=rfq_line,
                    unit_price=line_data['unit_price'],
                    quantity=line_data['quantity'],
                    lead_time_days=line_data['lead_time']
                )

        messages.success(self.request, 'RFQ response submitted successfully!')
        return redirect('supplier_portal:rfq_list')
```

## 4.3 WEBSOCKET REAL-TIME UPDATES
### Week 9-12: Live Data Streaming

#### 4.3.1 WebSocket Server

**File: `django_app/apps/realtime/websocket_server.py`**
```python
import asyncio
import json
import logging
from typing import Dict, Set
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class PricingWebSocket(AsyncWebsocketConsumer):
    """WebSocket handler for real-time pricing updates"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.organization = None
        self.subscriptions = set()
        self.redis_client = None

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Get user's organization
        self.organization = await self.get_user_organization()

        # Accept connection
        await self.accept()

        # Initialize Redis subscription
        self.redis_client = await redis.create_redis_pool('redis://localhost:6379')

        # Join organization group
        await self.channel_layer.group_add(
            f"org_{self.organization.id}",
            self.channel_name
        )

        # Send initial data
        await self.send_initial_data()

        logger.info(f"WebSocket connected: {self.user.username}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave organization group
        if self.organization:
            await self.channel_layer.group_discard(
                f"org_{self.organization.id}",
                self.channel_name
            )

        # Close Redis connection
        if self.redis_client:
            self.redis_client.close()
            await self.redis_client.wait_closed()

        logger.info(f"WebSocket disconnected: {self.user.username if self.user else 'Unknown'}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'subscribe':
                await self.handle_subscribe(data)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(data)
            elif message_type == 'request':
                await self.handle_request(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self.send_error(str(e))

    async def handle_subscribe(self, data):
        """Handle subscription requests"""
        channels = data.get('channels', [])

        for channel in channels:
            if channel not in self.subscriptions:
                self.subscriptions.add(channel)

                # Join channel group
                await self.channel_layer.group_add(
                    channel,
                    self.channel_name
                )

                # Start listening to Redis channel
                await self.redis_subscribe(channel)

        await self.send_json({
            'type': 'subscription_confirmed',
            'channels': list(self.subscriptions)
        })

    async def handle_unsubscribe(self, data):
        """Handle unsubscription requests"""
        channels = data.get('channels', [])

        for channel in channels:
            if channel in self.subscriptions:
                self.subscriptions.remove(channel)

                # Leave channel group
                await self.channel_layer.group_discard(
                    channel,
                    self.channel_name
                )

        await self.send_json({
            'type': 'unsubscription_confirmed',
            'channels': list(self.subscriptions)
        })

    async def handle_request(self, data):
        """Handle data requests"""
        request_type = data.get('request_type')

        if request_type == 'price_update':
            await self.send_price_update(data.get('material_id'))
        elif request_type == 'anomaly_alert':
            await self.send_anomaly_alerts()
        elif request_type == 'analytics_refresh':
            await self.send_analytics_update()

    async def send_initial_data(self):
        """Send initial data upon connection"""
        # Get latest prices
        prices = await self.get_latest_prices()

        # Get active alerts
        alerts = await self.get_active_alerts()

        await self.send_json({
            'type': 'initial_data',
            'data': {
                'prices': prices,
                'alerts': alerts,
                'timestamp': datetime.now().isoformat()
            }
        })

    async def redis_subscribe(self, channel):
        """Subscribe to Redis channel for real-time updates"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)

        async def reader():
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self.send_json({
                        'type': 'channel_update',
                        'channel': channel,
                        'data': json.loads(message['data'])
                    })

        asyncio.create_task(reader())

    # Channel layer message handlers
    async def price_update(self, event):
        """Handle price update messages"""
        await self.send_json({
            'type': 'price_update',
            'data': event['data']
        })

    async def anomaly_detected(self, event):
        """Handle anomaly detection messages"""
        await self.send_json({
            'type': 'anomaly_alert',
            'data': event['data']
        })

    async def analytics_update(self, event):
        """Handle analytics update messages"""
        await self.send_json({
            'type': 'analytics_update',
            'data': event['data']
        })

    # Helper methods
    async def send_json(self, data):
        """Send JSON data to client"""
        await self.send(text_data=json.dumps(data))

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send_json({
            'type': 'error',
            'message': error_message
        })

    @database_sync_to_async
    def get_user_organization(self):
        """Get user's organization"""
        return self.user.profile.organization

    @database_sync_to_async
    def get_latest_prices(self):
        """Get latest price data"""
        from apps.pricing.models import Price

        prices = Price.objects.filter(
            organization=self.organization
        ).select_related('material', 'supplier').order_by('-created_at')[:100]

        return [{
            'material': price.material.name,
            'supplier': price.supplier.name,
            'price': float(price.price),
            'currency': price.currency,
            'timestamp': price.created_at.isoformat()
        } for price in prices]

    @database_sync_to_async
    def get_active_alerts(self):
        """Get active alerts"""
        from apps.analytics.models import Alert

        alerts = Alert.objects.filter(
            organization=self.organization,
            status='active'
        ).order_by('-created_at')[:50]

        return [{
            'id': str(alert.id),
            'type': alert.alert_type,
            'severity': alert.severity,
            'message': alert.message,
            'timestamp': alert.created_at.isoformat()
        } for alert in alerts]
```

---

## PHASE 5: ADVANCED ANALYTICS
### Q3 2025 (July - September)

## 5.1 PREDICTIVE SPEND ANALYTICS
### Week 1-4: Forecasting Engine

#### 5.1.1 Spend Predictor Model

**File: `fastapi_ml/models/spend_predictor.py`**
```python
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class SpendPredictor:
    """Predictive spend analytics model"""

    def __init__(self):
        self.models = {}
        self.feature_importance = {}
        self.version = "1.0.0"

    async def initialize(self):
        """Initialize spend prediction models"""
        # Initialize ensemble models
        self.models['rf'] = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        self.models['gb'] = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )

        self.models['xgb'] = xgb.XGBRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )

        logger.info("Spend predictor initialized")

    async def predict_spend(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict future spend"""
        try:
            # Extract parameters
            category = data.get('category', 'all')
            horizon_months = data.get('horizon_months', 12)
            scenario = data.get('scenario', 'baseline')

            # Get historical spend data
            historical_spend = await self._get_historical_spend(category)

            # Create features
            features = self._create_features(historical_spend)

            # Make predictions
            predictions = {}
            for model_name, model in self.models.items():
                if hasattr(model, 'predict'):
                    pred = model.predict(features)
                    predictions[model_name] = pred

            # Ensemble predictions
            ensemble_prediction = np.mean(list(predictions.values()), axis=0)

            # Apply scenario adjustments
            adjusted_prediction = self._apply_scenario(ensemble_prediction, scenario)

            # Generate forecast
            forecast = self._generate_forecast(
                adjusted_prediction,
                horizon_months,
                historical_spend
            )

            return {
                'forecast': forecast,
                'confidence_interval': self._calculate_confidence_interval(predictions),
                'drivers': self._identify_spend_drivers(features),
                'recommendations': self._generate_recommendations(forecast),
                'scenario': scenario,
                'model_version': self.version
            }

        except Exception as e:
            logger.error(f"Spend prediction error: {e}")
            raise

    def _create_features(self, historical_data: pd.DataFrame) -> np.ndarray:
        """Create features for spend prediction"""
        features = []

        # Time-based features
        features.extend([
            historical_data['month'].values,
            historical_data['quarter'].values,
            historical_data['year'].values
        ])

        # Lag features
        for lag in [1, 3, 6, 12]:
            features.append(historical_data['spend'].shift(lag).fillna(0).values)

        # Rolling statistics
        for window in [3, 6, 12]:
            features.append(historical_data['spend'].rolling(window).mean().fillna(0).values)
            features.append(historical_data['spend'].rolling(window).std().fillna(0).values)

        # Economic indicators
        features.extend([
            historical_data.get('inflation_rate', 0).values,
            historical_data.get('exchange_rate', 1).values,
            historical_data.get('market_index', 100).values
        ])

        return np.array(features).T

    def _apply_scenario(self, prediction: np.ndarray, scenario: str) -> np.ndarray:
        """Apply scenario adjustments to predictions"""
        adjustments = {
            'baseline': 1.0,
            'optimistic': 0.9,  # 10% reduction
            'pessimistic': 1.15,  # 15% increase
            'aggressive_savings': 0.8,  # 20% reduction target
            'growth': 1.2  # 20% growth scenario
        }

        factor = adjustments.get(scenario, 1.0)
        return prediction * factor
```

## 5.2 MARKET INTELLIGENCE
### Week 5-8: External Data Integration

#### 5.2.1 Market Data Aggregator

**File: `django_app/apps/market_intelligence/aggregator.py`**
```python
import requests
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import aiohttp
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MarketIntelligenceAggregator:
    """Aggregate market data from multiple sources"""

    def __init__(self):
        self.sources = {
            'lme': LMEDataSource(),
            'cme': CMEDataSource(),
            'bloomberg': BloombergDataSource(),
            'reuters': ReutersDataSource(),
            'custom_feeds': CustomFeedSource()
        }

    async def aggregate_market_data(self) -> Dict[str, Any]:
        """Aggregate data from all sources"""
        tasks = []
        for source_name, source in self.sources.items():
            tasks.append(self._fetch_source_data(source_name, source))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated_data = {
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }

        for source_name, data in zip(self.sources.keys(), results):
            if isinstance(data, Exception):
                logger.error(f"Error fetching {source_name}: {data}")
                aggregated_data['sources'][source_name] = {'error': str(data)}
            else:
                aggregated_data['sources'][source_name] = data

        # Process and combine data
        aggregated_data['combined_indices'] = self._combine_indices(aggregated_data['sources'])
        aggregated_data['material_prices'] = self._aggregate_material_prices(aggregated_data['sources'])
        aggregated_data['market_trends'] = self._analyze_trends(aggregated_data['sources'])

        return aggregated_data

    async def _fetch_source_data(self, name: str, source) -> Dict:
        """Fetch data from a specific source"""
        try:
            return await source.fetch_data()
        except Exception as e:
            logger.error(f"Error fetching from {name}: {e}")
            raise

class LMEDataSource:
    """London Metal Exchange data source"""

    def __init__(self):
        self.base_url = "https://api.lme.com/v1"
        self.api_key = settings.LME_API_KEY

    async def fetch_data(self) -> Dict:
        """Fetch LME metal prices"""
        async with aiohttp.ClientSession() as session:
            metals = ['copper', 'aluminum', 'zinc', 'lead', 'nickel', 'tin']
            prices = {}

            for metal in metals:
                url = f"{self.base_url}/prices/{metal}/latest"
                headers = {'Authorization': f'Bearer {self.api_key}'}

                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices[metal] = {
                            'price': data['price'],
                            'currency': 'USD',
                            'unit': 'MT',
                            'change_24h': data['change_24h'],
                            'timestamp': data['timestamp']
                        }

            return {
                'prices': prices,
                'exchange': 'LME',
                'update_time': datetime.now().isoformat()
            }
```

---

## IMPLEMENTATION SUMMARY

### Phase 3 Deliverables (Q1 2025)
✅ FastAPI ML Service Architecture
✅ LSTM Price Prediction Model
✅ Prophet Time-Series Forecasting
✅ Should-Cost Modeling System
✅ Advanced Anomaly Detection
✅ ML API Endpoints

### Phase 4 Deliverables (Q2 2025)
✅ SAP ERP Integration
✅ Oracle EBS Integration
✅ Microsoft Dynamics 365 Integration
✅ Supplier Collaboration Portal
✅ WebSocket Real-time Updates

### Phase 5 Deliverables (Q3 2025)
✅ Predictive Spend Analytics
✅ Market Intelligence Platform
✅ Supply Chain Risk Management
✅ Advanced Reporting

---

**Document Version**: 1.0
**Last Updated**: December 2024
**Repository**: https://github.com/bomino/Pricing-Agent2

---

*End of Phase 4-5 Implementation Plan*
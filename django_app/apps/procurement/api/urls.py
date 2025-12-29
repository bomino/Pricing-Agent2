"""
Procurement API URL configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

# Create router and register viewsets
router = DefaultRouter()
router.register(r'suppliers', viewsets.SupplierViewSet, basename='suppliers')
router.register(r'rfqs', viewsets.RFQViewSet, basename='rfqs')
router.register(r'quotes', viewsets.QuoteViewSet, basename='quotes')
router.register(r'contracts', viewsets.ContractViewSet, basename='contracts')
router.register(r'analytics', viewsets.ProcurementAnalyticsViewSet, basename='procurement-analytics')

app_name = 'procurement-api'

urlpatterns = [
    # API router URLs
    path('', include(router.urls)),
    
    # Additional custom endpoints can be added here if needed
]

# API endpoints documentation:
"""
Suppliers:
- GET    /api/v1/procurement/suppliers/                    - List suppliers
- POST   /api/v1/procurement/suppliers/                    - Create supplier
- GET    /api/v1/procurement/suppliers/{id}/               - Get supplier details
- PUT    /api/v1/procurement/suppliers/{id}/               - Update supplier
- PATCH  /api/v1/procurement/suppliers/{id}/               - Partial update supplier
- DELETE /api/v1/procurement/suppliers/{id}/               - Delete supplier
- POST   /api/v1/procurement/suppliers/{id}/approve/       - Approve supplier
- POST   /api/v1/procurement/suppliers/{id}/suspend/       - Suspend supplier
- GET    /api/v1/procurement/suppliers/{id}/performance/   - Get supplier performance
- GET    /api/v1/procurement/suppliers/{id}/quotes/        - Get supplier quotes
- GET    /api/v1/procurement/suppliers/{id}/contracts/     - Get supplier contracts
- POST   /api/v1/procurement/suppliers/{id}/add_contact/   - Add supplier contact
- GET    /api/v1/procurement/suppliers/performance_ranking/ - Get performance ranking

RFQs (Request for Quotes):
- GET    /api/v1/procurement/rfqs/                         - List RFQs
- POST   /api/v1/procurement/rfqs/                         - Create RFQ
- GET    /api/v1/procurement/rfqs/{id}/                    - Get RFQ details
- PUT    /api/v1/procurement/rfqs/{id}/                    - Update RFQ
- PATCH  /api/v1/procurement/rfqs/{id}/                    - Partial update RFQ
- DELETE /api/v1/procurement/rfqs/{id}/                    - Delete RFQ
- POST   /api/v1/procurement/rfqs/{id}/publish/            - Publish RFQ
- POST   /api/v1/procurement/rfqs/{id}/close/              - Close RFQ
- POST   /api/v1/procurement/rfqs/{id}/award/              - Award RFQ to quote
- GET    /api/v1/procurement/rfqs/{id}/quotes/             - Get RFQ quotes
- GET    /api/v1/procurement/rfqs/{id}/analytics/          - Get RFQ analytics
- GET    /api/v1/procurement/rfqs/{id}/compare_quotes/     - Compare quotes
- POST   /api/v1/procurement/rfqs/{id}/add_item/           - Add item to RFQ

Quotes:
- GET    /api/v1/procurement/quotes/                       - List quotes
- POST   /api/v1/procurement/quotes/                       - Create quote
- GET    /api/v1/procurement/quotes/{id}/                  - Get quote details
- PUT    /api/v1/procurement/quotes/{id}/                  - Update quote
- PATCH  /api/v1/procurement/quotes/{id}/                  - Partial update quote
- DELETE /api/v1/procurement/quotes/{id}/                  - Delete quote
- POST   /api/v1/procurement/quotes/{id}/submit/           - Submit quote
- POST   /api/v1/procurement/quotes/{id}/accept/           - Accept quote
- POST   /api/v1/procurement/quotes/{id}/reject/           - Reject quote
- POST   /api/v1/procurement/quotes/{id}/evaluate/         - Evaluate quote

Contracts:
- GET    /api/v1/procurement/contracts/                    - List contracts
- POST   /api/v1/procurement/contracts/                    - Create contract
- GET    /api/v1/procurement/contracts/{id}/               - Get contract details
- PUT    /api/v1/procurement/contracts/{id}/               - Update contract
- PATCH  /api/v1/procurement/contracts/{id}/               - Partial update contract
- DELETE /api/v1/procurement/contracts/{id}/               - Delete contract
- POST   /api/v1/procurement/contracts/{id}/approve/       - Approve contract
- POST   /api/v1/procurement/contracts/{id}/terminate/     - Terminate contract
- GET    /api/v1/procurement/contracts/expiring_soon/      - Get expiring contracts

Analytics:
- GET    /api/v1/procurement/analytics/stats/              - Get procurement statistics
- GET    /api/v1/procurement/analytics/supplier_performance/ - Get supplier performance
- GET    /api/v1/procurement/analytics/spending_analysis/  - Get spending analysis
- GET    /api/v1/procurement/analytics/savings_analysis/   - Get savings analysis

Query Parameters:
- page: Page number for pagination
- page_size: Number of items per page (default: 50, max: 100)
- search: Search term for filtering
- ordering: Field to order by (prefix with '-' for descending)
- supplier_type: Filter suppliers by type
- status: Filter by status
- priority: Filter RFQs by priority
- currency: Filter quotes/contracts by currency
- contract_type: Filter contracts by type

Example Requests:

1. Create new supplier:
   POST /api/v1/procurement/suppliers/
   {
     "name": "Acme Corp",
     "code": "ACME001",
     "supplier_type": "manufacturer",
     "primary_contact_name": "John Smith",
     "primary_contact_email": "john@acme.com",
     "country": "USA",
     "payment_terms": "Net 30"
   }

2. Create RFQ:
   POST /api/v1/procurement/rfqs/
   {
     "title": "Office Supplies Q1 2024",
     "description": "Quarterly office supplies procurement",
     "deadline": "2024-03-15T23:59:59Z",
     "priority": "medium",
     "invited_supplier_ids": ["uuid1", "uuid2"],
     "payment_terms": "Net 30"
   }

3. Submit quote:
   POST /api/v1/procurement/quotes/{id}/submit/

4. Evaluate quote:
   POST /api/v1/procurement/quotes/{id}/evaluate/
   {
     "technical_score": 85.5,
     "commercial_score": 92.0,
     "notes": "Good technical compliance, competitive pricing"
   }

5. Award RFQ:
   POST /api/v1/procurement/rfqs/{id}/award/
   {
     "quote_id": "uuid-of-winning-quote"
   }

6. Get supplier performance:
   GET /api/v1/procurement/suppliers/{id}/performance/

7. Compare quotes for RFQ:
   GET /api/v1/procurement/rfqs/{id}/compare_quotes/

8. Get procurement statistics:
   GET /api/v1/procurement/analytics/stats/

Response Format:
All responses follow a consistent format:
- List endpoints return paginated results with 'count', 'next', 'previous', and 'results'
- Detail endpoints return the object data directly
- Error responses include 'error' message and appropriate HTTP status codes
- Success operations return 'status' message

Workflow Examples:

1. Supplier Onboarding:
   a. Create supplier (status: pending_approval)
   b. Admin reviews and approves: POST /suppliers/{id}/approve/
   c. Supplier status changes to 'active'

2. RFQ Process:
   a. Create RFQ (status: draft)
   b. Add items: POST /rfqs/{id}/add_item/
   c. Invite suppliers by adding to invited_supplier_ids
   d. Publish RFQ: POST /rfqs/{id}/publish/
   e. Suppliers submit quotes
   f. Evaluate quotes: POST /quotes/{id}/evaluate/
   g. Compare quotes: GET /rfqs/{id}/compare_quotes/
   h. Award RFQ: POST /rfqs/{id}/award/

3. Quote Evaluation:
   a. Quote submitted by supplier
   b. Buyer evaluates: POST /quotes/{id}/evaluate/
   c. Quote accepted/rejected: POST /quotes/{id}/accept/ or /reject/

4. Contract Management:
   a. Create contract from awarded quote
   b. Approve contract: POST /contracts/{id}/approve/
   c. Monitor expiration: GET /contracts/expiring_soon/
   d. Terminate if needed: POST /contracts/{id}/terminate/

Permissions:
- IsAuthenticated: Required for all endpoints
- IsAdminUser: Required for approval operations
- Organization filtering automatically applied
- Users can only access data within their organization

Status Workflows:

Supplier: pending_approval → active → suspended/inactive
RFQ: draft → published → closed → awarded
Quote: draft → submitted → under_review → accepted/rejected
Contract: draft → pending_approval → active → completed/terminated

Error Codes:
- 400: Bad Request (validation errors, workflow violations)
- 401: Unauthorized (authentication required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found (resource doesn't exist)
- 409: Conflict (duplicate entries, business rule violations)
"""
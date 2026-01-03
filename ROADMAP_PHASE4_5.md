# Implementation Plan: Phase 4 & 5 Roadmap

## Overview
Combined implementation roadmap for Phase 4 (Enterprise Features) and Phase 5 (Advanced Analytics) for the AI Pricing Agent platform.

**Based on:** README.md roadmap + codebase exploration
**Status:** PLANNING
**Target:** Q1-Q3 2026

---

## Phase 4: Enterprise Features

### 4.1 Advanced RBAC ✅ COMPLETE
- Already implemented in `apps/core/rbac.py`
- 3 roles (Admin, Analyst, User) with 30+ permissions
- Decorators and mixins ready for use

### 4.2 WebSocket Real-Time Updates
**Status:** FastAPI ready, Django needs implementation

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/pricing_agent/asgi.py` | ASGI application with Channels routing |
| `django_app/apps/core/consumers.py` | WebSocket consumers for real-time events |
| `django_app/apps/core/routing.py` | WebSocket URL routing |

**Dependencies to Add:**
```
channels==4.0.0
daphne==4.0.0
channels-redis==4.1.0
```

**Implementation Steps:**
1. Install Django Channels and configure ASGI
2. Create WebSocket consumers for:
   - Price update notifications
   - Anomaly alerts
   - RFQ status changes
   - ML prediction completion
3. Connect to existing FastAPI WebSocket infrastructure
4. Update templates with WebSocket client JavaScript

**Existing FastAPI WebSockets:** `fastapi_ml/api/websockets.py` - ConnectionManager fully implemented

### 4.3 ERP System Integration (SAP, Oracle, Sage)
**Status:** Framework exists, no API implementations

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/integrations/models.py` | IntegrationConnection, SyncLog, WebhookEndpoint models |
| `django_app/apps/integrations/serializers.py` | API serializers |
| `django_app/apps/integrations/connectors/base.py` | Base ERP connector class |
| `django_app/apps/integrations/connectors/sap.py` | SAP Business One connector |
| `django_app/apps/integrations/connectors/oracle.py` | Oracle ERP Cloud connector |
| `django_app/apps/integrations/connectors/sage.py` | Sage connector |
| `django_app/apps/integrations/tasks.py` | Celery tasks for sync operations |
| `django_app/templates/integrations/*.html` | Integration UI templates |

**Existing Framework:** `apps/integrations/views.py` (523 lines) - Views ready, needs models/connectors

**Implementation Steps:**
1. Create integration models (IntegrationConnection, SyncLog, WebhookEndpoint)
2. Build base connector class with common interface
3. Implement SAP connector (OAuth2, data mapping)
4. Implement Oracle connector
5. Implement Sage connector
6. Create Celery tasks for scheduled sync
7. Build integration templates

### 4.4 Supplier Portal
**Status:** Internal CRUD exists, external portal missing

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/procurement/portal_views.py` | External supplier-facing views |
| `django_app/apps/accounts/supplier_auth.py` | Supplier authentication/registration |
| `django_app/templates/supplier_portal/*.html` | Portal templates |

**Existing:** Supplier CRUD in `apps/procurement/views.py`, `supplier_detail.html`

**Implementation Steps:**
1. Create supplier user role and authentication
2. Build supplier self-service views:
   - Profile management
   - Quote submission
   - RFQ response
   - Document upload
3. Add messaging/collaboration features
4. Create external-facing templates

### 4.5 Multi-Language Support (i18n)
**Status:** Not started

**Files to Modify:**
| File | Changes |
|------|---------|
| `settings.py` | Add LocaleMiddleware, LANGUAGES config |
| `urls.py` | Add i18n_patterns for URL routing |
| All templates | Add `{% trans %}` tags |
| All Python files | Add `_()` for translatable strings |

**Implementation Steps:**
1. Configure Django i18n middleware
2. Create base translation files (.po)
3. Mark strings for translation in code
4. Add language switcher to UI
5. Translate to target languages (Spanish, French, German)

---

## Phase 5: Advanced Analytics

### 5.1 Predictive Spend Analytics
**Status:** Price prediction exists, spend forecasting missing

**Files to Create:**
| File | Purpose |
|------|---------|
| `fastapi_ml/services/spend_forecasting.py` | Spend prediction model |
| `django_app/apps/analytics/spend_views.py` | Spend forecasting views |
| `django_app/templates/analytics/spend_forecast.html` | Forecast dashboard |

**Existing:** ML infrastructure in `fastapi_ml/`, `apps/pricing/ml_client.py`

**Implementation Steps:**
1. Build spend forecasting model (time series, seasonal patterns)
2. Add consumption pattern analysis
3. Create budget forecasting endpoints
4. Build spend forecast dashboard
5. Add trend projection visualizations

### 5.2 Market Intelligence Integration
**Status:** Bloomberg/Reuters stubs only

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/integrations/market_data/bloomberg.py` | Bloomberg API client |
| `django_app/apps/integrations/market_data/reuters.py` | Reuters API client |
| `django_app/apps/analytics/models.py` | MarketData, CommodityPrice models |
| `django_app/apps/analytics/market_views.py` | Market intelligence dashboard |

**Existing Stubs:** `apps/integrations/views.py` - BloombergIntegrationView, ReutersIntegrationView

**Implementation Steps:**
1. Implement Bloomberg Terminal API client
2. Implement Reuters Eikon API client
3. Create market data models
4. Build commodity price tracking
5. Add market intelligence dashboard
6. Integrate market data into price predictions

### 5.3 Supply Chain Risk Assessment
**Status:** Basic risk_level field only

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/procurement/risk_scoring.py` | Risk scoring model |
| `django_app/apps/procurement/risk_views.py` | Risk assessment views |
| `django_app/templates/procurement/risk_dashboard.html` | Risk heat map UI |

**Existing:** `Supplier.risk_level` field (low/medium/high/critical)

**Implementation Steps:**
1. Build multi-factor risk scoring model:
   - Financial health (payment history, credit)
   - Geographic concentration
   - Single-source dependency
   - Delivery performance
   - Quality metrics
2. Create risk trend analysis
3. Add alternative supplier recommendations
4. Build risk dashboard with heat maps
5. Create risk escalation alerts

### 5.4 Contract Compliance Monitoring
**Status:** Report generation exists, no monitoring

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/procurement/compliance.py` | Compliance monitoring engine |
| `django_app/apps/procurement/tasks.py` | Scheduled compliance checks |
| `django_app/templates/procurement/compliance_dashboard.html` | Compliance UI |

**Existing:** Contract model, `_generate_contract_compliance()` report method

**Implementation Steps:**
1. Create compliance rules engine
2. Implement automated checks:
   - Price escalation clause monitoring
   - Volume commitment tracking
   - KPI validation
   - Renewal date alerts
3. Add non-compliance escalation workflow
4. Build compliance dashboard
5. Create audit trail for contract changes

### 5.5 Automated RFQ Generation
**Status:** Manual creation only

**Files to Create:**
| File | Purpose |
|------|---------|
| `django_app/apps/procurement/rfq_automation.py` | Auto-RFQ triggers and generation |
| `django_app/apps/procurement/signals.py` | Event triggers for auto-RFQ |

**Existing:** Full RFQ workflow in `apps/procurement/models.py`

**Implementation Steps:**
1. Create auto-RFQ triggers:
   - Reorder point threshold
   - Expiring contracts (30/60/90 days)
   - Price increase alerts
   - Supplier performance issues
2. Implement intelligent supplier selection
3. Add template-based RFQ generation
4. Create batch RFQ capabilities
5. Build demand-based quantity calculation

---

## Implementation Priority

### High Priority (Q1 2026)
1. **4.3 ERP Integration** - Models + SAP connector (business-critical)
2. **5.1 Spend Forecasting** - Extends existing ML (high ROI)
3. **4.4 Supplier Portal** - External collaboration (user-requested)

### Medium Priority (Q2 2026)
4. **4.2 WebSockets** - Real-time updates (UX improvement)
5. **5.5 RFQ Automation** - Process efficiency (time saver)
6. **5.3 Risk Assessment** - Risk management (enterprise requirement)

### Lower Priority (Q3 2026)
7. **5.4 Contract Compliance** - Extends existing reports
8. **5.2 Market Intelligence** - External API costs
9. **4.5 i18n** - Multi-language (if international expansion)

---

## Success Criteria

### Phase 4
- [ ] WebSocket connections working for real-time alerts
- [ ] At least 1 ERP connector (SAP) fully functional
- [ ] Supplier portal with self-service quote submission
- [ ] RBAC enforced across all enterprise features

### Phase 5
- [ ] Spend forecasting with 80%+ accuracy
- [ ] Risk scores calculated for all active suppliers
- [ ] Contract compliance alerts triggered automatically
- [ ] RFQs auto-generated for reorder points

---

## Dependencies

**New Python Packages:**
```
channels==4.0.0
daphne==4.0.0
channels-redis==4.1.0
statsmodels==0.14.0  # For time series forecasting
```

**External APIs (credentials required):**
- SAP Business One API
- Oracle ERP Cloud API
- Bloomberg Terminal API (optional)
- Reuters Eikon API (optional)

---

## Estimated Effort

| Component | Complexity | Est. Days |
|-----------|------------|-----------|
| 4.2 WebSockets | Medium | 5 |
| 4.3 ERP Integration (SAP) | High | 15 |
| 4.4 Supplier Portal | Medium | 10 |
| 4.5 i18n | Low | 5 |
| 5.1 Spend Forecasting | High | 12 |
| 5.2 Market Intelligence | High | 15 |
| 5.3 Risk Assessment | Medium | 8 |
| 5.4 Contract Compliance | Medium | 8 |
| 5.5 RFQ Automation | Medium | 10 |
| **Total** | | **88 days** |

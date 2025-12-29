-- =====================================================================
-- Migration 003: RFQ and Quote Workflow Tables
-- Business process tables for procurement workflow
-- =====================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('003', 'RFQ and Quote workflow tables', NOW())
ON CONFLICT (version) DO NOTHING;

BEGIN;

-- =====================================================================
-- RFQ WORKFLOW TABLES
-- =====================================================================

-- Request for Quotes
CREATE TABLE IF NOT EXISTS rfqs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    rfq_number VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    priority VARCHAR(20) DEFAULT 'medium',
    due_date TIMESTAMPTZ,
    created_by BIGINT NOT NULL REFERENCES users(id),
    assigned_to BIGINT REFERENCES users(id),
    total_estimated_value DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    terms_and_conditions TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RFQ line items
CREATE TABLE IF NOT EXISTS rfq_items (
    id BIGSERIAL PRIMARY KEY,
    rfq_id BIGINT NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    material_id BIGINT NOT NULL REFERENCES materials(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_of_measure VARCHAR(50) NOT NULL,
    description TEXT,
    specifications JSONB DEFAULT '{}',
    delivery_date TIMESTAMPTZ,
    line_number INTEGER NOT NULL,
    
    UNIQUE(rfq_id, line_number)
);

-- RFQ suppliers (invitation list)
CREATE TABLE IF NOT EXISTS rfq_suppliers (
    id BIGSERIAL PRIMARY KEY,
    rfq_id BIGINT NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    invited_by BIGINT REFERENCES users(id),
    response_status VARCHAR(50) DEFAULT 'pending',
    
    UNIQUE(rfq_id, supplier_id)
);

-- =====================================================================
-- QUOTE WORKFLOW TABLES
-- =====================================================================

-- Supplier quotes
CREATE TABLE IF NOT EXISTS quotes (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    rfq_id BIGINT REFERENCES rfqs(id),
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    quote_number VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'draft',
    total_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    validity_period INTEGER,
    payment_terms VARCHAR(255),
    delivery_terms VARCHAR(255),
    notes TEXT,
    submitted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, quote_number)
);

-- Quote line items
CREATE TABLE IF NOT EXISTS quote_items (
    id BIGSERIAL PRIMARY KEY,
    quote_id BIGINT NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    rfq_item_id BIGINT REFERENCES rfq_items(id),
    material_id BIGINT NOT NULL REFERENCES materials(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    unit_of_measure VARCHAR(50) NOT NULL,
    delivery_date TIMESTAMPTZ,
    lead_time_days INTEGER,
    line_number INTEGER NOT NULL,
    notes TEXT,
    
    UNIQUE(quote_id, line_number)
);

-- =====================================================================
-- WORKFLOW INDEXES
-- =====================================================================

-- RFQ indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rfqs_org_status 
ON rfqs (organization_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rfqs_assigned 
ON rfqs (assigned_to, status, due_date) WHERE assigned_to IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rfqs_due_date 
ON rfqs (due_date, status) WHERE due_date IS NOT NULL;

-- RFQ items indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rfq_items_rfq 
ON rfq_items (rfq_id, line_number);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rfq_items_material 
ON rfq_items (material_id, quantity DESC);

-- Quote indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quotes_org_status 
ON quotes (organization_id, status, submitted_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quotes_rfq 
ON quotes (rfq_id, status, total_amount DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quotes_supplier 
ON quotes (supplier_id, status, submitted_at DESC);

-- Quote items indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quote_items_quote 
ON quote_items (quote_id, line_number);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quote_items_material 
ON quote_items (material_id, unit_price);

-- =====================================================================
-- WORKFLOW STATUS CONSTRAINTS
-- =====================================================================

-- Add check constraints for valid status values
ALTER TABLE rfqs ADD CONSTRAINT check_rfq_status 
CHECK (status IN ('draft', 'sent', 'closed', 'cancelled'));

ALTER TABLE rfq_suppliers ADD CONSTRAINT check_response_status 
CHECK (response_status IN ('pending', 'submitted', 'declined'));

ALTER TABLE quotes ADD CONSTRAINT check_quote_status 
CHECK (status IN ('draft', 'submitted', 'accepted', 'rejected'));

ALTER TABLE rfqs ADD CONSTRAINT check_priority 
CHECK (priority IN ('low', 'medium', 'high', 'urgent'));

-- =====================================================================
-- WORKFLOW TRIGGERS
-- =====================================================================

-- Function to update RFQ status when quotes are received
CREATE OR REPLACE FUNCTION update_rfq_on_quote_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Update RFQ supplier response status when quote is submitted
    IF NEW.status = 'submitted' AND (OLD.status IS NULL OR OLD.status != 'submitted') THEN
        UPDATE rfq_suppliers 
        SET response_status = 'submitted' 
        WHERE rfq_id = NEW.rfq_id AND supplier_id = NEW.supplier_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on quotes table
CREATE TRIGGER trg_update_rfq_on_quote_change
    AFTER UPDATE ON quotes
    FOR EACH ROW
    EXECUTE FUNCTION update_rfq_on_quote_change();

COMMIT;
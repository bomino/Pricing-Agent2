-- =====================================================================
-- Migration 004: Contracts and Audit System
-- Contract management and comprehensive audit trail
-- =====================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('004', 'Contract management and audit system', NOW())
ON CONFLICT (version) DO NOTHING;

BEGIN;

-- =====================================================================
-- CONTRACT MANAGEMENT TABLES
-- =====================================================================

-- Contracts master
CREATE TABLE IF NOT EXISTS contracts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    contract_number VARCHAR(100) UNIQUE NOT NULL,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    quote_id BIGINT REFERENCES quotes(id),
    title VARCHAR(500) NOT NULL,
    contract_type VARCHAR(50) DEFAULT 'purchase',
    status VARCHAR(50) DEFAULT 'draft',
    start_date DATE NOT NULL,
    end_date DATE,
    total_value DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    payment_terms VARCHAR(255),
    terms_and_conditions TEXT,
    auto_renew BOOLEAN DEFAULT FALSE,
    renewal_period INTEGER,
    created_by BIGINT NOT NULL REFERENCES users(id),
    approved_by BIGINT REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Contract line items
CREATE TABLE IF NOT EXISTS contract_items (
    id BIGSERIAL PRIMARY KEY,
    contract_id BIGINT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    material_id BIGINT NOT NULL REFERENCES materials(id),
    unit_price DECIMAL(15,2) NOT NULL,
    minimum_quantity DECIMAL(15,4),
    maximum_quantity DECIMAL(15,4),
    unit_of_measure VARCHAR(50) NOT NULL,
    price_escalation_clause TEXT,
    line_number INTEGER NOT NULL,
    
    UNIQUE(contract_id, line_number)
);

-- =====================================================================
-- AUDIT SYSTEM TABLES
-- =====================================================================

-- Comprehensive audit log (will become hypertable)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    table_name VARCHAR(255) NOT NULL,
    record_id BIGINT NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_fields JSONB,
    user_id BIGINT REFERENCES users(id),
    session_id UUID,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Convert audit_log to hypertable
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'audit_log'
    ) THEN
        PERFORM create_hypertable('audit_log', 'timestamp', 
                                chunk_time_interval => INTERVAL '1 day');
    END IF;
END $$;

-- Document management
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(255),
    checksum VARCHAR(255),
    entity_type VARCHAR(100),
    entity_id BIGINT NOT NULL,
    document_type VARCHAR(100),
    version INTEGER DEFAULT 1,
    is_current BOOLEAN DEFAULT TRUE,
    uploaded_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- CONTRACT INDEXES
-- =====================================================================

-- Contract indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_org_status 
ON contracts (organization_id, status, start_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_supplier 
ON contracts (supplier_id, status, end_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_dates 
ON contracts (start_date, end_date, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_expiring 
ON contracts (end_date, status) 
WHERE status = 'active' AND end_date BETWEEN NOW() AND NOW() + INTERVAL '90 days';

-- Contract items indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_items_contract 
ON contract_items (contract_id, line_number);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_items_material 
ON contract_items (material_id, unit_price);

-- =====================================================================
-- AUDIT INDEXES
-- =====================================================================

-- Audit log indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_org_table 
ON audit_log (organization_id, table_name, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_record 
ON audit_log (table_name, record_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_user_action 
ON audit_log (user_id, action, timestamp DESC) WHERE user_id IS NOT NULL;

-- Document indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_entity 
ON documents (entity_type, entity_id, is_current);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_type 
ON documents (organization_id, document_type, created_at DESC);

-- =====================================================================
-- CONTRACT CONSTRAINTS
-- =====================================================================

-- Contract status constraints
ALTER TABLE contracts ADD CONSTRAINT check_contract_type 
CHECK (contract_type IN ('purchase', 'blanket', 'framework'));

ALTER TABLE contracts ADD CONSTRAINT check_contract_status 
CHECK (status IN ('draft', 'active', 'expired', 'terminated'));

-- Date validation
ALTER TABLE contracts ADD CONSTRAINT check_contract_dates 
CHECK (end_date IS NULL OR end_date >= start_date);

-- =====================================================================
-- AUDIT SYSTEM SETUP
-- =====================================================================

-- Enhanced audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    old_data JSONB;
    new_data JSONB;
    changed_fields JSONB = '[]'::JSONB;
    org_id BIGINT;
BEGIN
    -- Get organization_id from the record
    IF TG_OP = 'DELETE' THEN
        org_id = OLD.organization_id;
        old_data = to_jsonb(OLD);
        new_data = NULL;
    ELSIF TG_OP = 'UPDATE' THEN
        org_id = NEW.organization_id;
        old_data = to_jsonb(OLD);
        new_data = to_jsonb(NEW);
        
        -- Find changed fields
        SELECT jsonb_agg(key)
        INTO changed_fields
        FROM (
            SELECT key 
            FROM jsonb_each(old_data) 
            WHERE key != 'updated_at' 
                AND old_data->>key IS DISTINCT FROM new_data->>key
        ) t;
        
    ELSIF TG_OP = 'INSERT' THEN
        org_id = NEW.organization_id;
        old_data = NULL;
        new_data = to_jsonb(NEW);
    END IF;
    
    -- Only log if there are actual changes (for UPDATE) or for INSERT/DELETE
    IF TG_OP != 'UPDATE' OR jsonb_array_length(changed_fields) > 0 THEN
        INSERT INTO audit_log (
            organization_id,
            table_name,
            record_id,
            action,
            old_values,
            new_values,
            changed_fields,
            user_id,
            session_id,
            timestamp
        ) VALUES (
            org_id,
            TG_TABLE_NAME,
            COALESCE(NEW.id, OLD.id),
            TG_OP,
            old_data,
            new_data,
            changed_fields,
            NULLIF(current_setting('app.current_user_id', true), '')::BIGINT,
            NULLIF(current_setting('app.current_session_id', true), '')::UUID,
            NOW()
        );
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create audit triggers for key tables
CREATE TRIGGER audit_materials_trigger
    AFTER INSERT OR UPDATE OR DELETE ON materials
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_suppliers_trigger
    AFTER INSERT OR UPDATE OR DELETE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_pricing_history_trigger
    AFTER INSERT OR UPDATE OR DELETE ON pricing_history
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_rfqs_trigger
    AFTER INSERT OR UPDATE OR DELETE ON rfqs
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_quotes_trigger
    AFTER INSERT OR UPDATE OR DELETE ON quotes
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_contracts_trigger
    AFTER INSERT OR UPDATE OR DELETE ON contracts
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- =====================================================================
-- AUDIT RETENTION POLICY
-- =====================================================================

-- Retain audit logs for 10 years for compliance
SELECT add_retention_policy('audit_log', INTERVAL '10 years');

-- Enable compression on audit log (older than 30 days)
ALTER TABLE audit_log SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'organization_id, table_name, user_id',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('audit_log', INTERVAL '30 days');

COMMIT;
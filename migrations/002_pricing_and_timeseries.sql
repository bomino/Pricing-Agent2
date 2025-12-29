-- =====================================================================
-- Migration 002: Pricing Data and TimescaleDB Setup
-- Time-series tables, hypertables, and market data
-- =====================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('002', 'Pricing data tables and TimescaleDB hypertables setup', NOW())
ON CONFLICT (version) DO NOTHING;

BEGIN;

-- =====================================================================
-- PRICING AND MARKET DATA TABLES
-- =====================================================================

-- Historical pricing data (will become hypertable)
CREATE TABLE IF NOT EXISTS pricing_history (
    id BIGSERIAL,
    organization_id BIGINT NOT NULL,
    material_id BIGINT NOT NULL REFERENCES materials(id),
    supplier_id BIGINT REFERENCES suppliers(id),
    price DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    quantity DECIMAL(15,4),
    unit_of_measure VARCHAR(50),
    price_type VARCHAR(50) DEFAULT 'quoted',
    source VARCHAR(100),
    source_reference VARCHAR(255),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Market data (will become hypertable)
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL,
    organization_id BIGINT NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    price DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    exchange VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL,
    volume DECIMAL(15,4),
    metadata JSONB DEFAULT '{}'
);

-- =====================================================================
-- CONVERT TO HYPERTABLES (if not already converted)
-- =====================================================================

-- Check and create hypertables
DO $$
BEGIN
    -- Check if pricing_history is already a hypertable
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'pricing_history'
    ) THEN
        PERFORM create_hypertable('pricing_history', 'recorded_at', 
                                chunk_time_interval => INTERVAL '7 days');
    END IF;
    
    -- Check if market_data is already a hypertable
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'market_data'
    ) THEN
        PERFORM create_hypertable('market_data', 'timestamp', 
                                chunk_time_interval => INTERVAL '1 hour');
    END IF;
END $$;

-- =====================================================================
-- PRICING INDEXES (TimescaleDB optimized)Class
-- =====================================================================

-- Pricing history indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pricing_history_material_time 
ON pricing_history (material_id, recorded_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pricing_history_supplier_time 
ON pricing_history (supplier_id, recorded_at DESC) WHERE supplier_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pricing_history_org_time 
ON pricing_history (organization_id, recorded_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pricing_history_price_type 
ON pricing_history (price_type, recorded_at DESC);

-- Market data indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_market_data_symbol_time 
ON market_data (symbol, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_market_data_org_time 
ON market_data (organization_id, timestamp DESC);

-- =====================================================================
-- CONSTRAINTS AFTER HYPERTABLE CREATION
-- =====================================================================

-- Add constraints that work with TimescaleDB
ALTER TABLE pricing_history ADD CONSTRAINT fk_pricing_organization 
FOREIGN KEY (organization_id) REFERENCES organizations(id);

ALTER TABLE pricing_history ADD CONSTRAINT fk_pricing_material 
FOREIGN KEY (material_id) REFERENCES materials(id);

ALTER TABLE market_data ADD CONSTRAINT fk_market_organization 
FOREIGN KEY (organization_id) REFERENCES organizations(id);

-- =====================================================================
-- INITIAL DATA RETENTION POLICY
-- =====================================================================

-- Set up basic retention (will be enhanced in later migrations)
SELECT add_retention_policy('pricing_history', INTERVAL '7 years');
SELECT add_retention_policy('market_data', INTERVAL '2 years');

COMMIT;
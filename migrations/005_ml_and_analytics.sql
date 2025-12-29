-- =====================================================================
-- Migration 005: ML Features and Analytics
-- Machine learning infrastructure and analytics tables
-- =====================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('005', 'ML features and analytics infrastructure', NOW())
ON CONFLICT (version) DO NOTHING;

BEGIN;

-- =====================================================================
-- ML INFRASTRUCTURE TABLES
-- =====================================================================

-- ML model registry
CREATE TABLE IF NOT EXISTS ml_models (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    algorithm VARCHAR(100),
    parameters JSONB DEFAULT '{}',
    training_data_info JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, name, version)
);

-- Feature store (will become hypertable)
CREATE TABLE IF NOT EXISTS ml_features (
    id BIGSERIAL,
    organization_id BIGINT NOT NULL,
    feature_group VARCHAR(255) NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    feature_value DECIMAL(15,6),
    feature_vector JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    model_version VARCHAR(50)
);

-- Convert ml_features to hypertable
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'ml_features'
    ) THEN
        PERFORM create_hypertable('ml_features', 'computed_at', 
                                chunk_time_interval => INTERVAL '1 day');
    END IF;
END $$;

-- ML predictions and results
CREATE TABLE IF NOT EXISTS ml_predictions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    model_id BIGINT NOT NULL REFERENCES ml_models(id),
    prediction_type VARCHAR(100) NOT NULL,
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    predicted_value DECIMAL(15,6),
    confidence_score DECIMAL(5,4),
    prediction_data JSONB DEFAULT '{}',
    input_features JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- SYSTEM CONFIGURATION TABLES
-- =====================================================================

-- System settings
CREATE TABLE IF NOT EXISTS system_settings (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    setting_key VARCHAR(255) NOT NULL,
    setting_value JSONB NOT NULL,
    data_type VARCHAR(50) DEFAULT 'json',
    description TEXT,
    is_encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, setting_key)
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    user_id BIGINT REFERENCES users(id),
    type VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    message TEXT,
    data JSONB DEFAULT '{}',
    read_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- ML AND ANALYTICS INDEXES
-- =====================================================================

-- ML models indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_models_org_type 
ON ml_models (organization_id, model_type, is_active);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_models_version 
ON ml_models (organization_id, name, version DESC);

-- ML features indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_features_entity_time 
ON ml_features (entity_type, entity_id, computed_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_features_group_time 
ON ml_features (feature_group, computed_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_features_org_group 
ON ml_features (organization_id, feature_group, computed_at DESC);

-- ML predictions indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_predictions_entity 
ON ml_predictions (entity_type, entity_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_predictions_model 
ON ml_predictions (model_id, prediction_type, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_predictions_confidence 
ON ml_predictions (confidence_score DESC, created_at DESC) 
WHERE confidence_score >= 0.7;

-- System settings indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_settings_org_key 
ON system_settings (organization_id, setting_key);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_settings_global 
ON system_settings (setting_key) WHERE organization_id IS NULL;

-- Notifications indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_user_unread 
ON notifications (user_id, read_at, created_at DESC) WHERE read_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_org_type 
ON notifications (organization_id, type, created_at DESC);

-- =====================================================================
-- ANALYTICAL VIEWS
-- =====================================================================

-- Latest pricing view
CREATE VIEW IF NOT EXISTS latest_pricing AS
SELECT DISTINCT ON (ph.material_id, ph.supplier_id)
    ph.id,
    ph.organization_id,
    ph.material_id,
    m.name as material_name,
    m.sku,
    ph.supplier_id,
    s.name as supplier_name,
    ph.price,
    ph.currency,
    ph.quantity,
    ph.price_type,
    ph.recorded_at,
    ph.valid_from,
    ph.valid_to
FROM pricing_history ph
JOIN materials m ON ph.material_id = m.id
LEFT JOIN suppliers s ON ph.supplier_id = s.id
ORDER BY ph.material_id, ph.supplier_id, ph.recorded_at DESC;

-- Active contracts summary
CREATE VIEW IF NOT EXISTS active_contracts_summary AS
SELECT 
    c.id,
    c.organization_id,
    c.contract_number,
    c.title,
    s.name as supplier_name,
    c.start_date,
    c.end_date,
    c.total_value,
    c.currency,
    COUNT(ci.id) as item_count
FROM contracts c
JOIN suppliers s ON c.supplier_id = s.id
LEFT JOIN contract_items ci ON c.id = ci.contract_id
WHERE c.status = 'active' 
    AND (c.end_date IS NULL OR c.end_date >= CURRENT_DATE)
GROUP BY c.id, s.name;

-- Quote analysis view
CREATE VIEW IF NOT EXISTS quote_analysis AS
SELECT 
    q.id,
    q.organization_id,
    q.rfq_id,
    r.title as rfq_title,
    q.supplier_id,
    s.name as supplier_name,
    q.total_amount,
    q.currency,
    q.status,
    q.submitted_at,
    COUNT(qi.id) as item_count,
    AVG(qi.unit_price) as avg_unit_price
FROM quotes q
JOIN suppliers s ON q.supplier_id = s.id
LEFT JOIN rfqs r ON q.rfq_id = r.id
LEFT JOIN quote_items qi ON q.id = qi.quote_id
GROUP BY q.id, s.name, r.title;

-- =====================================================================
-- ML FEATURE CONSTRAINTS AND POLICIES
-- =====================================================================

-- Constraints for ML tables
ALTER TABLE ml_models ADD CONSTRAINT check_model_type 
CHECK (model_type IN ('price_prediction', 'demand_forecast', 'supplier_rating', 
                     'anomaly_detection', 'recommendation'));

ALTER TABLE ml_predictions ADD CONSTRAINT check_confidence_score 
CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

-- ML features retention and compression
SELECT add_retention_policy('ml_features', INTERVAL '3 years');

ALTER TABLE ml_features SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'organization_id, feature_group, entity_type',
    timescaledb.compress_orderby = 'computed_at DESC'
);

SELECT add_compression_policy('ml_features', INTERVAL '30 days');

-- =====================================================================
-- INITIAL SYSTEM SETTINGS
-- =====================================================================

-- Insert default system settings
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('default_currency', '"USD"', 'Default system currency'),
('price_decimal_places', '2', 'Decimal places for pricing'),
('session_timeout_minutes', '480', 'User session timeout in minutes'),
('max_file_upload_mb', '50', 'Maximum file upload size in MB'),
('enable_ml_predictions', 'true', 'Enable ML prediction features'),
('data_retention_years', '7', 'Data retention period in years'),
('rate_limit_requests_per_hour', '1000', 'API rate limit per user per hour'),
('notification_retention_days', '90', 'How long to keep notifications')
ON CONFLICT (organization_id, setting_key) DO NOTHING;

COMMIT;
-- =====================================================================
-- Migration Framework Setup
-- Schema versioning and migration management system
-- =====================================================================

-- Create schema_migrations table for tracking applied migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    execution_time INTERVAL,
    checksum VARCHAR(64)
);

-- Migration execution log for detailed tracking
CREATE TABLE IF NOT EXISTS migration_log (
    id BIGSERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    operation VARCHAR(20) NOT NULL, -- APPLY, ROLLBACK, SKIP
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    execution_time INTERVAL,
    applied_by VARCHAR(255) DEFAULT current_user
);

-- Function to safely apply a migration
CREATE OR REPLACE FUNCTION apply_migration(
    migration_version VARCHAR(50),
    migration_description TEXT,
    migration_sql TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
    execution_duration INTERVAL;
    migration_exists BOOLEAN;
    log_id BIGINT;
BEGIN
    start_time := NOW();
    
    -- Check if migration already applied
    SELECT EXISTS(
        SELECT 1 FROM schema_migrations 
        WHERE version = migration_version
    ) INTO migration_exists;
    
    IF migration_exists THEN
        RAISE NOTICE 'Migration % already applied, skipping', migration_version;
        
        INSERT INTO migration_log (version, operation, completed_at, success, error_message)
        VALUES (migration_version, 'SKIP', NOW(), TRUE, 'Migration already applied');
        
        RETURN TRUE;
    END IF;
    
    -- Start migration log
    INSERT INTO migration_log (version, operation, started_at)
    VALUES (migration_version, 'APPLY', start_time)
    RETURNING id INTO log_id;
    
    BEGIN
        -- Execute the migration SQL
        EXECUTE migration_sql;
        
        end_time := NOW();
        execution_duration := end_time - start_time;
        
        -- Record successful migration
        INSERT INTO schema_migrations (version, description, applied_at, execution_time)
        VALUES (migration_version, migration_description, end_time, execution_duration);
        
        -- Update log
        UPDATE migration_log 
        SET completed_at = end_time, 
            success = TRUE, 
            execution_time = execution_duration
        WHERE id = log_id;
        
        RAISE NOTICE 'Migration % applied successfully in %', migration_version, execution_duration;
        RETURN TRUE;
        
    EXCEPTION WHEN OTHERS THEN
        end_time := NOW();
        execution_duration := end_time - start_time;
        
        -- Record failed migration
        UPDATE migration_log 
        SET completed_at = end_time, 
            success = FALSE, 
            execution_time = execution_duration,
            error_message = SQLERRM
        WHERE id = log_id;
        
        RAISE NOTICE 'Migration % failed: %', migration_version, SQLERRM;
        RETURN FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to check migration status
CREATE OR REPLACE FUNCTION get_migration_status()
RETURNS TABLE (
    version VARCHAR(50),
    description TEXT,
    status VARCHAR(20),
    applied_at TIMESTAMPTZ,
    execution_time INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sm.version,
        sm.description,
        'APPLIED'::VARCHAR(20) as status,
        sm.applied_at,
        sm.execution_time
    FROM schema_migrations sm
    ORDER BY sm.version;
END;
$$ LANGUAGE plpgsql;

-- Function to rollback a migration (use with extreme caution)
CREATE OR REPLACE FUNCTION rollback_migration(
    migration_version VARCHAR(50),
    rollback_sql TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
    execution_duration INTERVAL;
    migration_exists BOOLEAN;
    log_id BIGINT;
BEGIN
    start_time := NOW();
    
    -- Check if migration exists
    SELECT EXISTS(
        SELECT 1 FROM schema_migrations 
        WHERE version = migration_version
    ) INTO migration_exists;
    
    IF NOT migration_exists THEN
        RAISE NOTICE 'Migration % not found, cannot rollback', migration_version;
        RETURN FALSE;
    END IF;
    
    -- Start rollback log
    INSERT INTO migration_log (version, operation, started_at)
    VALUES (migration_version, 'ROLLBACK', start_time)
    RETURNING id INTO log_id;
    
    BEGIN
        -- Execute the rollback SQL
        EXECUTE rollback_sql;
        
        -- Remove from schema_migrations
        DELETE FROM schema_migrations WHERE version = migration_version;
        
        end_time := NOW();
        execution_duration := end_time - start_time;
        
        -- Update log
        UPDATE migration_log 
        SET completed_at = end_time, 
            success = TRUE, 
            execution_time = execution_duration
        WHERE id = log_id;
        
        RAISE NOTICE 'Migration % rolled back successfully in %', migration_version, execution_duration;
        RETURN TRUE;
        
    EXCEPTION WHEN OTHERS THEN
        end_time := NOW();
        execution_duration := end_time - start_time;
        
        -- Record failed rollback
        UPDATE migration_log 
        SET completed_at = end_time, 
            success = FALSE, 
            execution_time = execution_duration,
            error_message = SQLERRM
        WHERE id = log_id;
        
        RAISE NOTICE 'Migration rollback % failed: %', migration_version, SQLERRM;
        RETURN FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to validate database schema integrity
CREATE OR REPLACE FUNCTION validate_schema_integrity()
RETURNS TABLE (
    check_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Check for missing foreign key constraints
    RETURN QUERY
    SELECT 
        'Foreign Key Constraints'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        'Found ' || COUNT(*)::TEXT || ' foreign key constraints'::TEXT
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
        AND table_schema = 'public';
    
    -- Check for TimescaleDB hypertables
    RETURN QUERY
    SELECT 
        'TimescaleDB Hypertables'::TEXT,
        CASE WHEN COUNT(*) >= 4 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        'Found ' || COUNT(*)::TEXT || ' hypertables (expected: pricing_history, market_data, ml_features, audit_log)'::TEXT
    FROM timescaledb_information.hypertables
    WHERE hypertable_name IN ('pricing_history', 'market_data', 'ml_features', 'audit_log');
    
    -- Check for required indexes
    RETURN QUERY
    SELECT 
        'Critical Indexes'::TEXT,
        CASE WHEN COUNT(*) > 20 THEN 'PASS' ELSE 'WARN' END::TEXT,
        'Found ' || COUNT(*)::TEXT || ' indexes on critical tables'::TEXT
    FROM pg_indexes
    WHERE schemaname = 'public'
        AND tablename IN ('users', 'materials', 'suppliers', 'pricing_history', 'quotes', 'contracts');
    
    -- Check audit triggers
    RETURN QUERY
    SELECT 
        'Audit Triggers'::TEXT,
        CASE WHEN COUNT(*) >= 6 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        'Found ' || COUNT(*)::TEXT || ' audit triggers'::TEXT
    FROM pg_trigger
    WHERE tgname LIKE '%audit%';
    
END;
$$ LANGUAGE plpgsql;

-- Initial migration framework record
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('000', 'Migration framework setup', NOW())
ON CONFLICT (version) DO NOTHING;

-- Create indexes for migration tracking
CREATE INDEX IF NOT EXISTS idx_schema_migrations_version ON schema_migrations (version);
CREATE INDEX IF NOT EXISTS idx_migration_log_version_operation ON migration_log (version, operation, started_at);

COMMENT ON TABLE schema_migrations IS 'Tracks applied database migrations';
COMMENT ON TABLE migration_log IS 'Detailed log of migration operations';
COMMENT ON FUNCTION apply_migration IS 'Safely applies a database migration with logging';
COMMENT ON FUNCTION rollback_migration IS 'Rolls back a migration - use with extreme caution';
COMMENT ON FUNCTION validate_schema_integrity IS 'Validates database schema and configuration';

-- Display current migration status
SELECT * FROM get_migration_status();
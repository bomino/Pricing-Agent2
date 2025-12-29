-- =====================================================================
-- Migration 001: Initial Schema Setup
-- AI Pricing Agent Database - Initial table creation
-- Compatible with PostgreSQL 16 + TimescaleDB
-- =====================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) VALUES 
('001', 'Initial schema setup with core tables', NOW())
ON CONFLICT (version) DO NOTHING;

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- =====================================================================
-- ORGANIZATIONS AND USERS
-- =====================================================================

-- Organizations table (Multi-tenant architecture)
CREATE TABLE IF NOT EXISTS organizations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    settings JSONB DEFAULT '{}',
    subscription_tier VARCHAR(50) DEFAULT 'basic',
    max_users INTEGER DEFAULT 50,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    role VARCHAR(50) DEFAULT 'user',
    permissions JSONB DEFAULT '[]',
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_key VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API keys
CREATE TABLE IF NOT EXISTS api_keys (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '[]',
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by BIGINT REFERENCES users(id)
);

-- =====================================================================
-- MATERIALS CATALOG
-- =====================================================================

-- Material categories
CREATE TABLE IF NOT EXISTS material_categories (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id BIGINT REFERENCES material_categories(id),
    path TEXT,
    level INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, name, parent_id)
);

-- Materials master
CREATE TABLE IF NOT EXISTS materials (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    category_id BIGINT REFERENCES material_categories(id),
    sku VARCHAR(255) NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    specifications JSONB DEFAULT '{}',
    unit_of_measure VARCHAR(50) NOT NULL,
    weight_kg DECIMAL(10,4),
    dimensions JSONB,
    material_type VARCHAR(100),
    grade VARCHAR(100),
    certifications JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, sku)
);

-- Material attributes
CREATE TABLE IF NOT EXISTS material_attributes (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    attribute_name VARCHAR(255) NOT NULL,
    attribute_value TEXT,
    data_type VARCHAR(50) DEFAULT 'text',
    unit VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(material_id, attribute_name)
);

-- =====================================================================
-- SUPPLIERS
-- =====================================================================

-- Suppliers master
CREATE TABLE IF NOT EXISTS suppliers (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    website VARCHAR(255),
    address JSONB,
    tax_id VARCHAR(100),
    payment_terms VARCHAR(255),
    lead_time_days INTEGER,
    minimum_order_value DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    rating DECIMAL(3,2),
    is_approved BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(organization_id, code)
);

-- Supplier materials relationship
CREATE TABLE IF NOT EXISTS supplier_materials (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    material_id BIGINT NOT NULL REFERENCES materials(id),
    supplier_sku VARCHAR(255),
    supplier_name VARCHAR(500),
    lead_time_days INTEGER,
    minimum_quantity DECIMAL(15,4),
    packaging_unit DECIMAL(15,4),
    last_quoted_price DECIMAL(15,2),
    last_quoted_date TIMESTAMPTZ,
    is_preferred BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(supplier_id, material_id)
);

-- Create basic indexes for this migration
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_slug ON organizations (slug);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_org ON users (organization_id, is_active);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_materials_org_sku ON materials (organization_id, sku);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suppliers_org_code ON suppliers (organization_id, code);

COMMIT;
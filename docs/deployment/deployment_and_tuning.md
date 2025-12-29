# Database Deployment and Performance Tuning Guide
## AI Pricing Agent - PostgreSQL 16 + TimescaleDB

### System Requirements and Architecture

**Minimum Production Requirements**:
- **CPU**: 16 cores (Intel Xeon or AMD EPYC)
- **RAM**: 64GB (128GB recommended)
- **Storage**: 2TB NVMe SSD (primary) + 10TB HDD (archives)
- **Network**: 10Gbps connection
- **OS**: Ubuntu 22.04 LTS or RHEL 8+

**Recommended Production Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (HAProxy/nginx)           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Application Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Django    │  │   FastAPI   │  │   Redis     │         │
│  │   (Web)     │  │   (ML/API)  │  │   (Cache)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Database Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Primary    │  │   Read       │  │   Analytics  │      │
│  │   (Master)   │──│   Replica    │  │   Replica    │      │
│  │              │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 1. Installation and Setup

### 1.1 PostgreSQL 16 Installation

```bash
#!/bin/bash
# install_postgresql16.sh

# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update

# Install PostgreSQL 16
sudo apt-get install -y postgresql-16 postgresql-contrib-16 postgresql-16-wal2json

# Install additional extensions
sudo apt-get install -y postgresql-16-pg-stat-statements postgresql-16-pgaudit
```

### 1.2 TimescaleDB Installation

```bash
#!/bin/bash
# install_timescaledb.sh

# Add TimescaleDB repository
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt-get update

# Install TimescaleDB
sudo apt-get install -y timescaledb-2-postgresql-16

# Run TimescaleDB setup
sudo timescaledb-tune --quiet --yes
```

### 1.3 Initial Database Setup

```bash
#!/bin/bash
# setup_database.sh

# Create database and user
sudo -u postgres createdb pricing_agent_db
sudo -u postgres psql -c "CREATE USER pricing_agent WITH ENCRYPTED PASSWORD 'secure_password_here';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE pricing_agent_db TO pricing_agent;"

# Create extensions
sudo -u postgres psql pricing_agent_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
sudo -u postgres psql pricing_agent_db -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
sudo -u postgres psql pricing_agent_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
sudo -u postgres psql pricing_agent_db -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
sudo -u postgres psql pricing_agent_db -c "CREATE EXTENSION IF NOT EXISTS btree_gin;"
```

## 2. PostgreSQL Configuration Optimization

### 2.1 Primary Configuration (`postgresql.conf`)

```ini
# postgresql.conf - Optimized for AI Pricing Agent

# =====================================================================
# CONNECTIONS AND AUTHENTICATION
# =====================================================================
listen_addresses = '*'
port = 5432
max_connections = 200                    # Adjust based on connection pooling
superuser_reserved_connections = 5

# =====================================================================
# RESOURCE USAGE
# =====================================================================

# Memory Settings (for 64GB RAM system)
shared_buffers = 16GB                   # 25% of total RAM
effective_cache_size = 48GB             # 75% of total RAM  
work_mem = 256MB                        # Per query operation memory
maintenance_work_mem = 2GB              # For VACUUM, CREATE INDEX, etc.
autovacuum_work_mem = 2GB               # Autovacuum memory

# Background Writer
bgwriter_delay = 200ms
bgwriter_lru_maxpages = 100
bgwriter_lru_multiplier = 2.0
bgwriter_flush_after = 512kB

# Checkpoints
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
checkpoint_flush_after = 256kB
max_wal_size = 4GB
min_wal_size = 1GB

# =====================================================================
# WRITE-AHEAD LOGGING (WAL)
# =====================================================================
wal_level = replica
wal_compression = on
wal_buffers = 16MB
wal_writer_delay = 200ms
wal_writer_flush_after = 1MB

# Archiving (for backup/replication)
archive_mode = on
archive_command = 'wal-e wal-push %p'
archive_timeout = 300                   # 5 minutes

# =====================================================================
# REPLICATION
# =====================================================================
max_wal_senders = 5
max_replication_slots = 5
hot_standby = on
hot_standby_feedback = on
max_standby_streaming_delay = 30s
max_standby_archive_delay = 60s

# =====================================================================
# QUERY TUNING
# =====================================================================
random_page_cost = 1.1                 # SSD optimized
seq_page_cost = 1.0
effective_io_concurrency = 32           # SSD concurrent I/O
max_worker_processes = 16
max_parallel_workers_per_gather = 4
max_parallel_workers = 16
max_parallel_maintenance_workers = 4

# =====================================================================
# TIMESCALEDB SPECIFIC SETTINGS
# =====================================================================
timescaledb.max_background_workers = 8
timescaledb.last_updated_cache_max_entries = 10000

# =====================================================================
# LOGGING AND MONITORING
# =====================================================================
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB

# Log timing and statistics
log_min_duration_statement = 1000       # Log queries > 1 second
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 10MB

# Statement statistics
shared_preload_libraries = 'timescaledb,pg_stat_statements'
pg_stat_statements.max = 10000
pg_stat_statements.track = all
pg_stat_statements.track_utility = on
pg_stat_statements.save = on

# =====================================================================
# AUTOVACUUM TUNING
# =====================================================================
autovacuum = on
autovacuum_naptime = 60s               # More frequent for high-write workload
autovacuum_max_workers = 6
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.05   # Vacuum when 5% changed
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.02  # Analyze when 2% changed
autovacuum_freeze_max_age = 200000000
autovacuum_multixact_freeze_max_age = 400000000

# =====================================================================
# LOCK MANAGEMENT
# =====================================================================
deadlock_timeout = 1s
max_locks_per_transaction = 256
max_pred_locks_per_transaction = 64

# =====================================================================
# MISCELLANEOUS
# =====================================================================
timezone = 'UTC'
shared_preload_libraries = 'timescaledb,pg_stat_statements,pgaudit'
```

### 2.2 Host-Based Authentication (`pg_hba.conf`)

```ini
# pg_hba.conf - Secure access configuration

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections
local   all             postgres                                peer
local   all             all                                     md5

# IPv4 local connections
host    all             all             127.0.0.1/32            md5

# Application connections
host    pricing_agent_db pricing_agent  10.0.0.0/16            md5
host    pricing_agent_db pricing_agent  172.16.0.0/12          md5

# Replication connections
host    replication     replicator      10.0.0.0/16            md5

# SSL connections only for production
hostssl all             all             0.0.0.0/0               md5
```

### 2.3 System-Level Optimizations

```bash
#!/bin/bash
# system_optimization.sh

# Kernel parameters for PostgreSQL
cat >> /etc/sysctl.conf << 'EOF'
# PostgreSQL optimizations
kernel.shmmax = 68719476736      # 64GB in bytes
kernel.shmall = 16777216         # 64GB in pages (4KB each)
kernel.shmmni = 4096
kernel.sem = 250 32000 100 128

# Network optimizations
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 5000

# Virtual memory settings
vm.swappiness = 1                # Minimize swapping
vm.dirty_expire_centisecs = 500
vm.dirty_writeback_centisecs = 250
vm.dirty_ratio = 10
vm.dirty_background_ratio = 3

# File system settings  
fs.file-max = 65536
EOF

# Apply kernel parameters
sysctl -p

# PostgreSQL service limits
cat >> /etc/security/limits.conf << 'EOF'
postgres soft nofile 65536
postgres hard nofile 65536
postgres soft nproc 32768
postgres hard nproc 32768
EOF

# Disable transparent huge pages (recommended for databases)
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
```

## 3. Performance Tuning and Optimization

### 3.1 Connection Pooling with PgBouncer

```ini
# pgbouncer.ini
[databases]
pricing_agent_db = host=localhost port=5432 dbname=pricing_agent_db

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
admin_users = postgres
stats_users = stats, postgres

# Pool settings
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 10
max_db_connections = 150

# Timeouts
server_reset_query = DISCARD ALL
server_check_delay = 30
server_lifetime = 3600
server_idle_timeout = 600
client_idle_timeout = 300

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
```

### 3.2 Query Performance Optimization

**Regular Maintenance Script**:
```sql
-- maintenance_queries.sql

-- Analyze table statistics (run daily)
ANALYZE materials;
ANALYZE suppliers;
ANALYZE pricing_history;
ANALYZE quotes;
ANALYZE contracts;

-- Update query planner statistics
UPDATE pg_class SET reltuples = (
    SELECT count(*) FROM pricing_history
) WHERE relname = 'pricing_history';

-- Check for unused indexes
SELECT 
    schemaname, 
    tablename, 
    indexname, 
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes 
WHERE idx_scan = 0 
    AND pg_relation_size(indexrelid) > 1024*1024  -- > 1MB
ORDER BY pg_relation_size(indexrelid) DESC;

-- Find slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    stddev_time,
    rows
FROM pg_stat_statements 
WHERE mean_time > 1000  -- > 1 second
ORDER BY mean_time DESC
LIMIT 20;
```

### 3.3 TimescaleDB Optimization

**Chunk Management**:
```sql
-- Optimize chunk size for different tables
SELECT set_chunk_time_interval('pricing_history', INTERVAL '7 days');
SELECT set_chunk_time_interval('market_data', INTERVAL '1 hour');
SELECT set_chunk_time_interval('ml_features', INTERVAL '1 day');
SELECT set_chunk_time_interval('audit_log', INTERVAL '1 day');

-- Enable compression on older chunks
SELECT add_compression_policy('pricing_history', INTERVAL '7 days');
SELECT add_compression_policy('market_data', INTERVAL '1 day');
SELECT add_compression_policy('ml_features', INTERVAL '30 days');
SELECT add_compression_policy('audit_log', INTERVAL '30 days');

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('pricing_daily_avg',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '15 minutes'
);
```

## 4. Monitoring and Alerting Setup

### 4.1 Prometheus Metrics Collection

```yaml
# docker-compose.yml for monitoring stack
version: '3.8'
services:
  postgres_exporter:
    image: quay.io/prometheuscommunity/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://monitoring:password@localhost:5432/pricing_agent_db?sslmode=disable"
    ports:
      - "9187:9187"
    command:
      - --log.level=info
      - --web.telemetry-path=/metrics
      
  timescaledb_exporter:
    image: timescale/promscale:latest
    environment:
      PROMSCALE_DB_URI: postgres://monitoring:password@localhost:5432/pricing_agent_db
    ports:
      - "9201:9201"
      
  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - --path.procfs=/host/proc
      - --path.rootfs=/rootfs
      - --path.sysfs=/host/sys
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
```

### 4.2 Critical Alerts Configuration

```yaml
# alerts.yml
groups:
- name: database_alerts
  rules:
  - alert: DatabaseDown
    expr: pg_up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "PostgreSQL database is down"
      
  - alert: HighConnectionCount
    expr: pg_stat_activity_count > 180
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High number of database connections"
      
  - alert: SlowQuery
    expr: pg_stat_activity_max_tx_duration > 300
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Long running query detected"
      
  - alert: ReplicationLag
    expr: pg_replication_lag > 60
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Database replication lag is high"
      
  - alert: DiskSpaceUsage
    expr: (node_filesystem_avail_bytes{mountpoint="/var/lib/postgresql"} / node_filesystem_size_bytes{mountpoint="/var/lib/postgresql"}) < 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Database disk space is running low"
```

## 5. Deployment Scripts

### 5.1 Zero-Downtime Migration Script

```bash
#!/bin/bash
# zero_downtime_migration.sh

set -e

DB_HOST="localhost"
DB_NAME="pricing_agent_db"
DB_USER="pricing_agent"
MIGRATION_PATH="/opt/pricing_agent/migrations"

echo "Starting zero-downtime migration process..."

# 1. Create read replica for testing
echo "Setting up test replica..."
pg_basebackup -h $DB_HOST -D /tmp/test_replica -U replicator -v -P -R

# 2. Apply migrations to test replica
echo "Testing migrations on replica..."
for migration in $MIGRATION_PATH/*.sql; do
    echo "Applying $(basename $migration)..."
    psql -h localhost -p 15432 -U $DB_USER -d $DB_NAME -f $migration
done

# 3. Validate migrations
echo "Validating migrations..."
psql -h localhost -p 15432 -U $DB_USER -d $DB_NAME -c "SELECT * FROM validate_schema_integrity();"

# 4. Apply to production during maintenance window
echo "Applying to production..."
for migration in $MIGRATION_PATH/*.sql; do
    echo "Applying $(basename $migration) to production..."
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f $migration
done

echo "Migration completed successfully!"
```

### 5.2 Health Check Script

```bash
#!/bin/bash
# health_check.sh

DB_HOST="localhost"
DB_NAME="pricing_agent_db"
DB_USER="pricing_agent"

# Function to check database connectivity
check_db_connection() {
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;" > /dev/null 2>&1
    return $?
}

# Function to check replication lag
check_replication_lag() {
    local lag=$(psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::int;")
    if [ "$lag" -gt 300 ]; then
        echo "CRITICAL: Replication lag is ${lag} seconds"
        return 1
    fi
    return 0
}

# Function to check TimescaleDB health
check_timescaledb() {
    local chunks=$(psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT count(*) FROM timescaledb_information.chunks;")
    if [ "$chunks" -lt 1 ]; then
        echo "WARNING: No TimescaleDB chunks found"
        return 1
    fi
    return 0
}

# Run all health checks
echo "Running database health checks..."

if check_db_connection; then
    echo "✓ Database connection: OK"
else
    echo "✗ Database connection: FAILED"
    exit 1
fi

if check_replication_lag; then
    echo "✓ Replication lag: OK"
else
    echo "✗ Replication lag: HIGH"
fi

if check_timescaledb; then
    echo "✓ TimescaleDB: OK"
else
    echo "✗ TimescaleDB: WARNING"
fi

echo "Health check completed."
```

## 6. Performance Benchmarking

### 6.1 Load Testing Scripts

```bash
#!/bin/bash
# load_test.sh

# Test concurrent connections
for i in {1..100}; do
    (
        psql -h localhost -U pricing_agent -d pricing_agent_db -c "
            SELECT pg_sleep(0.1);
            INSERT INTO pricing_history (organization_id, material_id, price, recorded_at)
            VALUES (1, $i, random()*1000, NOW());
        " &
    )
done
wait

# Test query performance
echo "Testing query performance..."
time psql -h localhost -U pricing_agent -d pricing_agent_db -c "
    SELECT 
        m.name,
        AVG(ph.price) as avg_price,
        COUNT(*) as price_count
    FROM pricing_history ph
    JOIN materials m ON ph.material_id = m.id
    WHERE ph.recorded_at >= NOW() - INTERVAL '30 days'
    GROUP BY m.name
    ORDER BY avg_price DESC
    LIMIT 100;
"
```

### 6.2 Performance Baseline Metrics

**Expected Performance Targets**:
- **Insert Rate**: 10,000+ records/second (pricing data)
- **Query Response**: < 500ms for 95th percentile
- **Connection Time**: < 100ms
- **Replication Lag**: < 30 seconds
- **Backup Time**: < 2 hours for full backup
- **Recovery Time**: < 4 hours for complete restore

## 7. Troubleshooting Guide

### 7.1 Common Performance Issues

**Slow Queries**:
```sql
-- Find blocking queries
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**High CPU Usage**:
```sql
-- Find CPU-intensive queries
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    (total_time/sum(total_time) OVER()) * 100 AS percentage_cpu
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;
```

**Memory Issues**:
```sql
-- Check work_mem usage
SELECT 
    query,
    calls,
    temp_blks_read + temp_blks_written as temp_blocks,
    temp_blks_read + temp_blks_written > 0 as uses_temp
FROM pg_stat_statements
WHERE temp_blks_read + temp_blks_written > 0
ORDER BY temp_blks_read + temp_blks_written DESC;
```

---

This comprehensive deployment and tuning guide provides the foundation for running the AI Pricing Agent database at scale with optimal performance and reliability.
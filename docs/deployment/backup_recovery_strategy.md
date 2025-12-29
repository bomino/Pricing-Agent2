# Database Backup and Recovery Strategy
## AI Pricing Agent - PostgreSQL with TimescaleDB

### Executive Summary

This document outlines a comprehensive backup and recovery strategy for the AI Pricing Agent database system, designed to ensure:
- **RPO (Recovery Point Objective)**: Maximum 15 minutes of data loss
- **RTO (Recovery Time Objective)**: Maximum 4 hours for complete system recovery
- **99.9% uptime** with automated failover capabilities
- **7+ years** of historical data retention for compliance

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Primary DB    │    │   Streaming      │    │  Backup Storage │
│ PostgreSQL 16   │────│   Replica        │────│  (S3/Azure)     │
│ + TimescaleDB   │    │   (Hot Standby)  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         ├─ WAL-E Continuous      ├─ Point-in-Time       ├─ Long-term
         ├─ Base Backups (Daily)  ├─ Recovery Ready      ├─ Archival
         └─ Monitoring/Alerts     └─ Read Replicas       └─ Compliance
```

## 1. Backup Strategy

### 1.1 Continuous WAL Archiving

**Implementation**: WAL-E or WAL-G with cloud storage
```bash
# WAL-E Configuration
export WALE_S3_PREFIX="s3://pricing-agent-backups/wal"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# PostgreSQL Configuration
archive_mode = on
archive_command = 'wal-e wal-push %p'
archive_timeout = 300  # 5 minutes
```

**Features**:
- Continuous WAL streaming to cloud storage
- 15-minute maximum data loss (RPO)
- Encrypted in transit and at rest
- Cross-region replication for disaster recovery

### 1.2 Base Backup Schedule

**Daily Full Backups**:
```bash
#!/bin/bash
# daily_backup.sh
export BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
export BACKUP_PATH="s3://pricing-agent-backups/base/${BACKUP_DATE}"

# Create base backup with WAL-E
wal-e backup-push /var/lib/postgresql/16/main

# Verify backup integrity
wal-e backup-list | tail -5

# Cleanup old backups (retain 30 days)
wal-e delete retain 30
```

**Weekly Full System Backups**:
- Complete database cluster backup
- Configuration files and certificates
- Application code and dependencies
- Stored in separate geographical location

### 1.3 TimescaleDB-Specific Backups

**Compressed Chunk Backups**:
```sql
-- Backup compressed chunks separately for efficiency
SELECT chunk_name, compression_status, compressed_chunk_id
FROM timescaledb_information.chunks 
WHERE is_compressed = true;

-- Export specific chunks for archival
pg_dump --table=_timescaledb_internal._hyper_*_chunk \
        --compress=9 \
        pricing_agent_db > chunk_backup_${DATE}.sql.gz
```

**Continuous Aggregate Refresh**:
```sql
-- Ensure continuous aggregates are consistent
CALL refresh_continuous_aggregate('pricing_daily_avg', NULL, NULL);
CALL refresh_continuous_aggregate('pricing_weekly_avg', NULL, NULL);
CALL refresh_continuous_aggregate('pricing_monthly_avg', NULL, NULL);
```

## 2. Recovery Procedures

### 2.1 Point-in-Time Recovery (PITR)

**Scenario**: Recover to specific timestamp before data corruption

```bash
#!/bin/bash
# pitr_recovery.sh

RECOVERY_TARGET="2024-01-15 14:30:00"
RECOVERY_PATH="/var/lib/postgresql/16/recovery"

# Stop PostgreSQL
systemctl stop postgresql

# Clear data directory
rm -rf /var/lib/postgresql/16/main/*

# Restore base backup
wal-e backup-fetch /var/lib/postgresql/16/main LATEST

# Create recovery configuration
cat > /var/lib/postgresql/16/main/recovery.conf << EOF
restore_command = 'wal-e wal-fetch "%f" "%p"'
recovery_target_time = '${RECOVERY_TARGET}'
recovery_target_action = 'promote'
EOF

# Start recovery
systemctl start postgresql

# Monitor recovery progress
tail -f /var/log/postgresql/postgresql-16-main.log
```

### 2.2 Full System Recovery

**Disaster Recovery Steps**:

1. **Infrastructure Setup**:
```bash
# Provision new PostgreSQL + TimescaleDB instance
apt-get update
apt-get install postgresql-16 timescaledb-2-postgresql-16

# Install extensions
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

2. **Data Recovery**:
```bash
# Restore from latest base backup
wal-e backup-fetch /var/lib/postgresql/16/main LATEST

# Apply WAL files up to failure point
# PostgreSQL will automatically fetch required WAL files
systemctl start postgresql
```

3. **Verification**:
```sql
-- Verify data consistency
SELECT * FROM get_migration_status();
SELECT * FROM validate_schema_integrity();

-- Check TimescaleDB hypertables
SELECT hypertable_name, num_chunks 
FROM timescaledb_information.hypertables;

-- Verify recent data
SELECT COUNT(*), MAX(recorded_at) 
FROM pricing_history 
WHERE recorded_at >= NOW() - INTERVAL '1 hour';
```

### 2.3 Read Replica Recovery

**Hot Standby Configuration**:
```bash
# postgresql.conf on replica
hot_standby = on
max_standby_streaming_delay = 30s
max_standby_archive_delay = 60s

# recovery.conf on replica
standby_mode = 'on'
primary_conninfo = 'host=primary-db port=5432 user=replicator'
restore_command = 'wal-e wal-fetch "%f" "%p"'
```

**Failover Process**:
```bash
#!/bin/bash
# failover.sh

# Promote replica to primary
sudo -u postgres /usr/lib/postgresql/16/bin/pg_ctl promote \
    -D /var/lib/postgresql/16/main

# Update application connection strings
# Update DNS records to point to new primary

# Setup new replica from failed primary (after repair)
```

## 3. Monitoring and Alerting

### 3.1 Backup Monitoring

**Key Metrics**:
- WAL archive lag time
- Backup completion status
- Storage utilization
- Replication lag

**Monitoring Script**:
```bash
#!/bin/bash
# backup_monitor.sh

# Check WAL archive lag
LAG=$(psql -t -c "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xlog_receive_location()::timestamp))")

if (( $(echo "$LAG > 900" | bc -l) )); then
    echo "CRITICAL: WAL archive lag is ${LAG} seconds" | \
        mail -s "Backup Alert" alerts@yourcompany.com
fi

# Check backup status
LAST_BACKUP=$(wal-e backup-list | tail -1 | awk '{print $2}')
BACKUP_AGE=$(date -d "${LAST_BACKUP}" +%s)
CURRENT_TIME=$(date +%s)
AGE_HOURS=$(( (CURRENT_TIME - BACKUP_AGE) / 3600 ))

if (( AGE_HOURS > 25 )); then
    echo "WARNING: Last backup is ${AGE_HOURS} hours old" | \
        mail -s "Backup Alert" alerts@yourcompany.com
fi
```

### 3.2 Alerting Configuration

**Prometheus Metrics**:
```yaml
# prometheus.yml
- job_name: 'postgresql'
  static_configs:
    - targets: ['localhost:9187']
  metrics_path: /metrics
  scrape_interval: 15s

- job_name: 'timescaledb'
  static_configs:
    - targets: ['localhost:9188']
  metrics_path: /metrics
  scrape_interval: 30s
```

**Alert Rules**:
```yaml
# backup_alerts.yml
groups:
- name: database.rules
  rules:
  - alert: BackupLag
    expr: pg_wal_archive_lag_seconds > 900
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Database backup lag is high"
      
  - alert: ReplicationLag
    expr: pg_replication_lag_seconds > 300
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Database replication lag is high"
```

## 4. Data Archival Strategy

### 4.1 TimescaleDB Data Retention

**Automated Retention Policies**:
```sql
-- Pricing data: 7 years retention
SELECT add_retention_policy('pricing_history', INTERVAL '7 years');

-- Market data: 2 years (aggregates retained longer)
SELECT add_retention_policy('market_data', INTERVAL '2 years');

-- Audit logs: 10 years for compliance
SELECT add_retention_policy('audit_log', INTERVAL '10 years');

-- ML features: 3 years
SELECT add_retention_policy('ml_features', INTERVAL '3 years');
```

**Compression for Long-term Storage**:
```sql
-- Enable compression on older chunks
ALTER TABLE pricing_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'organization_id, material_id, supplier_id',
    timescaledb.compress_orderby = 'recorded_at DESC'
);

-- Compress chunks older than 7 days
SELECT add_compression_policy('pricing_history', INTERVAL '7 days');
```

### 4.2 Cold Storage Migration

**Archive to S3 Glacier**:
```bash
#!/bin/bash
# archive_old_data.sh

# Export data older than 5 years to cold storage
ARCHIVE_DATE=$(date -d '5 years ago' +%Y-%m-%d)

# Create compressed export
pg_dump --table=pricing_history \
        --where="recorded_at < '${ARCHIVE_DATE}'" \
        --compress=9 \
        pricing_agent_db > pricing_archive_${ARCHIVE_DATE}.sql.gz

# Upload to S3 Glacier
aws s3 cp pricing_archive_${ARCHIVE_DATE}.sql.gz \
    s3://pricing-agent-archive/glacier/ \
    --storage-class GLACIER

# Verify upload and remove from primary storage
# (Only after verification)
```

## 5. Testing and Validation

### 5.1 Regular Recovery Testing

**Monthly Recovery Drills**:
```bash
#!/bin/bash
# recovery_test.sh

# Create test environment
docker run -d --name recovery-test \
    -e POSTGRES_PASSWORD=test123 \
    -p 15432:5432 \
    timescale/timescaledb:latest-pg16

# Restore backup to test environment
wal-e backup-fetch /var/lib/postgresql/data LATEST

# Run validation queries
psql -h localhost -p 15432 -U postgres -f recovery_validation.sql

# Cleanup test environment
docker stop recovery-test && docker rm recovery-test
```

**Validation Queries**:
```sql
-- recovery_validation.sql
-- Check data consistency
SELECT 
    COUNT(*) as total_records,
    MIN(recorded_at) as earliest_date,
    MAX(recorded_at) as latest_date
FROM pricing_history;

-- Verify constraints
SELECT 
    table_name,
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'public'
    AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE');

-- Check TimescaleDB functionality
SELECT hypertable_name, num_chunks 
FROM timescaledb_information.hypertables;
```

### 5.2 Performance Benchmarking

**Backup Performance**:
```bash
# Measure backup speed
time wal-e backup-push /var/lib/postgresql/16/main

# Measure restore speed
time wal-e backup-fetch /tmp/restore_test LATEST
```

**Recovery Time Testing**:
- Document recovery times for different scenarios
- Test partial recovery vs full recovery
- Validate RTO/RPO objectives under load

## 6. Security Considerations

### 6.1 Backup Encryption

**Encryption in Transit**:
```bash
# WAL-E with encryption
export WALE_GPG_KEY_ID="backup-key-id"
wal-e backup-push --encrypt /var/lib/postgresql/16/main
```

**Encryption at Rest**:
- S3 server-side encryption (SSE-S3/SSE-KMS)
- Application-level encryption for sensitive data
- Regular key rotation schedule

### 6.2 Access Control

**Backup Access Permissions**:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::account:user/backup-service"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::pricing-agent-backups/*"
        }
    ]
}
```

## 7. Compliance and Auditing

### 7.1 Audit Trail

**Backup Audit Log**:
```sql
-- Track backup operations
CREATE TABLE backup_audit_log (
    id BIGSERIAL PRIMARY KEY,
    operation VARCHAR(50) NOT NULL,
    backup_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    size_bytes BIGINT,
    location TEXT,
    checksum VARCHAR(255),
    performed_by VARCHAR(255),
    status VARCHAR(20) DEFAULT 'RUNNING'
);
```

### 7.2 Retention Compliance

**Legal Hold Process**:
```sql
-- Mark data for legal hold (prevent deletion)
UPDATE pricing_history 
SET metadata = metadata || '{"legal_hold": true}'::jsonb
WHERE organization_id = ? 
    AND recorded_at BETWEEN ? AND ?;

-- Custom retention for legal hold data
CREATE TABLE legal_hold_exceptions (
    table_name VARCHAR(255),
    record_id BIGINT,
    hold_reason TEXT,
    hold_until DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 8. Operational Procedures

### 8.1 Daily Operations Checklist

- [ ] Verify overnight backups completed successfully
- [ ] Check WAL archive lag (should be < 5 minutes)
- [ ] Monitor replication lag on read replicas
- [ ] Review backup storage utilization
- [ ] Check for any failed compression policies
- [ ] Validate continuous aggregate refreshes

### 8.2 Emergency Contacts

**Escalation Matrix**:
1. **Level 1**: Database Administrator (On-call 24/7)
2. **Level 2**: Infrastructure Team Lead
3. **Level 3**: CTO/Technical Director
4. **Level 4**: External Database Consultant

### 8.3 Documentation

**Required Documentation**:
- Current backup schedules and retention policies
- Recovery procedures with step-by-step instructions
- Emergency contact information
- Compliance requirements and audit trails
- Performance benchmarks and SLA metrics

---

## Summary

This backup and recovery strategy provides:

- **Comprehensive Coverage**: All data types and storage tiers
- **Automated Operations**: Minimal manual intervention required  
- **Compliance Ready**: Meets regulatory requirements for data retention
- **Tested and Validated**: Regular testing ensures reliability
- **Scalable Architecture**: Grows with business needs

The strategy supports the AI Pricing Agent's requirements for high availability, data integrity, and regulatory compliance while maintaining optimal performance and cost-effectiveness.
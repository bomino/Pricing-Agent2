#!/usr/bin/env python3
"""
Backup management script for the Pricing Agent system.
Handles database backups, model artifact backups, and backup verification.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


@dataclass
class BackupResult:
    """Result of a backup operation"""
    backup_type: str
    status: str  # 'success', 'failed', 'warning'
    backup_name: str
    size_bytes: int
    duration_seconds: float
    timestamp: str
    location: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class BackupVerification:
    """Result of backup verification"""
    backup_name: str
    verification_type: str
    status: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


class BackupManager:
    """Comprehensive backup management for Pricing Agent"""
    
    def __init__(self, environment: str, namespace: str = None):
        self.environment = environment
        self.namespace = namespace or f"pricing-agent-{environment}"
        self.logger = logging.getLogger(__name__)
        
        # AWS S3 configuration
        self.s3_client = None
        self.backup_bucket = os.getenv('DATABASE_BACKUP_S3')
        self.model_bucket = os.getenv('MODEL_ARTIFACTS_S3')
        
        # Initialize S3 client if credentials available
        try:
            self.s3_client = boto3.client('s3')
            # Test connection
            self.s3_client.head_bucket(Bucket=self.backup_bucket)
        except (NoCredentialsError, ClientError) as e:
            self.logger.warning(f"S3 not available: {e}")
            self.s3_client = None

    def _generate_backup_name(self, backup_type: str, prefix: str = "") -> str:
        """Generate a unique backup name"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        env_prefix = f"{self.environment}-" if self.environment != "production" else ""
        name_prefix = f"{prefix}-" if prefix else ""
        return f"{env_prefix}{name_prefix}{backup_type}-{timestamp}"

    def _run_kubectl_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Execute a kubectl command"""
        full_command = ["kubectl"] + command + ["-n", self.namespace]
        self.logger.debug(f"Running command: {' '.join(full_command)}")
        
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minutes timeout
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"kubectl command failed: {e}")
            self.logger.error(f"stdout: {e.stdout}")
            self.logger.error(f"stderr: {e.stderr}")
            raise
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"kubectl command timed out: {e}")
            raise

    async def backup_database(self, retention_days: int = 30) -> BackupResult:
        """Create a database backup"""
        self.logger.info("Starting database backup...")
        start_time = time.time()
        
        backup_name = self._generate_backup_name("postgres", "database")
        local_path = f"/tmp/{backup_name}.sql.gz"
        
        try:
            # Get database credentials from secrets
            secret_result = self._run_kubectl_command([
                "get", "secret", "pricing-agent-secrets", 
                "-o", "jsonpath={.data.POSTGRES_PASSWORD}"
            ])
            
            # Create database backup using kubectl exec
            backup_command = [
                "exec", "deployment/pricing-postgres", "--",
                "sh", "-c",
                f"pg_dump -U pricing_user -h localhost pricing_agent | gzip > /tmp/{backup_name}.sql.gz"
            ]
            
            self._run_kubectl_command(backup_command)
            
            # Copy backup from pod to local machine
            copy_command = [
                "cp", f"pricing-postgres-0:/tmp/{backup_name}.sql.gz", local_path
            ]
            
            self._run_kubectl_command(copy_command)
            
            # Get backup size
            backup_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            
            # Upload to S3 if available
            s3_location = None
            if self.s3_client and self.backup_bucket:
                s3_key = f"database-backups/{backup_name}.sql.gz"
                try:
                    self.s3_client.upload_file(local_path, self.backup_bucket, s3_key)
                    s3_location = f"s3://{self.backup_bucket}/{s3_key}"
                    self.logger.info(f"Database backup uploaded to S3: {s3_location}")
                    
                    # Clean up local file
                    os.remove(local_path)
                except ClientError as e:
                    self.logger.error(f"Failed to upload to S3: {e}")
                    s3_location = local_path  # Keep local copy
            else:
                s3_location = local_path
                self.logger.info(f"Database backup saved locally: {local_path}")
            
            # Clean up backup from pod
            cleanup_command = [
                "exec", "deployment/pricing-postgres", "--",
                "rm", "-f", f"/tmp/{backup_name}.sql.gz"
            ]
            
            try:
                self._run_kubectl_command(cleanup_command)
            except Exception as e:
                self.logger.warning(f"Failed to clean up backup from pod: {e}")
            
            duration = time.time() - start_time
            
            return BackupResult(
                backup_type="database",
                status="success",
                backup_name=backup_name,
                size_bytes=backup_size,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location=s3_location,
                details={
                    "database": "pricing_agent",
                    "compression": "gzip",
                    "retention_days": retention_days
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Database backup failed: {e}")
            
            return BackupResult(
                backup_type="database",
                status="failed",
                backup_name=backup_name,
                size_bytes=0,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location="",
                details={"error": str(e)}
            )

    async def backup_redis_data(self) -> BackupResult:
        """Create a Redis data backup"""
        self.logger.info("Starting Redis data backup...")
        start_time = time.time()
        
        backup_name = self._generate_backup_name("redis", "data")
        local_path = f"/tmp/{backup_name}.rdb"
        
        try:
            # Create Redis backup using BGSAVE
            bgsave_command = [
                "exec", "deployment/pricing-redis", "--",
                "redis-cli", "BGSAVE"
            ]
            
            self._run_kubectl_command(bgsave_command)
            
            # Wait for backup to complete
            await asyncio.sleep(5)
            
            # Check if backup is complete
            check_command = [
                "exec", "deployment/pricing-redis", "--",
                "redis-cli", "LASTSAVE"
            ]
            
            # Copy the RDB file
            copy_command = [
                "cp", f"pricing-redis-0:/data/dump.rdb", local_path
            ]
            
            self._run_kubectl_command(copy_command)
            
            backup_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            
            # Upload to S3 if available
            s3_location = None
            if self.s3_client and self.backup_bucket:
                s3_key = f"redis-backups/{backup_name}.rdb"
                try:
                    self.s3_client.upload_file(local_path, self.backup_bucket, s3_key)
                    s3_location = f"s3://{self.backup_bucket}/{s3_key}"
                    self.logger.info(f"Redis backup uploaded to S3: {s3_location}")
                    os.remove(local_path)
                except ClientError as e:
                    self.logger.error(f"Failed to upload Redis backup to S3: {e}")
                    s3_location = local_path
            else:
                s3_location = local_path
            
            duration = time.time() - start_time
            
            return BackupResult(
                backup_type="redis",
                status="success",
                backup_name=backup_name,
                size_bytes=backup_size,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location=s3_location,
                details={"backup_method": "BGSAVE"}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Redis backup failed: {e}")
            
            return BackupResult(
                backup_type="redis",
                status="failed",
                backup_name=backup_name,
                size_bytes=0,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location="",
                details={"error": str(e)}
            )

    async def backup_ml_models(self) -> BackupResult:
        """Backup ML model artifacts"""
        self.logger.info("Starting ML model artifacts backup...")
        start_time = time.time()
        
        backup_name = self._generate_backup_name("models", "ml-artifacts")
        local_path = f"/tmp/{backup_name}.tar.gz"
        
        try:
            # Create tar archive of model artifacts from FastAPI pod
            tar_command = [
                "exec", "deployment/pricing-fastapi", "--",
                "tar", "-czf", f"/tmp/{backup_name}.tar.gz",
                "-C", "/app/fastapi_ml/ml_artifacts", "."
            ]
            
            self._run_kubectl_command(tar_command)
            
            # Copy backup from pod
            copy_command = [
                "cp", f"pricing-fastapi-0:/tmp/{backup_name}.tar.gz", local_path
            ]
            
            self._run_kubectl_command(copy_command)
            
            backup_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            
            # Upload to S3 if available
            s3_location = None
            if self.s3_client and self.model_bucket:
                s3_key = f"model-backups/{backup_name}.tar.gz"
                try:
                    self.s3_client.upload_file(local_path, self.model_bucket, s3_key)
                    s3_location = f"s3://{self.model_bucket}/{s3_key}"
                    self.logger.info(f"ML models backup uploaded to S3: {s3_location}")
                    os.remove(local_path)
                except ClientError as e:
                    self.logger.error(f"Failed to upload ML models to S3: {e}")
                    s3_location = local_path
            else:
                s3_location = local_path
            
            # Clean up from pod
            cleanup_command = [
                "exec", "deployment/pricing-fastapi", "--",
                "rm", "-f", f"/tmp/{backup_name}.tar.gz"
            ]
            
            try:
                self._run_kubectl_command(cleanup_command)
            except Exception:
                pass  # Non-critical
            
            duration = time.time() - start_time
            
            return BackupResult(
                backup_type="ml_models",
                status="success",
                backup_name=backup_name,
                size_bytes=backup_size,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location=s3_location,
                details={"compression": "gzip", "format": "tar"}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"ML models backup failed: {e}")
            
            return BackupResult(
                backup_type="ml_models",
                status="failed",
                backup_name=backup_name,
                size_bytes=0,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location="",
                details={"error": str(e)}
            )

    async def backup_kubernetes_manifests(self) -> BackupResult:
        """Backup Kubernetes configuration"""
        self.logger.info("Starting Kubernetes manifests backup...")
        start_time = time.time()
        
        backup_name = self._generate_backup_name("k8s", "manifests")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                backup_dir = Path(temp_dir) / backup_name
                backup_dir.mkdir()
                
                # Export all resources from namespace
                resources = [
                    "configmaps", "secrets", "deployments", "services",
                    "ingresses", "persistentvolumeclaims", "horizontalpodautoscalers"
                ]
                
                for resource in resources:
                    try:
                        result = self._run_kubectl_command([
                            "get", resource, "-o", "yaml"
                        ])
                        
                        output_file = backup_dir / f"{resource}.yaml"
                        with open(output_file, 'w') as f:
                            f.write(result.stdout)
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to export {resource}: {e}")
                
                # Create tar archive
                local_path = f"/tmp/{backup_name}.tar.gz"
                subprocess.run([
                    "tar", "-czf", local_path, "-C", temp_dir, backup_name
                ], check=True)
                
                backup_size = os.path.getsize(local_path)
                
                # Upload to S3 if available
                s3_location = None
                if self.s3_client and self.backup_bucket:
                    s3_key = f"k8s-manifests/{backup_name}.tar.gz"
                    try:
                        self.s3_client.upload_file(local_path, self.backup_bucket, s3_key)
                        s3_location = f"s3://{self.backup_bucket}/{s3_key}"
                        os.remove(local_path)
                    except ClientError as e:
                        self.logger.error(f"Failed to upload K8s manifests to S3: {e}")
                        s3_location = local_path
                else:
                    s3_location = local_path
                
                duration = time.time() - start_time
                
                return BackupResult(
                    backup_type="kubernetes_manifests",
                    status="success",
                    backup_name=backup_name,
                    size_bytes=backup_size,
                    duration_seconds=duration,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    location=s3_location,
                    details={"resources": resources, "namespace": self.namespace}
                )
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Kubernetes manifests backup failed: {e}")
            
            return BackupResult(
                backup_type="kubernetes_manifests",
                status="failed",
                backup_name=backup_name,
                size_bytes=0,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location="",
                details={"error": str(e)}
            )

    async def verify_database_backup(self, backup_location: str) -> BackupVerification:
        """Verify database backup integrity"""
        self.logger.info(f"Verifying database backup: {backup_location}")
        
        try:
            # For S3 backups, download temporarily
            if backup_location.startswith('s3://'):
                with tempfile.NamedTemporaryFile(suffix='.sql.gz', delete=False) as temp_file:
                    bucket, key = backup_location[5:].split('/', 1)
                    self.s3_client.download_file(bucket, key, temp_file.name)
                    local_path = temp_file.name
            else:
                local_path = backup_location
            
            # Check if file exists and is readable
            if not os.path.exists(local_path):
                return BackupVerification(
                    backup_name=os.path.basename(backup_location),
                    verification_type="file_integrity",
                    status="failed",
                    message="Backup file not found",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            
            # Check if gzip file is valid
            result = subprocess.run(
                ["gunzip", "-t", local_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return BackupVerification(
                    backup_name=os.path.basename(backup_location),
                    verification_type="file_integrity",
                    status="failed",
                    message=f"Backup file is corrupted: {result.stderr}",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            # Clean up temporary file if downloaded from S3
            if backup_location.startswith('s3://') and local_path.startswith('/tmp/'):
                os.unlink(local_path)
            
            return BackupVerification(
                backup_name=os.path.basename(backup_location),
                verification_type="file_integrity",
                status="success",
                message=f"Backup file is valid and readable (size: {file_size} bytes)",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={"file_size": file_size}
            )
            
        except Exception as e:
            return BackupVerification(
                backup_name=os.path.basename(backup_location),
                verification_type="file_integrity",
                status="failed",
                message=f"Verification failed: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={"error": str(e)}
            )

    async def list_backups(self, backup_type: str = None) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = []
        
        if not self.s3_client or not self.backup_bucket:
            self.logger.warning("S3 not available, cannot list backups")
            return backups
        
        try:
            # List objects in S3 bucket
            prefixes = []
            if backup_type:
                prefixes.append(f"{backup_type}-backups/")
            else:
                prefixes = ["database-backups/", "redis-backups/", "k8s-manifests/"]
            
            for prefix in prefixes:
                try:
                    response = self.s3_client.list_objects_v2(
                        Bucket=self.backup_bucket,
                        Prefix=prefix
                    )
                    
                    for obj in response.get('Contents', []):
                        backup_info = {
                            'name': obj['Key'].split('/')[-1],
                            'type': prefix.rstrip('-backups/'),
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'location': f"s3://{self.backup_bucket}/{obj['Key']}"
                        }
                        backups.append(backup_info)
                        
                except ClientError as e:
                    self.logger.error(f"Failed to list backups with prefix {prefix}: {e}")
            
            # Sort by last modified (newest first)
            backups.sort(key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
        
        return backups

    async def cleanup_old_backups(self, retention_days: int = 30) -> Dict[str, Any]:
        """Clean up old backups based on retention policy"""
        self.logger.info(f"Cleaning up backups older than {retention_days} days")
        
        if not self.s3_client or not self.backup_bucket:
            return {"status": "skipped", "reason": "S3 not available"}
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted_backups = []
        errors = []
        
        try:
            # Get all backups
            response = self.s3_client.list_objects_v2(Bucket=self.backup_bucket)
            
            for obj in response.get('Contents', []):
                if obj['LastModified'] < cutoff_date:
                    try:
                        self.s3_client.delete_object(
                            Bucket=self.backup_bucket,
                            Key=obj['Key']
                        )
                        deleted_backups.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat()
                        })
                        self.logger.info(f"Deleted old backup: {obj['Key']}")
                    except ClientError as e:
                        error_msg = f"Failed to delete {obj['Key']}: {e}"
                        errors.append(error_msg)
                        self.logger.error(error_msg)
            
            return {
                "status": "completed",
                "deleted_count": len(deleted_backups),
                "deleted_backups": deleted_backups,
                "errors": errors,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "retention_days": retention_days
            }


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Backup management for Pricing Agent system'
    )
    parser.add_argument(
        '--environment', 
        required=True, 
        choices=['staging', 'production', 'development'],
        help='Environment name'
    )
    parser.add_argument(
        '--namespace', 
        help='Kubernetes namespace (auto-detected if not provided)'
    )
    parser.add_argument(
        '--operation', 
        required=True,
        choices=['backup', 'verify', 'list', 'cleanup'],
        help='Operation to perform'
    )
    parser.add_argument(
        '--backup-type', 
        choices=['database', 'redis', 'ml_models', 'kubernetes_manifests', 'all'],
        default='all',
        help='Type of backup to create/manage'
    )
    parser.add_argument(
        '--retention-days', 
        type=int, 
        default=30,
        help='Backup retention in days'
    )
    parser.add_argument(
        '--backup-location', 
        help='Backup location for verification'
    )
    parser.add_argument(
        '--output-format', 
        choices=['json', 'text'], 
        default='text',
        help='Output format'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true', 
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        manager = BackupManager(args.environment, args.namespace)
        
        if args.operation == 'backup':
            results = []
            
            if args.backup_type == 'all':
                backup_types = ['database', 'redis', 'ml_models', 'kubernetes_manifests']
            else:
                backup_types = [args.backup_type]
            
            for backup_type in backup_types:
                if backup_type == 'database':
                    result = await manager.backup_database(args.retention_days)
                elif backup_type == 'redis':
                    result = await manager.backup_redis_data()
                elif backup_type == 'ml_models':
                    result = await manager.backup_ml_models()
                elif backup_type == 'kubernetes_manifests':
                    result = await manager.backup_kubernetes_manifests()
                
                results.append(result)
            
            # Output results
            if args.output_format == 'json':
                print(json.dumps([asdict(r) for r in results], indent=2))
            else:
                print(f"Backup Results for {args.environment}:")
                for result in results:
                    status_symbol = "✓" if result.status == "success" else "✗"
                    print(f"{status_symbol} {result.backup_type}: {result.status}")
                    print(f"  Name: {result.backup_name}")
                    print(f"  Size: {result.size_bytes} bytes")
                    print(f"  Duration: {result.duration_seconds:.2f}s")
                    print(f"  Location: {result.location}")
                    if result.details:
                        print(f"  Details: {result.details}")
                    print()
        
        elif args.operation == 'verify':
            if not args.backup_location:
                print("Error: --backup-location required for verify operation")
                sys.exit(1)
            
            verification = await manager.verify_database_backup(args.backup_location)
            
            if args.output_format == 'json':
                print(json.dumps(asdict(verification), indent=2))
            else:
                status_symbol = "✓" if verification.status == "success" else "✗"
                print(f"Verification Result:")
                print(f"{status_symbol} {verification.backup_name}: {verification.status}")
                print(f"  Message: {verification.message}")
                print(f"  Type: {verification.verification_type}")
                print(f"  Timestamp: {verification.timestamp}")
        
        elif args.operation == 'list':
            backups = await manager.list_backups(
                args.backup_type if args.backup_type != 'all' else None
            )
            
            if args.output_format == 'json':
                print(json.dumps(backups, indent=2))
            else:
                print(f"Available Backups ({len(backups)} total):")
                for backup in backups:
                    print(f"  {backup['name']}")
                    print(f"    Type: {backup['type']}")
                    print(f"    Size: {backup['size']} bytes")
                    print(f"    Modified: {backup['last_modified']}")
                    print(f"    Location: {backup['location']}")
                    print()
        
        elif args.operation == 'cleanup':
            result = await manager.cleanup_old_backups(args.retention_days)
            
            if args.output_format == 'json':
                print(json.dumps(result, indent=2))
            else:
                print(f"Backup Cleanup Results:")
                print(f"  Status: {result['status']}")
                if result['status'] == 'completed':
                    print(f"  Deleted: {result['deleted_count']} backups")
                    print(f"  Retention: {result['retention_days']} days")
                    if result['errors']:
                        print(f"  Errors: {len(result['errors'])}")
                        for error in result['errors']:
                            print(f"    - {error}")
                elif result['status'] == 'failed':
                    print(f"  Error: {result['error']}")
        
    except KeyboardInterrupt:
        logger.info("Backup operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backup operation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
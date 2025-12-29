"""
HashiCorp Vault Integration for Secrets Management
Provides secure storage and retrieval of secrets, API keys, and encryption keys
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

import hvac
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .security_models import SecurityEvent, EncryptionKey
from .exceptions import SecurityException

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Vault configuration"""
    url: str = "http://localhost:8200"
    token: Optional[str] = None
    role_id: Optional[str] = None
    secret_id: Optional[str] = None
    mount_point: str = "secret"
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    
    @classmethod
    def from_settings(cls) -> 'VaultConfig':
        """Create config from Django settings"""
        vault_settings = getattr(settings, 'VAULT_SETTINGS', {})
        return cls(
            url=vault_settings.get('URL', os.getenv('VAULT_ADDR', 'http://localhost:8200')),
            token=vault_settings.get('TOKEN', os.getenv('VAULT_TOKEN')),
            role_id=vault_settings.get('ROLE_ID', os.getenv('VAULT_ROLE_ID')),
            secret_id=vault_settings.get('SECRET_ID', os.getenv('VAULT_SECRET_ID')),
            mount_point=vault_settings.get('MOUNT_POINT', 'secret'),
            ca_cert_path=vault_settings.get('CA_CERT_PATH', os.getenv('VAULT_CACERT')),
            client_cert_path=vault_settings.get('CLIENT_CERT_PATH', os.getenv('VAULT_CLIENT_CERT')),
            client_key_path=vault_settings.get('CLIENT_KEY_PATH', os.getenv('VAULT_CLIENT_KEY')),
            verify_ssl=vault_settings.get('VERIFY_SSL', True),
            timeout=vault_settings.get('TIMEOUT', 30),
            max_retries=vault_settings.get('MAX_RETRIES', 3),
        )


class VaultClient:
    """HashiCorp Vault client for secrets management"""
    
    def __init__(self, config: VaultConfig = None):
        self.config = config or VaultConfig.from_settings()
        self._client = None
        self._authenticated = False
        self._token_expires_at = None
        
    def _get_client(self) -> hvac.Client:
        """Get or create Vault client"""
        if not self._client:
            client_kwargs = {
                'url': self.config.url,
                'verify': self.config.verify_ssl,
                'timeout': self.config.timeout,
            }
            
            # Add SSL certificates if configured
            if self.config.ca_cert_path:
                client_kwargs['verify'] = self.config.ca_cert_path
            
            if self.config.client_cert_path and self.config.client_key_path:
                client_kwargs['cert'] = (self.config.client_cert_path, self.config.client_key_path)
            
            self._client = hvac.Client(**client_kwargs)
        
        return self._client
    
    def authenticate(self) -> bool:
        """Authenticate with Vault"""
        if self._authenticated and self._token_expires_at and datetime.now() < self._token_expires_at:
            return True
        
        client = self._get_client()
        
        try:
            if self.config.token:
                # Token authentication
                client.token = self.config.token
                if client.is_authenticated():
                    self._authenticated = True
                    # Token doesn't expire for root tokens, set far future
                    self._token_expires_at = datetime.now() + timedelta(hours=24)
                    logger.info("Authenticated to Vault using token")
                    return True
            
            elif self.config.role_id and self.config.secret_id:
                # AppRole authentication
                auth_response = client.auth.approle.login(
                    role_id=self.config.role_id,
                    secret_id=self.config.secret_id,
                )
                
                if auth_response and 'auth' in auth_response:
                    client.token = auth_response['auth']['client_token']
                    lease_duration = auth_response['auth'].get('lease_duration', 3600)
                    self._token_expires_at = datetime.now() + timedelta(seconds=lease_duration - 300)  # 5 min buffer
                    self._authenticated = True
                    logger.info("Authenticated to Vault using AppRole")
                    return True
            
            else:
                logger.error("No authentication method configured for Vault")
                return False
                
        except Exception as e:
            logger.error(f"Failed to authenticate to Vault: {e}")
            SecurityEvent.log_event(
                'vault_auth_failure',
                description=f'Vault authentication failed: {str(e)}',
                severity='high',
                metadata={'error': str(e)}
            )
            return False
        
        return False
    
    def write_secret(self, path: str, secret_data: Dict[str, Any], mount_point: str = None) -> bool:
        """Write secret to Vault"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        mount = mount_point or self.config.mount_point
        
        try:
            # Handle different KV versions
            if self._is_kv_v2(mount):
                response = client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=mount,
                )
            else:
                response = client.secrets.kv.v1.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=mount,
                )
            
            logger.info(f"Successfully wrote secret to Vault: {mount}/{path}")
            
            # Log security event
            SecurityEvent.log_event(
                'secret_write',
                description=f'Secret written to Vault: {mount}/{path}',
                severity='medium',
                metadata={'path': f"{mount}/{path}", 'keys': list(secret_data.keys())}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write secret to Vault: {e}")
            SecurityEvent.log_event(
                'vault_write_failure',
                description=f'Failed to write secret to Vault: {str(e)}',
                severity='high',
                metadata={'path': f"{mount}/{path}", 'error': str(e)}
            )
            raise SecurityException(f"Failed to write secret: {e}")
    
    def read_secret(self, path: str, mount_point: str = None) -> Optional[Dict[str, Any]]:
        """Read secret from Vault"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        mount = mount_point or self.config.mount_point
        
        try:
            # Check cache first
            cache_key = f"vault_secret:{mount}:{path}"
            cached_secret = cache.get(cache_key)
            if cached_secret:
                return cached_secret
            
            # Handle different KV versions
            if self._is_kv_v2(mount):
                response = client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=mount,
                )
                secret_data = response['data']['data'] if response and 'data' in response else None
            else:
                response = client.secrets.kv.v1.read_secret(
                    path=path,
                    mount_point=mount,
                )
                secret_data = response['data'] if response and 'data' in response else None
            
            if secret_data:
                # Cache for 5 minutes
                cache.set(cache_key, secret_data, timeout=300)
                logger.debug(f"Successfully read secret from Vault: {mount}/{path}")
                return secret_data
            else:
                logger.warning(f"Secret not found in Vault: {mount}/{path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to read secret from Vault: {e}")
            SecurityEvent.log_event(
                'vault_read_failure',
                description=f'Failed to read secret from Vault: {str(e)}',
                severity='medium',
                metadata={'path': f"{mount}/{path}", 'error': str(e)}
            )
            return None
    
    def delete_secret(self, path: str, mount_point: str = None) -> bool:
        """Delete secret from Vault"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        mount = mount_point or self.config.mount_point
        
        try:
            # Handle different KV versions
            if self._is_kv_v2(mount):
                client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path,
                    mount_point=mount,
                )
            else:
                client.secrets.kv.v1.delete_secret(
                    path=path,
                    mount_point=mount,
                )
            
            # Clear cache
            cache_key = f"vault_secret:{mount}:{path}"
            cache.delete(cache_key)
            
            logger.info(f"Successfully deleted secret from Vault: {mount}/{path}")
            
            # Log security event
            SecurityEvent.log_event(
                'secret_delete',
                description=f'Secret deleted from Vault: {mount}/{path}',
                severity='high',
                metadata={'path': f"{mount}/{path}"}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            SecurityEvent.log_event(
                'vault_delete_failure',
                description=f'Failed to delete secret from Vault: {str(e)}',
                severity='high',
                metadata={'path': f"{mount}/{path}", 'error': str(e)}
            )
            raise SecurityException(f"Failed to delete secret: {e}")
    
    def list_secrets(self, path: str = "", mount_point: str = None) -> List[str]:
        """List secrets at path"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        mount = mount_point or self.config.mount_point
        
        try:
            # Handle different KV versions
            if self._is_kv_v2(mount):
                response = client.secrets.kv.v2.list_secrets(
                    path=path,
                    mount_point=mount,
                )
            else:
                response = client.secrets.kv.v1.list_secrets(
                    path=path,
                    mount_point=mount,
                )
            
            return response.get('data', {}).get('keys', []) if response else []
            
        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            return []
    
    def generate_password(self, length: int = 32, policy: str = "default") -> str:
        """Generate password using Vault password generator"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        
        try:
            response = client.secrets.identity.generate_password(
                policy_name=policy,
                length=length,
            )
            
            return response['data']['password']
            
        except Exception as e:
            logger.error(f"Failed to generate password from Vault: {e}")
            # Fallback to local generation
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def encrypt_data(self, plaintext: str, key_name: str = "pricing-agent") -> str:
        """Encrypt data using Vault transit engine"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        
        try:
            response = client.secrets.transit.encrypt_data(
                name=key_name,
                plaintext=plaintext,
                mount_point='transit'
            )
            
            return response['data']['ciphertext']
            
        except Exception as e:
            logger.error(f"Failed to encrypt data with Vault: {e}")
            raise SecurityException(f"Encryption failed: {e}")
    
    def decrypt_data(self, ciphertext: str, key_name: str = "pricing-agent") -> str:
        """Decrypt data using Vault transit engine"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        
        try:
            response = client.secrets.transit.decrypt_data(
                name=key_name,
                ciphertext=ciphertext,
                mount_point='transit'
            )
            
            return response['data']['plaintext']
            
        except Exception as e:
            logger.error(f"Failed to decrypt data with Vault: {e}")
            raise SecurityException(f"Decryption failed: {e}")
    
    def create_encryption_key(self, key_name: str, key_type: str = "aes256-gcm96") -> bool:
        """Create encryption key in Vault transit engine"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        
        try:
            client.secrets.transit.create_key(
                name=key_name,
                key_type=key_type,
                mount_point='transit'
            )
            
            logger.info(f"Created encryption key in Vault: {key_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create encryption key in Vault: {e}")
            raise SecurityException(f"Key creation failed: {e}")
    
    def rotate_encryption_key(self, key_name: str) -> bool:
        """Rotate encryption key in Vault"""
        if not self.authenticate():
            raise SecurityException("Failed to authenticate to Vault")
        
        client = self._get_client()
        
        try:
            client.secrets.transit.rotate_key(
                name=key_name,
                mount_point='transit'
            )
            
            logger.info(f"Rotated encryption key in Vault: {key_name}")
            
            # Log security event
            SecurityEvent.log_event(
                'key_rotation',
                description=f'Encryption key rotated in Vault: {key_name}',
                severity='medium',
                metadata={'key_name': key_name}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate encryption key in Vault: {e}")
            raise SecurityException(f"Key rotation failed: {e}")
    
    def _is_kv_v2(self, mount_point: str) -> bool:
        """Check if KV mount is version 2"""
        client = self._get_client()
        
        try:
            mounts = client.sys.list_mounted_secrets_engines()
            mount_info = mounts.get(f"{mount_point}/", {})
            options = mount_info.get('options', {})
            version = options.get('version', '1')
            return version == '2'
        except:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Vault health"""
        try:
            client = self._get_client()
            health = client.sys.read_health_status()
            
            return {
                'healthy': True,
                'sealed': health.get('sealed', False),
                'standby': health.get('standby', False),
                'version': health.get('version', 'unknown'),
                'cluster_name': health.get('cluster_name', 'unknown'),
            }
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }


class SecretManager:
    """High-level secrets management interface"""
    
    def __init__(self, vault_client: VaultClient = None):
        self.vault = vault_client or VaultClient()
        self.cache_timeout = 300  # 5 minutes
    
    def get_database_credentials(self, database_name: str) -> Optional[Dict[str, str]]:
        """Get database credentials"""
        path = f"databases/{database_name}"
        return self.vault.read_secret(path)
    
    def get_api_key(self, service_name: str) -> Optional[str]:
        """Get API key for external service"""
        path = f"api-keys/{service_name}"
        secret = self.vault.read_secret(path)
        return secret.get('api_key') if secret else None
    
    def get_jwt_secret(self, service_name: str = 'default') -> Optional[str]:
        """Get JWT signing secret"""
        path = f"jwt/{service_name}"
        secret = self.vault.read_secret(path)
        return secret.get('secret') if secret else None
    
    def get_encryption_key(self, key_name: str) -> Optional[str]:
        """Get encryption key"""
        path = f"encryption/{key_name}"
        secret = self.vault.read_secret(path)
        return secret.get('key') if secret else None
    
    def store_database_credentials(self, database_name: str, username: str, password: str, host: str, port: int) -> bool:
        """Store database credentials"""
        path = f"databases/{database_name}"
        data = {
            'username': username,
            'password': password,
            'host': host,
            'port': port,
            'created_at': datetime.now().isoformat(),
        }
        return self.vault.write_secret(path, data)
    
    def store_api_key(self, service_name: str, api_key: str, description: str = "") -> bool:
        """Store API key"""
        path = f"api-keys/{service_name}"
        data = {
            'api_key': api_key,
            'description': description,
            'created_at': datetime.now().isoformat(),
        }
        return self.vault.write_secret(path, data)
    
    def rotate_jwt_secret(self, service_name: str = 'default') -> str:
        """Rotate JWT signing secret"""
        import secrets
        new_secret = secrets.token_urlsafe(64)
        
        path = f"jwt/{service_name}"
        data = {
            'secret': new_secret,
            'rotated_at': datetime.now().isoformat(),
        }
        
        if self.vault.write_secret(path, data):
            return new_secret
        else:
            raise SecurityException("Failed to rotate JWT secret")
    
    def generate_and_store_password(self, path: str, length: int = 32) -> str:
        """Generate and store a secure password"""
        password = self.vault.generate_password(length=length)
        data = {
            'password': password,
            'generated_at': datetime.now().isoformat(),
        }
        
        if self.vault.write_secret(path, data):
            return password
        else:
            raise SecurityException("Failed to store generated password")
    
    def backup_secrets(self, backup_path: str) -> bool:
        """Backup all secrets to specified path"""
        try:
            # List all secrets
            all_secrets = {}
            
            # Common secret paths
            secret_paths = ['databases', 'api-keys', 'jwt', 'encryption']
            
            for base_path in secret_paths:
                secrets_list = self.vault.list_secrets(base_path)
                for secret_name in secrets_list:
                    full_path = f"{base_path}/{secret_name}"
                    secret_data = self.vault.read_secret(full_path)
                    if secret_data:
                        all_secrets[full_path] = secret_data
            
            # Store backup
            backup_data = {
                'secrets': all_secrets,
                'backup_timestamp': datetime.now().isoformat(),
                'backup_version': '1.0',
            }
            
            return self.vault.write_secret(backup_path, backup_data)
            
        except Exception as e:
            logger.error(f"Failed to backup secrets: {e}")
            return False
    
    def audit_secrets(self) -> Dict[str, Any]:
        """Audit secrets for compliance"""
        audit_results = {
            'total_secrets': 0,
            'secrets_by_type': defaultdict(int),
            'old_secrets': [],
            'expiring_secrets': [],
            'issues': [],
        }
        
        try:
            # Common secret paths
            secret_paths = ['databases', 'api-keys', 'jwt', 'encryption']
            
            for base_path in secret_paths:
                secrets_list = self.vault.list_secrets(base_path)
                audit_results['secrets_by_type'][base_path] = len(secrets_list)
                audit_results['total_secrets'] += len(secrets_list)
                
                for secret_name in secrets_list:
                    full_path = f"{base_path}/{secret_name}"
                    secret_data = self.vault.read_secret(full_path)
                    
                    if secret_data:
                        # Check age
                        created_at_str = secret_data.get('created_at')
                        if created_at_str:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            age_days = (datetime.now() - created_at.replace(tzinfo=None)).days
                            
                            if age_days > 365:  # Older than 1 year
                                audit_results['old_secrets'].append({
                                    'path': full_path,
                                    'age_days': age_days,
                                })
                        
                        # Check for expiration
                        expires_at_str = secret_data.get('expires_at')
                        if expires_at_str:
                            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                            days_until_expiry = (expires_at.replace(tzinfo=None) - datetime.now()).days
                            
                            if days_until_expiry < 30:  # Expires in 30 days
                                audit_results['expiring_secrets'].append({
                                    'path': full_path,
                                    'days_until_expiry': days_until_expiry,
                                })
        
        except Exception as e:
            audit_results['issues'].append(f"Audit failed: {str(e)}")
        
        return audit_results


# Global instances
vault_client = VaultClient()
secret_manager = SecretManager(vault_client)
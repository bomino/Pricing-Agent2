"""
Data Encryption and Key Management for AI Pricing Agent
Implements field-level encryption, database encryption, and key rotation
"""
import os
import base64
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import secrets

from django.conf import settings
from django.db import models
from django.core.cache import cache
from django.utils import timezone

from .vault_integration import vault_client
from .security_models import SecurityEvent, EncryptionKey, DataClassification
from .exceptions import SecurityException

logger = logging.getLogger(__name__)


@dataclass
class EncryptionConfig:
    """Encryption configuration"""
    algorithm: str = "AES-256-GCM"
    key_size: int = 32  # 256 bits
    iv_size: int = 12   # 96 bits for GCM
    tag_size: int = 16  # 128 bits for GCM
    kdf_iterations: int = 100000
    key_rotation_days: int = 90
    backup_key_versions: int = 3


class EncryptionService:
    """Service for handling encryption operations"""
    
    def __init__(self, config: EncryptionConfig = None):
        self.config = config or EncryptionConfig()
        self._master_key_cache = {}
        self._key_cache_timeout = 3600  # 1 hour
    
    def encrypt_field(self, plaintext: str, context: str, key_name: str = None) -> str:
        """Encrypt a field value with context"""
        if not plaintext:
            return plaintext
        
        try:
            # Use Vault if available, fallback to local encryption
            if vault_client.authenticate():
                return self._encrypt_with_vault(plaintext, key_name or context)
            else:
                return self._encrypt_locally(plaintext, context)
                
        except Exception as e:
            logger.error(f"Encryption failed for context {context}: {e}")
            raise SecurityException(f"Encryption failed: {e}")
    
    def decrypt_field(self, ciphertext: str, context: str, key_name: str = None) -> str:
        """Decrypt a field value with context"""
        if not ciphertext:
            return ciphertext
        
        try:
            # Check if it's Vault encrypted (starts with vault:)
            if ciphertext.startswith('vault:'):
                if vault_client.authenticate():
                    return self._decrypt_with_vault(ciphertext, key_name or context)
                else:
                    raise SecurityException("Vault not available for decryption")
            else:
                return self._decrypt_locally(ciphertext, context)
                
        except Exception as e:
            logger.error(f"Decryption failed for context {context}: {e}")
            raise SecurityException(f"Decryption failed: {e}")
    
    def _encrypt_with_vault(self, plaintext: str, key_name: str) -> str:
        """Encrypt using Vault transit engine"""
        try:
            ciphertext = vault_client.encrypt_data(plaintext, key_name)
            return ciphertext
        except Exception as e:
            logger.warning(f"Vault encryption failed, falling back to local: {e}")
            return self._encrypt_locally(plaintext, key_name)
    
    def _decrypt_with_vault(self, ciphertext: str, key_name: str) -> str:
        """Decrypt using Vault transit engine"""
        return vault_client.decrypt_data(ciphertext, key_name)
    
    def _encrypt_locally(self, plaintext: str, context: str) -> str:
        """Encrypt locally using AES-GCM"""
        # Get or derive key
        key = self._get_or_derive_key(context)
        
        # Generate random IV
        iv = secrets.token_bytes(self.config.iv_size)
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext_bytes = encryptor.update(plaintext.encode('utf-8')) + encryptor.finalize()
        
        # Combine IV + tag + ciphertext
        encrypted_data = iv + encryptor.tag + ciphertext_bytes
        
        # Encode as base64
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def _decrypt_locally(self, ciphertext: str, context: str) -> str:
        """Decrypt locally using AES-GCM"""
        try:
            # Decode from base64
            encrypted_data = base64.b64decode(ciphertext.encode('utf-8'))
            
            # Extract components
            iv = encrypted_data[:self.config.iv_size]
            tag = encrypted_data[self.config.iv_size:self.config.iv_size + self.config.tag_size]
            ciphertext_bytes = encrypted_data[self.config.iv_size + self.config.tag_size:]
            
            # Get key
            key = self._get_or_derive_key(context)
            
            # Decrypt
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            plaintext_bytes = decryptor.update(ciphertext_bytes) + decryptor.finalize()
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Local decryption failed: {e}")
            raise SecurityException(f"Decryption failed: {e}")
    
    def _get_or_derive_key(self, context: str) -> bytes:
        """Get or derive encryption key for context"""
        cache_key = f"encryption_key:{context}"
        
        # Check cache
        key = self._master_key_cache.get(cache_key)
        if key:
            return key
        
        # Try to get from Vault
        try:
            if vault_client.authenticate():
                key_data = vault_client.read_secret(f"encryption/{context}")
                if key_data and 'key' in key_data:
                    key = base64.b64decode(key_data['key'])
                    self._master_key_cache[cache_key] = key
                    return key
        except Exception as e:
            logger.debug(f"Could not get key from Vault: {e}")
        
        # Derive from master key
        master_key = self._get_master_key()
        salt = context.encode('utf-8') + b'pricing_agent_salt'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.config.key_size,
            salt=salt,
            iterations=self.config.kdf_iterations,
            backend=default_backend()
        )
        
        key = kdf.derive(master_key)
        self._master_key_cache[cache_key] = key
        
        return key
    
    def _get_master_key(self) -> bytes:
        """Get master encryption key"""
        # Try Vault first
        try:
            if vault_client.authenticate():
                key_data = vault_client.read_secret('master/encryption_key')
                if key_data and 'key' in key_data:
                    return base64.b64decode(key_data['key'])
        except Exception as e:
            logger.debug(f"Could not get master key from Vault: {e}")
        
        # Fall back to settings
        master_key = getattr(settings, 'ENCRYPTION_MASTER_KEY', None)
        if master_key:
            return master_key.encode('utf-8')
        
        # Use SECRET_KEY as last resort
        return settings.SECRET_KEY.encode('utf-8')
    
    def rotate_key(self, context: str) -> bool:
        """Rotate encryption key for context"""
        try:
            # Generate new key
            new_key = secrets.token_bytes(self.config.key_size)
            
            # Store in Vault
            if vault_client.authenticate():
                key_data = {
                    'key': base64.b64encode(new_key).decode('utf-8'),
                    'created_at': datetime.now().isoformat(),
                    'algorithm': self.config.algorithm,
                }
                vault_client.write_secret(f"encryption/{context}", key_data)
            
            # Clear cache
            cache_key = f"encryption_key:{context}"
            self._master_key_cache.pop(cache_key, None)
            
            # Log rotation
            SecurityEvent.log_event(
                'key_rotation',
                description=f'Encryption key rotated for context: {context}',
                severity='medium',
                metadata={'context': context}
            )
            
            logger.info(f"Key rotated for context: {context}")
            return True
            
        except Exception as e:
            logger.error(f"Key rotation failed for context {context}: {e}")
            return False
    
    def encrypt_file(self, file_path: str, output_path: str = None, context: str = "file_encryption") -> str:
        """Encrypt a file"""
        if not os.path.exists(file_path):
            raise SecurityException(f"File not found: {file_path}")
        
        output_path = output_path or f"{file_path}.encrypted"
        
        try:
            # Generate file-specific key
            file_key = secrets.token_bytes(self.config.key_size)
            iv = secrets.token_bytes(self.config.iv_size)
            
            # Encrypt file content
            cipher = Cipher(
                algorithms.AES(file_key),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            with open(file_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                # Write header
                outfile.write(b'ENC1')  # Format version
                outfile.write(iv)
                
                # Encrypt in chunks
                while True:
                    chunk = infile.read(8192)
                    if not chunk:
                        break
                    encrypted_chunk = encryptor.update(chunk)
                    outfile.write(encrypted_chunk)
                
                # Finalize and write tag
                encryptor.finalize()
                outfile.write(encryptor.tag)
            
            # Encrypt and store the file key
            encrypted_file_key = self.encrypt_field(
                base64.b64encode(file_key).decode('utf-8'),
                f"file_{os.path.basename(file_path)}"
            )
            
            # Store file key metadata
            if vault_client.authenticate():
                file_key_data = {
                    'encrypted_key': encrypted_file_key,
                    'file_path': file_path,
                    'encrypted_path': output_path,
                    'created_at': datetime.now().isoformat(),
                }
                vault_client.write_secret(f"file_keys/{os.path.basename(file_path)}", file_key_data)
            
            logger.info(f"File encrypted: {file_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"File encryption failed: {e}")
            raise SecurityException(f"File encryption failed: {e}")
    
    def decrypt_file(self, encrypted_path: str, output_path: str = None) -> str:
        """Decrypt a file"""
        if not os.path.exists(encrypted_path):
            raise SecurityException(f"Encrypted file not found: {encrypted_path}")
        
        output_path = output_path or encrypted_path.replace('.encrypted', '.decrypted')
        
        try:
            # Get file key
            file_name = os.path.basename(encrypted_path).replace('.encrypted', '')
            
            if vault_client.authenticate():
                file_key_data = vault_client.read_secret(f"file_keys/{file_name}")
                if not file_key_data:
                    raise SecurityException("File key not found")
                
                encrypted_file_key = file_key_data['encrypted_key']
                file_key = base64.b64decode(
                    self.decrypt_field(encrypted_file_key, f"file_{file_name}")
                )
            else:
                raise SecurityException("Cannot decrypt file without key store")
            
            # Decrypt file
            with open(encrypted_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                # Read header
                format_version = infile.read(4)
                if format_version != b'ENC1':
                    raise SecurityException("Invalid encrypted file format")
                
                iv = infile.read(self.config.iv_size)
                
                # Read and decrypt content
                cipher = Cipher(
                    algorithms.AES(file_key),
                    modes.GCM(iv),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                # Read all content except the tag
                content = infile.read()
                tag = content[-self.config.tag_size:]
                encrypted_content = content[:-self.config.tag_size:]
                
                # Set tag and decrypt
                cipher = Cipher(
                    algorithms.AES(file_key),
                    modes.GCM(iv, tag),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                decrypted_content = decryptor.update(encrypted_content)
                decryptor.finalize()
                
                outfile.write(decrypted_content)
            
            logger.info(f"File decrypted: {encrypted_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise SecurityException(f"File decryption failed: {e}")


class EncryptedFieldMixin:
    """Mixin for models with encrypted fields"""
    
    ENCRYPTED_FIELDS = []  # List of field names to encrypt
    
    def save(self, *args, **kwargs):
        """Override save to encrypt fields"""
        encryption_service = EncryptionService()
        
        for field_name in self.ENCRYPTED_FIELDS:
            if hasattr(self, field_name):
                field_value = getattr(self, field_name)
                if field_value and not self._is_encrypted(field_value):
                    # Encrypt the field
                    context = f"{self._meta.label_lower}_{field_name}"
                    encrypted_value = encryption_service.encrypt_field(field_value, context)
                    setattr(self, field_name, encrypted_value)
        
        super().save(*args, **kwargs)
    
    def get_decrypted_field(self, field_name: str) -> str:
        """Get decrypted field value"""
        if field_name not in self.ENCRYPTED_FIELDS:
            raise ValueError(f"Field {field_name} is not encrypted")
        
        field_value = getattr(self, field_name, '')
        if not field_value or not self._is_encrypted(field_value):
            return field_value
        
        encryption_service = EncryptionService()
        context = f"{self._meta.label_lower}_{field_name}"
        return encryption_service.decrypt_field(field_value, context)
    
    def set_encrypted_field(self, field_name: str, value: str):
        """Set encrypted field value"""
        if field_name not in self.ENCRYPTED_FIELDS:
            raise ValueError(f"Field {field_name} is not encrypted")
        
        if value:
            encryption_service = EncryptionService()
            context = f"{self._meta.label_lower}_{field_name}"
            encrypted_value = encryption_service.encrypt_field(value, context)
            setattr(self, field_name, encrypted_value)
        else:
            setattr(self, field_name, value)
    
    def _is_encrypted(self, value: str) -> bool:
        """Check if value is already encrypted"""
        if not value:
            return False
        
        # Check for Vault format
        if value.startswith('vault:'):
            return True
        
        # Check for base64 format (local encryption)
        try:
            base64.b64decode(value)
            # If it's valid base64 and long enough, assume it's encrypted
            return len(value) > 20
        except:
            return False


class DatabaseEncryption:
    """Database-level encryption utilities"""
    
    @staticmethod
    def setup_tde(database_alias: str = 'default'):
        """Setup Transparent Data Encryption for database"""
        from django.db import connections
        
        connection = connections[database_alias]
        
        # PostgreSQL TDE setup
        if 'postgresql' in connection.settings_dict['ENGINE']:
            with connection.cursor() as cursor:
                # Enable pgcrypto extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
                
                # Create encryption functions
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION encrypt_field(data TEXT, key TEXT)
                    RETURNS TEXT AS $$
                    BEGIN
                        RETURN encode(pgp_sym_encrypt(data, key), 'base64');
                    END;
                    $$ LANGUAGE plpgsql;
                """)
                
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION decrypt_field(encrypted_data TEXT, key TEXT)
                    RETURNS TEXT AS $$
                    BEGIN
                        RETURN pgp_sym_decrypt(decode(encrypted_data, 'base64'), key);
                    END;
                    $$ LANGUAGE plpgsql;
                """)
                
                logger.info(f"TDE setup completed for database: {database_alias}")
        
        # SQLite encryption (would require special SQLite build)
        elif 'sqlite' in connection.settings_dict['ENGINE']:
            logger.warning("SQLite TDE requires SQLCipher - not implemented")
        
        else:
            logger.warning(f"TDE not implemented for {connection.settings_dict['ENGINE']}")
    
    @staticmethod
    def encrypt_backup(backup_path: str, encryption_key: str) -> str:
        """Encrypt database backup"""
        encryption_service = EncryptionService()
        encrypted_path = encryption_service.encrypt_file(backup_path, context="database_backup")
        
        # Store backup encryption key
        if vault_client.authenticate():
            key_data = {
                'encryption_key': encryption_key,
                'backup_path': backup_path,
                'encrypted_path': encrypted_path,
                'created_at': datetime.now().isoformat(),
            }
            vault_client.write_secret(f"backup_keys/{os.path.basename(backup_path)}", key_data)
        
        return encrypted_path


class DataMasking:
    """Data masking for non-production environments"""
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address"""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[:2] + '*' * (len(local) - 2)
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone number"""
        if not phone:
            return phone
        
        # Remove non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) < 4:
            return '*' * len(phone)
        
        # Keep last 4 digits
        masked = '*' * (len(digits) - 4) + digits[-4:]
        return masked
    
    @staticmethod
    def mask_ssn(ssn: str) -> str:
        """Mask SSN"""
        if not ssn:
            return ssn
        
        # Remove non-digits
        digits = ''.join(c for c in ssn if c.isdigit())
        if len(digits) != 9:
            return '*' * len(ssn)
        
        return f"***-**-{digits[-4:]}"
    
    @staticmethod
    def mask_credit_card(cc: str) -> str:
        """Mask credit card number"""
        if not cc:
            return cc
        
        # Remove non-digits
        digits = ''.join(c for c in cc if c.isdigit())
        if len(digits) < 8:
            return '*' * len(cc)
        
        # Keep first 4 and last 4
        return f"{digits[:4]}{'*' * (len(digits) - 8)}{digits[-4:]}"


# Global encryption service instance
encryption_service = EncryptionService()
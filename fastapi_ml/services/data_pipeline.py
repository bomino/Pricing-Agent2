"""
Data Pipeline Service - ETL and feature store implementation
"""
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import redis.asyncio as redis
from pathlib import Path
import json

from ..config import settings

logger = structlog.get_logger()


class DataValidator:
    """Data quality validation for incoming data"""
    
    def __init__(self):
        self.validation_rules = {
            'price_data': {
                'required_columns': ['material_id', 'supplier_id', 'price', 'quantity', 'timestamp'],
                'numeric_columns': ['price', 'quantity'],
                'positive_columns': ['price', 'quantity'],
                'date_columns': ['timestamp'],
                'max_null_ratio': 0.1  # Max 10% null values
            },
            'market_data': {
                'required_columns': ['date', 'commodity_index', 'inflation_rate'],
                'numeric_columns': ['commodity_index', 'inflation_rate'],
                'date_columns': ['date'],
                'max_null_ratio': 0.05
            },
            'supplier_data': {
                'required_columns': ['supplier_id', 'rating', 'region'],
                'numeric_columns': ['rating'],
                'categorical_columns': ['region'],
                'max_null_ratio': 0.05
            }
        }
    
    async def validate_data(self, data: pd.DataFrame, data_type: str) -> Dict[str, Any]:
        """Validate data against predefined rules"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'quality_score': 1.0,
            'row_count': len(data),
            'column_count': len(data.columns)
        }
        
        if data_type not in self.validation_rules:
            validation_result['warnings'].append(f"No validation rules defined for data type: {data_type}")
            return validation_result
        
        rules = self.validation_rules[data_type]
        
        # Check required columns
        missing_columns = set(rules['required_columns']) - set(data.columns)
        if missing_columns:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Missing required columns: {missing_columns}")
        
        # Check numeric columns
        for col in rules.get('numeric_columns', []):
            if col in data.columns:
                if not pd.api.types.is_numeric_dtype(data[col]):
                    validation_result['errors'].append(f"Column {col} should be numeric")
                    validation_result['is_valid'] = False
        
        # Check positive values
        for col in rules.get('positive_columns', []):
            if col in data.columns and data[col].min() <= 0:
                validation_result['warnings'].append(f"Column {col} has non-positive values")
                validation_result['quality_score'] -= 0.1
        
        # Check null ratios
        max_null_ratio = rules.get('max_null_ratio', 0.1)
        for col in data.columns:
            null_ratio = data[col].isnull().mean()
            if null_ratio > max_null_ratio:
                validation_result['warnings'].append(
                    f"Column {col} has high null ratio: {null_ratio:.2%}"
                )
                validation_result['quality_score'] -= 0.05
        
        # Check duplicates
        duplicate_count = data.duplicated().sum()
        if duplicate_count > 0:
            validation_result['warnings'].append(f"Found {duplicate_count} duplicate rows")
            validation_result['quality_score'] -= 0.05
        
        # Data freshness check
        if 'timestamp' in data.columns:
            try:
                max_date = pd.to_datetime(data['timestamp']).max()
                days_old = (datetime.utcnow() - max_date.to_pydatetime()).days
                if days_old > 30:
                    validation_result['warnings'].append(f"Data is {days_old} days old")
                    validation_result['quality_score'] -= 0.1
            except Exception as e:
                validation_result['warnings'].append(f"Could not validate data freshness: {e}")
        
        validation_result['quality_score'] = max(0, validation_result['quality_score'])
        
        logger.info(
            "Data validation completed",
            data_type=data_type,
            is_valid=validation_result['is_valid'],
            quality_score=validation_result['quality_score'],
            errors=len(validation_result['errors']),
            warnings=len(validation_result['warnings'])
        )
        
        return validation_result


class DataCleaner:
    """Data cleaning and preprocessing"""
    
    def __init__(self):
        self.cleaning_rules = {}
    
    async def clean_price_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean pricing data"""
        cleaned_data = data.copy()
        
        # Remove extreme outliers (beyond 3 IQRs)
        if 'price' in cleaned_data.columns:
            Q1 = cleaned_data['price'].quantile(0.25)
            Q3 = cleaned_data['price'].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR
            
            outlier_mask = (cleaned_data['price'] < lower_bound) | (cleaned_data['price'] > upper_bound)
            outliers_removed = outlier_mask.sum()
            
            if outliers_removed > 0:
                logger.info(f"Removing {outliers_removed} price outliers")
                cleaned_data = cleaned_data[~outlier_mask]
        
        # Handle missing values
        cleaned_data = await self._handle_missing_values(cleaned_data, 'price_data')
        
        # Standardize data types
        cleaned_data = await self._standardize_data_types(cleaned_data)
        
        # Remove duplicates
        initial_rows = len(cleaned_data)
        cleaned_data = cleaned_data.drop_duplicates()
        duplicates_removed = initial_rows - len(cleaned_data)
        
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows")
        
        return cleaned_data
    
    async def clean_market_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean market data"""
        cleaned_data = data.copy()
        
        # Handle missing values with forward fill for time series
        numeric_columns = cleaned_data.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            cleaned_data[col] = cleaned_data[col].fillna(method='ffill').fillna(method='bfill')
        
        # Smooth extreme volatility
        for col in ['commodity_index', 'inflation_rate']:
            if col in cleaned_data.columns:
                # Cap extreme values using percentile-based approach
                p1 = cleaned_data[col].quantile(0.01)
                p99 = cleaned_data[col].quantile(0.99)
                cleaned_data[col] = cleaned_data[col].clip(lower=p1, upper=p99)
        
        return cleaned_data
    
    async def _handle_missing_values(self, data: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Handle missing values based on data type"""
        cleaned_data = data.copy()
        
        # Strategy varies by column type
        for col in cleaned_data.columns:
            if cleaned_data[col].isnull().any():
                if pd.api.types.is_numeric_dtype(cleaned_data[col]):
                    # Fill numeric columns with median
                    cleaned_data[col] = cleaned_data[col].fillna(cleaned_data[col].median())
                elif pd.api.types.is_categorical_dtype(cleaned_data[col]) or cleaned_data[col].dtype == 'object':
                    # Fill categorical columns with mode
                    mode_value = cleaned_data[col].mode()
                    if not mode_value.empty:
                        cleaned_data[col] = cleaned_data[col].fillna(mode_value[0])
                    else:
                        cleaned_data[col] = cleaned_data[col].fillna('unknown')
                elif pd.api.types.is_datetime64_any_dtype(cleaned_data[col]):
                    # Fill datetime columns with forward fill
                    cleaned_data[col] = cleaned_data[col].fillna(method='ffill')
        
        return cleaned_data
    
    async def _standardize_data_types(self, data: pd.DataFrame) -> pd.DataFrame:
        """Standardize data types"""
        cleaned_data = data.copy()
        
        # Convert timestamp columns
        timestamp_columns = ['timestamp', 'date', 'created_at', 'updated_at']
        for col in timestamp_columns:
            if col in cleaned_data.columns:
                cleaned_data[col] = pd.to_datetime(cleaned_data[col], errors='coerce')
        
        # Convert ID columns to strings
        id_columns = [col for col in cleaned_data.columns if col.endswith('_id')]
        for col in id_columns:
            cleaned_data[col] = cleaned_data[col].astype(str)
        
        # Convert price/amount columns to float
        price_columns = ['price', 'amount', 'cost', 'value']
        for col in price_columns:
            if col in cleaned_data.columns:
                cleaned_data[col] = pd.to_numeric(cleaned_data[col], errors='coerce')
        
        return cleaned_data


class ETLPipeline:
    """Extract, Transform, Load pipeline"""
    
    def __init__(self):
        self.data_validator = DataValidator()
        self.data_cleaner = DataCleaner()
        self.redis_client: Optional[redis.Redis] = None
        
        # Database connection
        self.db_engine = create_async_engine(
            settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
            echo=False,
            pool_pre_ping=True
        )
        self.async_session = sessionmaker(
            self.db_engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def initialize(self, redis_client: redis.Redis):
        """Initialize ETL pipeline"""
        self.redis_client = redis_client
        logger.info("ETL Pipeline initialized")
    
    async def extract_pricing_data(self, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None,
                                 limit: Optional[int] = None) -> pd.DataFrame:
        """Extract pricing data from database"""
        try:
            query = """
            SELECT 
                p.material_id,
                p.supplier_id,
                p.price_per_unit as price,
                p.quantity,
                p.currency,
                p.created_at as timestamp,
                m.category as material_category,
                s.name as supplier_name,
                s.region as supplier_region,
                s.rating as supplier_rating
            FROM pricing_rfq p
            LEFT JOIN pricing_material m ON p.material_id = m.id
            LEFT JOIN pricing_supplier s ON p.supplier_id = s.id
            WHERE 1=1
            """
            
            params = {}
            if start_date:
                query += " AND p.created_at >= :start_date"
                params['start_date'] = start_date
            
            if end_date:
                query += " AND p.created_at <= :end_date"
                params['end_date'] = end_date
            
            query += " ORDER BY p.created_at DESC"
            
            if limit:
                query += " LIMIT :limit"
                params['limit'] = limit
            
            async with self.async_session() as session:
                result = await session.execute(text(query), params)
                data = result.fetchall()
                
                if data:
                    columns = result.keys()
                    df = pd.DataFrame(data, columns=columns)
                    logger.info(f"Extracted {len(df)} pricing records")
                    return df
                else:
                    logger.warning("No pricing data found")
                    return pd.DataFrame()
                    
        except Exception as e:
            logger.error(f"Failed to extract pricing data: {e}")
            # Return sample data for development
            return await self._generate_sample_pricing_data()
    
    async def extract_market_data(self) -> pd.DataFrame:
        """Extract market data from external sources"""
        try:
            # In production, this would call external APIs
            # For now, generate synthetic market data
            return await self._generate_sample_market_data()
            
        except Exception as e:
            logger.error(f"Failed to extract market data: {e}")
            return pd.DataFrame()
    
    async def extract_supplier_data(self) -> pd.DataFrame:
        """Extract supplier performance data"""
        try:
            query = """
            SELECT 
                s.id as supplier_id,
                s.name as supplier_name,
                s.region,
                s.rating,
                s.created_at,
                AVG(p.price_per_unit) as avg_price,
                COUNT(p.id) as quote_count,
                STDDEV(p.price_per_unit) as price_volatility
            FROM pricing_supplier s
            LEFT JOIN pricing_rfq p ON s.id = p.supplier_id
            GROUP BY s.id, s.name, s.region, s.rating, s.created_at
            """
            
            async with self.async_session() as session:
                result = await session.execute(text(query))
                data = result.fetchall()
                
                if data:
                    columns = result.keys()
                    df = pd.DataFrame(data, columns=columns)
                    logger.info(f"Extracted {len(df)} supplier records")
                    return df
                else:
                    return await self._generate_sample_supplier_data()
                    
        except Exception as e:
            logger.error(f"Failed to extract supplier data: {e}")
            return await self._generate_sample_supplier_data()
    
    async def transform_data(self, 
                           raw_data: pd.DataFrame, 
                           data_type: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Transform raw data through validation and cleaning"""
        
        # Validate data
        validation_result = await self.data_validator.validate_data(raw_data, data_type)
        
        if not validation_result['is_valid']:
            logger.error(f"Data validation failed for {data_type}: {validation_result['errors']}")
            # Could raise exception or return partial data based on requirements
        
        # Clean data based on type
        if data_type == 'price_data':
            cleaned_data = await self.data_cleaner.clean_price_data(raw_data)
        elif data_type == 'market_data':
            cleaned_data = await self.data_cleaner.clean_market_data(raw_data)
        else:
            cleaned_data = raw_data.copy()
        
        # Additional transformations
        transformed_data = await self._apply_business_rules(cleaned_data, data_type)
        
        logger.info(
            f"Data transformation completed for {data_type}",
            input_rows=len(raw_data),
            output_rows=len(transformed_data),
            quality_score=validation_result['quality_score']
        )
        
        return transformed_data, validation_result
    
    async def _apply_business_rules(self, data: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Apply business-specific transformation rules"""
        transformed_data = data.copy()
        
        if data_type == 'price_data':
            # Convert all prices to USD (placeholder - would use real exchange rates)
            if 'currency' in transformed_data.columns and 'price' in transformed_data.columns:
                # Simple currency conversion (in production, use real exchange rates)
                currency_rates = {'EUR': 1.1, 'GBP': 1.25, 'CAD': 0.75, 'USD': 1.0}
                
                for currency, rate in currency_rates.items():
                    mask = transformed_data['currency'] == currency
                    transformed_data.loc[mask, 'price'] *= rate
                    transformed_data.loc[mask, 'currency'] = 'USD'
            
            # Add price categories
            if 'price' in transformed_data.columns:
                transformed_data['price_category'] = pd.cut(
                    transformed_data['price'],
                    bins=[0, 50, 200, 1000, np.inf],
                    labels=['low', 'medium', 'high', 'premium']
                )
            
            # Add quantity brackets
            if 'quantity' in transformed_data.columns:
                transformed_data['quantity_bracket'] = pd.cut(
                    transformed_data['quantity'],
                    bins=[0, 10, 100, 1000, np.inf],
                    labels=['small', 'medium', 'large', 'bulk']
                )
        
        elif data_type == 'supplier_data':
            # Normalize supplier ratings to 0-1 scale
            if 'rating' in transformed_data.columns:
                max_rating = transformed_data['rating'].max()
                if max_rating > 1:
                    transformed_data['rating'] = transformed_data['rating'] / max_rating
        
        return transformed_data
    
    async def load_to_feature_store(self, 
                                  data: pd.DataFrame, 
                                  feature_set_name: str,
                                  version: Optional[str] = None) -> bool:
        """Load transformed data to feature store (Redis)"""
        try:
            if self.redis_client is None:
                logger.error("Redis client not initialized")
                return False
            
            version = version or datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            
            # Store as JSON in Redis
            feature_key = f"features:{feature_set_name}:{version}"
            
            # Split large datasets into chunks
            chunk_size = 1000
            chunks = [data.iloc[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                chunk_key = f"{feature_key}:chunk_{i}"
                chunk_data = chunk.to_json(orient='records', date_format='iso')
                
                await self.redis_client.setex(
                    chunk_key,
                    settings.FEATURE_CACHE_TTL,
                    chunk_data
                )
            
            # Store metadata
            metadata = {
                'feature_set_name': feature_set_name,
                'version': version,
                'row_count': len(data),
                'column_count': len(data.columns),
                'columns': list(data.columns),
                'chunk_count': len(chunks),
                'created_at': datetime.utcnow().isoformat(),
                'ttl': settings.FEATURE_CACHE_TTL
            }
            
            metadata_key = f"{feature_key}:metadata"
            await self.redis_client.setex(
                metadata_key,
                settings.FEATURE_CACHE_TTL,
                json.dumps(metadata)
            )
            
            logger.info(
                f"Loaded {len(data)} records to feature store",
                feature_set=feature_set_name,
                version=version,
                chunks=len(chunks)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load data to feature store: {e}")
            return False
    
    async def run_full_etl_pipeline(self) -> Dict[str, Any]:
        """Run complete ETL pipeline for all data types"""
        results = {}
        
        # Define data extraction and processing tasks
        tasks = [
            ('pricing_data', self.extract_pricing_data),
            ('market_data', self.extract_market_data),
            ('supplier_data', self.extract_supplier_data)
        ]
        
        for data_type, extract_func in tasks:
            try:
                logger.info(f"Starting ETL for {data_type}")
                
                # Extract
                raw_data = await extract_func()
                
                if raw_data.empty:
                    results[data_type] = {'status': 'skipped', 'reason': 'no_data'}
                    continue
                
                # Transform
                transformed_data, validation_result = await self.transform_data(raw_data, data_type)
                
                # Load
                load_success = await self.load_to_feature_store(transformed_data, data_type)
                
                results[data_type] = {
                    'status': 'success' if load_success else 'failed',
                    'raw_rows': len(raw_data),
                    'processed_rows': len(transformed_data),
                    'quality_score': validation_result['quality_score'],
                    'validation_errors': len(validation_result['errors']),
                    'validation_warnings': len(validation_result['warnings'])
                }
                
            except Exception as e:
                logger.error(f"ETL pipeline failed for {data_type}: {e}")
                results[data_type] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return results
    
    async def _generate_sample_pricing_data(self, n_records: int = 1000) -> pd.DataFrame:
        """Generate sample pricing data for development"""
        np.random.seed(42)
        
        data = {
            'material_id': np.random.randint(1, 100, n_records),
            'supplier_id': np.random.randint(1, 20, n_records),
            'price': np.random.lognormal(4, 0.5, n_records),
            'quantity': np.random.randint(1, 1000, n_records),
            'currency': np.random.choice(['USD', 'EUR', 'GBP'], n_records),
            'timestamp': pd.date_range('2023-01-01', periods=n_records, freq='H'),
            'material_category': np.random.choice(['electronics', 'machinery', 'materials'], n_records),
            'supplier_name': [f'Supplier_{i}' for i in np.random.randint(1, 20, n_records)],
            'supplier_region': np.random.choice(['North America', 'Europe', 'Asia'], n_records),
            'supplier_rating': np.random.uniform(1, 5, n_records)
        }
        
        return pd.DataFrame(data)
    
    async def _generate_sample_market_data(self, n_records: int = 365) -> pd.DataFrame:
        """Generate sample market data"""
        np.random.seed(42)
        
        dates = pd.date_range('2023-01-01', periods=n_records, freq='D')
        base_index = 100
        
        # Generate realistic market index with trend and seasonality
        trend = np.linspace(0, 10, n_records)  # 10% growth over period
        seasonality = 5 * np.sin(2 * np.pi * np.arange(n_records) / 365)
        noise = np.random.normal(0, 2, n_records)
        
        commodity_index = base_index + trend + seasonality + noise
        
        data = {
            'date': dates,
            'commodity_index': commodity_index,
            'inflation_rate': np.random.normal(0.02, 0.005, n_records),
            'exchange_rate_eur_usd': np.random.normal(1.1, 0.05, n_records),
            'exchange_rate_gbp_usd': np.random.normal(1.25, 0.05, n_records),
            'market_volatility': np.random.uniform(0.1, 0.3, n_records)
        }
        
        return pd.DataFrame(data)
    
    async def _generate_sample_supplier_data(self, n_suppliers: int = 50) -> pd.DataFrame:
        """Generate sample supplier data"""
        np.random.seed(42)
        
        data = {
            'supplier_id': range(1, n_suppliers + 1),
            'supplier_name': [f'Supplier_{i}' for i in range(1, n_suppliers + 1)],
            'region': np.random.choice(['North America', 'Europe', 'Asia', 'South America'], n_suppliers),
            'rating': np.random.uniform(1, 5, n_suppliers),
            'created_at': pd.date_range('2022-01-01', periods=n_suppliers, freq='W'),
            'avg_price': np.random.lognormal(4, 0.3, n_suppliers),
            'quote_count': np.random.randint(1, 100, n_suppliers),
            'price_volatility': np.random.uniform(0.05, 0.3, n_suppliers)
        }
        
        return pd.DataFrame(data)


class FeatureStoreManager:
    """Manage feature store operations"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
    
    async def get_feature_set(self, 
                            feature_set_name: str,
                            version: Optional[str] = None) -> pd.DataFrame:
        """Retrieve feature set from store"""
        try:
            # Get latest version if not specified
            if version is None:
                version = await self._get_latest_version(feature_set_name)
                if version is None:
                    logger.warning(f"No versions found for feature set: {feature_set_name}")
                    return pd.DataFrame()
            
            # Get metadata
            metadata_key = f"features:{feature_set_name}:{version}:metadata"
            metadata_json = await self.redis_client.get(metadata_key)
            
            if not metadata_json:
                logger.warning(f"Feature set metadata not found: {feature_set_name}:{version}")
                return pd.DataFrame()
            
            metadata = json.loads(metadata_json)
            
            # Retrieve all chunks
            chunks = []
            for i in range(metadata['chunk_count']):
                chunk_key = f"features:{feature_set_name}:{version}:chunk_{i}"
                chunk_data = await self.redis_client.get(chunk_key)
                
                if chunk_data:
                    chunk_df = pd.read_json(chunk_data, orient='records')
                    chunks.append(chunk_df)
            
            if chunks:
                result_df = pd.concat(chunks, ignore_index=True)
                logger.info(
                    f"Retrieved feature set",
                    feature_set=feature_set_name,
                    version=version,
                    rows=len(result_df)
                )
                return result_df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Failed to retrieve feature set: {e}")
            return pd.DataFrame()
    
    async def _get_latest_version(self, feature_set_name: str) -> Optional[str]:
        """Get latest version of a feature set"""
        try:
            pattern = f"features:{feature_set_name}:*:metadata"
            keys = await self.redis_client.keys(pattern)
            
            if not keys:
                return None
            
            # Extract versions and find the latest
            versions = []
            for key in keys:
                parts = key.split(':')
                if len(parts) >= 3:
                    versions.append(parts[2])
            
            if versions:
                # Sort versions (assuming timestamp format YYYYMMDD_HHMMSS)
                versions.sort(reverse=True)
                return versions[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get latest version: {e}")
            return None
    
    async def list_feature_sets(self) -> List[Dict[str, Any]]:
        """List all available feature sets"""
        try:
            pattern = "features:*:metadata"
            keys = await self.redis_client.keys(pattern)
            
            feature_sets = []
            for key in keys:
                metadata_json = await self.redis_client.get(key)
                if metadata_json:
                    metadata = json.loads(metadata_json)
                    feature_sets.append(metadata)
            
            return feature_sets
            
        except Exception as e:
            logger.error(f"Failed to list feature sets: {e}")
            return []
    
    async def delete_feature_set(self, feature_set_name: str, version: str) -> bool:
        """Delete a specific feature set version"""
        try:
            # Get metadata to know chunk count
            metadata_key = f"features:{feature_set_name}:{version}:metadata"
            metadata_json = await self.redis_client.get(metadata_key)
            
            if not metadata_json:
                logger.warning(f"Feature set not found: {feature_set_name}:{version}")
                return False
            
            metadata = json.loads(metadata_json)
            
            # Delete all chunks
            keys_to_delete = [metadata_key]
            for i in range(metadata['chunk_count']):
                chunk_key = f"features:{feature_set_name}:{version}:chunk_{i}"
                keys_to_delete.append(chunk_key)
            
            deleted_count = await self.redis_client.delete(*keys_to_delete)
            
            logger.info(
                f"Deleted feature set",
                feature_set=feature_set_name,
                version=version,
                keys_deleted=deleted_count
            )
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete feature set: {e}")
            return False
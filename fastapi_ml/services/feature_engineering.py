"""
Feature Engineering Service - Automated feature extraction and transformation
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from sklearn.preprocessing import StandardScaler, LabelEncoder, RobustScaler
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
from sklearn.decomposition import PCA
import structlog
from redis import Redis
import json

from ..config import settings, FEATURE_CONFIG

logger = structlog.get_logger()


class FeatureStore:
    """
    Production feature store with caching and versioning
    """
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis_client = redis_client
        self.feature_cache_ttl = settings.FEATURE_CACHE_TTL
        self.encoders: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_selectors: Dict[str, Any] = {}
        
    async def get_features(self, 
                          feature_set_name: str, 
                          entity_ids: List[str],
                          timestamp: Optional[datetime] = None) -> pd.DataFrame:
        """Get features for entities with point-in-time correctness"""
        cache_key = f"features:{feature_set_name}:{hash(str(entity_ids))}"
        
        # Try cache first
        if self.redis_client:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return pd.DataFrame(data)
        
        # Generate features
        features = await self._generate_features(feature_set_name, entity_ids, timestamp)
        
        # Cache results
        if self.redis_client and features is not None:
            await self.redis_client.setex(
                cache_key,
                self.feature_cache_ttl,
                features.to_json()
            )
        
        return features
    
    async def _generate_features(self, 
                               feature_set_name: str,
                               entity_ids: List[str],
                               timestamp: Optional[datetime] = None) -> pd.DataFrame:
        """Generate features based on feature set configuration"""
        # This would integrate with your database
        # For now, returning placeholder
        logger.info(
            "Generating features",
            feature_set=feature_set_name,
            entity_count=len(entity_ids)
        )
        
        # Placeholder - implement based on your data sources
        return pd.DataFrame()


class FeatureEngineer:
    """
    Advanced feature engineering with automated feature generation
    """
    
    def __init__(self, feature_store: Optional[FeatureStore] = None):
        self.feature_store = feature_store
        self.feature_transformers = {}
        self.feature_history = {}
        
    async def engineer_price_features(self, 
                                    data: pd.DataFrame,
                                    target_column: str = 'price') -> pd.DataFrame:
        """Engineer price-specific features"""
        try:
            features = data.copy()
            
            # Time-based features
            if 'timestamp' in features.columns:
                features = self._add_time_features(features)
            
            # Price lag features
            if target_column in features.columns:
                features = self._add_price_lag_features(features, target_column)
            
            # Statistical features
            features = self._add_statistical_features(features, target_column)
            
            # Market features
            features = self._add_market_features(features)
            
            # Supplier features
            features = self._add_supplier_features(features)
            
            # Category-specific features
            features = self._add_category_features(features)
            
            # Interaction features
            features = self._add_interaction_features(features)
            
            logger.info(
                "Price features engineered",
                original_columns=len(data.columns),
                engineered_columns=len(features.columns),
                added_features=len(features.columns) - len(data.columns)
            )
            
            return features
            
        except Exception as e:
            logger.error("Feature engineering failed", error=str(e), exc_info=True)
            return data
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features"""
        features = df.copy()
        
        if 'timestamp' not in features.columns:
            return features
        
        # Convert to datetime if not already
        features['timestamp'] = pd.to_datetime(features['timestamp'])
        
        # Extract time components
        time_features = FEATURE_CONFIG.get('time_features', [])
        
        if 'year' in time_features:
            features['year'] = features['timestamp'].dt.year
        
        if 'month' in time_features:
            features['month'] = features['timestamp'].dt.month
        
        if 'day_of_week' in time_features:
            features['day_of_week'] = features['timestamp'].dt.dayofweek
        
        if 'quarter' in time_features:
            features['quarter'] = features['timestamp'].dt.quarter
        
        if 'is_holiday' in time_features:
            # Simple holiday detection (customize based on your needs)
            features['is_holiday'] = features['timestamp'].dt.month.isin([12, 1]).astype(int)
        
        if 'is_weekend' in time_features:
            features['is_weekend'] = (features['timestamp'].dt.dayofweek >= 5).astype(int)
        
        # Cyclical encoding for periodic features
        features['month_sin'] = np.sin(2 * np.pi * features['timestamp'].dt.month / 12)
        features['month_cos'] = np.cos(2 * np.pi * features['timestamp'].dt.month / 12)
        features['day_of_week_sin'] = np.sin(2 * np.pi * features['timestamp'].dt.dayofweek / 7)
        features['day_of_week_cos'] = np.cos(2 * np.pi * features['timestamp'].dt.dayofweek / 7)
        
        return features
    
    def _add_price_lag_features(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        """Add price lag and rolling window features"""
        features = df.copy()
        
        if target_column not in features.columns:
            return features
        
        # Sort by timestamp for proper lag calculation
        if 'timestamp' in features.columns:
            features = features.sort_values('timestamp')
        
        # Group by material/supplier for meaningful lags
        group_cols = []
        for col in ['material_id', 'supplier_id', 'category']:
            if col in features.columns:
                group_cols.append(col)
        
        if group_cols:
            # Lag features
            price_features = FEATURE_CONFIG.get('price_features', [])
            
            for feature_name in price_features:
                if 'lag' in feature_name:
                    lag_days = int(feature_name.split('_')[-1])
                    features[feature_name] = features.groupby(group_cols)[target_column].shift(lag_days)
                
                elif 'rolling_mean' in feature_name:
                    window_days = int(feature_name.split('_')[-1])
                    features[feature_name] = (
                        features.groupby(group_cols)[target_column]
                        .rolling(window=window_days, min_periods=1)
                        .mean()
                        .reset_index(level=0, drop=True)
                    )
                
                elif 'rolling_std' in feature_name:
                    window_days = int(feature_name.split('_')[-1])
                    features[feature_name] = (
                        features.groupby(group_cols)[target_column]
                        .rolling(window=window_days, min_periods=1)
                        .std()
                        .reset_index(level=0, drop=True)
                    )
        
        # Price change features
        if 'price_lag_1' in features.columns:
            features['price_change_1d'] = features[target_column] - features['price_lag_1']
            features['price_change_1d_pct'] = (
                (features[target_column] - features['price_lag_1']) / features['price_lag_1']
            ).fillna(0)
        
        return features
    
    def _add_statistical_features(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        """Add statistical aggregation features"""
        features = df.copy()
        
        # Group-based statistics
        group_cols = ['supplier_id', 'material_category', 'region']
        available_groups = [col for col in group_cols if col in features.columns]
        
        if target_column in features.columns and available_groups:
            for group_col in available_groups:
                # Mean price by group
                group_mean = features.groupby(group_col)[target_column].transform('mean')
                features[f'{group_col}_avg_price'] = group_mean
                
                # Price deviation from group mean
                features[f'{group_col}_price_deviation'] = features[target_column] - group_mean
                
                # Group volatility
                group_std = features.groupby(group_col)[target_column].transform('std')
                features[f'{group_col}_price_volatility'] = group_std
                
                # Z-score within group
                features[f'{group_col}_price_zscore'] = (
                    (features[target_column] - group_mean) / group_std
                ).fillna(0)
        
        return features
    
    def _add_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market-related features"""
        features = df.copy()
        
        # Market trend indicators (placeholder - integrate with real market data)
        market_features = FEATURE_CONFIG.get('market_features', [])
        
        for feature_name in market_features:
            if feature_name not in features.columns:
                # Generate synthetic market features (replace with real data)
                if 'commodity_price_index' in feature_name:
                    features[feature_name] = np.random.normal(100, 10, len(features))
                elif 'inflation_rate' in feature_name:
                    features[feature_name] = np.random.normal(0.02, 0.005, len(features))
                elif 'exchange_rate' in feature_name:
                    features[feature_name] = np.random.normal(1.0, 0.1, len(features))
                elif 'market_volatility' in feature_name:
                    features[feature_name] = np.random.normal(0.2, 0.05, len(features))
        
        return features
    
    def _add_supplier_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add supplier-specific features"""
        features = df.copy()
        
        supplier_features = FEATURE_CONFIG.get('supplier_features', [])
        
        if 'supplier_id' in features.columns:
            # Supplier performance metrics (placeholder)
            for feature_name in supplier_features:
                if feature_name not in features.columns:
                    if 'rating' in feature_name:
                        features[feature_name] = np.random.uniform(1, 5, len(features))
                    elif 'delivery_score' in feature_name:
                        features[feature_name] = np.random.uniform(0.7, 1.0, len(features))
                    elif 'avg_price' in feature_name:
                        # Calculate from existing data or use placeholder
                        if 'price' in features.columns:
                            supplier_avg = features.groupby('supplier_id')['price'].transform('mean')
                            features[feature_name] = supplier_avg
                        else:
                            features[feature_name] = np.random.normal(100, 20, len(features))
        
        return features
    
    def _add_category_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add category-specific features"""
        features = df.copy()
        
        # Category encoding and features
        categorical_features = FEATURE_CONFIG.get('categorical_features', [])
        
        for cat_feature in categorical_features:
            if cat_feature in features.columns:
                # Category frequency
                category_counts = features[cat_feature].value_counts()
                features[f'{cat_feature}_frequency'] = features[cat_feature].map(category_counts)
                
                # Category rarity (inverse frequency)
                total_count = len(features)
                features[f'{cat_feature}_rarity'] = total_count / features[f'{cat_feature}_frequency']
        
        return features
    
    def _add_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add interaction features between important variables"""
        features = df.copy()
        
        # Key interaction pairs
        interactions = [
            ('quantity', 'supplier_rating'),
            ('material_category_frequency', 'supplier_rating'),
            ('month', 'material_category_frequency'),
        ]
        
        for feat1, feat2 in interactions:
            if feat1 in features.columns and feat2 in features.columns:
                # Multiplicative interaction
                features[f'{feat1}_{feat2}_interaction'] = (
                    features[feat1] * features[feat2]
                )
        
        return features
    
    async def engineer_anomaly_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer features specifically for anomaly detection"""
        try:
            features = data.copy()
            
            # Price deviation features
            if 'price' in features.columns:
                # Global price statistics
                global_mean = features['price'].mean()
                global_std = features['price'].std()
                
                features['price_zscore_global'] = (features['price'] - global_mean) / global_std
                features['price_deviation_global'] = np.abs(features['price'] - global_mean)
                
                # Percentile-based features
                features['price_percentile'] = features['price'].rank(pct=True)
                
                # IQR-based outlier score
                q1 = features['price'].quantile(0.25)
                q3 = features['price'].quantile(0.75)
                iqr = q3 - q1
                
                features['price_iqr_score'] = np.maximum(
                    (features['price'] - q3) / iqr,
                    (q1 - features['price']) / iqr
                ).fillna(0)
            
            # Quantity-based anomaly features
            if 'quantity' in features.columns:
                # Unusual quantity patterns
                features['quantity_log'] = np.log1p(features['quantity'])
                
                # Quantity vs historical patterns
                if 'material_id' in features.columns:
                    material_qty_mean = features.groupby('material_id')['quantity'].transform('mean')
                    material_qty_std = features.groupby('material_id')['quantity'].transform('std')
                    
                    features['quantity_material_zscore'] = (
                        (features['quantity'] - material_qty_mean) / material_qty_std
                    ).fillna(0)
            
            # Time-based anomaly features
            if 'timestamp' in features.columns:
                features['timestamp'] = pd.to_datetime(features['timestamp'])
                
                # Day of week anomaly (orders on unusual days)
                dow_counts = features['timestamp'].dt.dayofweek.value_counts()
                features['dow_rarity'] = features['timestamp'].dt.dayofweek.map(dow_counts)
                
                # Hour of day anomaly (if time is available)
                if features['timestamp'].dt.hour.nunique() > 1:
                    hour_counts = features['timestamp'].dt.hour.value_counts()
                    features['hour_rarity'] = features['timestamp'].dt.hour.map(hour_counts)
            
            logger.info(
                "Anomaly features engineered",
                original_columns=len(data.columns),
                total_columns=len(features.columns)
            )
            
            return features
            
        except Exception as e:
            logger.error("Anomaly feature engineering failed", error=str(e))
            return data
    
    async def select_features(self, 
                            X: pd.DataFrame, 
                            y: pd.Series,
                            method: str = 'mutual_info',
                            k: int = 50) -> Tuple[pd.DataFrame, List[str]]:
        """Automated feature selection"""
        try:
            # Remove non-numeric columns for feature selection
            numeric_X = X.select_dtypes(include=[np.number])
            
            if len(numeric_X.columns) == 0:
                logger.warning("No numeric features for selection")
                return X, list(X.columns)
            
            # Choose selection method
            if method == 'mutual_info':
                selector = SelectKBest(score_func=mutual_info_regression, k=min(k, len(numeric_X.columns)))
            else:
                selector = SelectKBest(score_func=f_regression, k=min(k, len(numeric_X.columns)))
            
            # Fit selector
            X_selected = selector.fit_transform(numeric_X.fillna(0), y)
            
            # Get selected feature names
            selected_features = numeric_X.columns[selector.get_support()].tolist()
            
            # Add back non-numeric features
            non_numeric_features = X.select_dtypes(exclude=[np.number]).columns.tolist()
            final_features = selected_features + non_numeric_features
            
            result_df = X[final_features]
            
            logger.info(
                "Feature selection completed",
                original_features=len(X.columns),
                selected_features=len(final_features),
                method=method
            )
            
            return result_df, final_features
            
        except Exception as e:
            logger.error("Feature selection failed", error=str(e))
            return X, list(X.columns)
    
    async def preprocess_features(self, 
                                X: pd.DataFrame,
                                feature_names: List[str],
                                fit_transforms: bool = True) -> pd.DataFrame:
        """Preprocess features with scaling and encoding"""
        try:
            processed_X = X.copy()
            
            # Handle categorical features
            categorical_features = FEATURE_CONFIG.get('categorical_features', [])
            for cat_feature in categorical_features:
                if cat_feature in processed_X.columns:
                    if fit_transforms:
                        encoder = LabelEncoder()
                        processed_X[cat_feature] = encoder.fit_transform(
                            processed_X[cat_feature].fillna('missing')
                        )
                        self.encoders[cat_feature] = encoder
                    elif cat_feature in self.encoders:
                        encoder = self.encoders[cat_feature]
                        # Handle unseen categories
                        processed_X[cat_feature] = processed_X[cat_feature].fillna('missing')
                        
                        # Map unseen categories to a default value
                        mask = processed_X[cat_feature].isin(encoder.classes_)
                        processed_X.loc[~mask, cat_feature] = 'missing'
                        
                        processed_X[cat_feature] = encoder.transform(processed_X[cat_feature])
            
            # Scale numeric features
            numeric_features = processed_X.select_dtypes(include=[np.number]).columns.tolist()
            
            if numeric_features:
                if fit_transforms:
                    scaler = RobustScaler()  # More robust to outliers than StandardScaler
                    processed_X[numeric_features] = scaler.fit_transform(
                        processed_X[numeric_features].fillna(0)
                    )
                    self.scalers['numeric'] = scaler
                elif 'numeric' in self.scalers:
                    scaler = self.scalers['numeric']
                    processed_X[numeric_features] = scaler.transform(
                        processed_X[numeric_features].fillna(0)
                    )
            
            logger.info(
                "Feature preprocessing completed",
                categorical_features=len([f for f in categorical_features if f in processed_X.columns]),
                numeric_features=len(numeric_features)
            )
            
            return processed_X
            
        except Exception as e:
            logger.error("Feature preprocessing failed", error=str(e))
            return X
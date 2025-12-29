"""
ML Service - Core machine learning service for pricing predictions
"""
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import structlog
from sklearn.ensemble import IsolationForest, RandomForestRegressor
import lightgbm as lgb
from prophet import Prophet
import json
from redis import Redis

from .model_registry import ModelRegistry, ModelMetadata
from .feature_engineering import FeatureEngineer, FeatureStore
from ..config import settings, MODEL_CONFIG

logger = structlog.get_logger()


class PricePredictionModel:
    """
    LightGBM-based price prediction model with business logic
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.feature_names = config.get('features', [])
        self.is_trained = False
        
    def train(self, X: pd.DataFrame, y: pd.Series, 
              X_val: Optional[pd.DataFrame] = None, 
              y_val: Optional[pd.Series] = None) -> Dict[str, float]:
        """Train the price prediction model"""
        try:
            # Prepare LightGBM datasets
            train_data = lgb.Dataset(X, label=y, feature_name=self.feature_names)
            
            valid_sets = [train_data]
            if X_val is not None and y_val is not None:
                val_data = lgb.Dataset(X_val, label=y_val, feature_name=self.feature_names)
                valid_sets.append(val_data)
            
            # Train model
            hyperparams = self.config.get('hyperparameters', {})
            
            self.model = lgb.train(
                hyperparams,
                train_data,
                valid_sets=valid_sets,
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
            )
            
            self.is_trained = True
            
            # Calculate metrics
            y_pred = self.model.predict(X)
            metrics = self._calculate_metrics(y, y_pred)
            
            if X_val is not None and y_val is not None:
                y_val_pred = self.model.predict(X_val)
                val_metrics = self._calculate_metrics(y_val, y_val_pred)
                metrics.update({f'val_{k}': v for k, v in val_metrics.items()})
            
            logger.info("Price prediction model trained", metrics=metrics)
            return metrics
            
        except Exception as e:
            logger.error("Model training failed", error=str(e), exc_info=True)
            raise
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make price predictions"""
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained")
        
        return self.model.predict(X)
    
    def predict_with_uncertainty(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict with uncertainty estimation"""
        predictions = self.predict(X)
        
        # Simple uncertainty based on feature importance and prediction confidence
        # In production, consider using quantile regression or ensemble methods
        feature_importance = self.model.feature_importance()
        uncertainty = np.std(predictions) * np.ones_like(predictions) * 0.1
        
        return predictions, uncertainty
    
    def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate model performance metrics"""
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        return {
            'mae': mae,
            'rmse': rmse,
            'r2': r2,
            'mape': mape
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        if not self.is_trained or self.model is None:
            return {}
        
        importance_scores = self.model.feature_importance()
        return dict(zip(self.feature_names, importance_scores))


class AnomalyDetectionModel:
    """
    Isolation Forest-based anomaly detection for pricing
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = IsolationForest(**config.get('hyperparameters', {}))
        self.is_trained = False
        
    def train(self, X: pd.DataFrame) -> Dict[str, float]:
        """Train anomaly detection model"""
        try:
            self.model.fit(X)
            self.is_trained = True
            
            # Calculate metrics on training data
            anomaly_scores = self.model.decision_function(X)
            outliers = self.model.predict(X)
            
            outlier_ratio = (outliers == -1).mean()
            avg_anomaly_score = np.mean(anomaly_scores)
            
            metrics = {
                'outlier_ratio': outlier_ratio,
                'avg_anomaly_score': avg_anomaly_score
            }
            
            logger.info("Anomaly detection model trained", metrics=metrics)
            return metrics
            
        except Exception as e:
            logger.error("Anomaly model training failed", error=str(e))
            raise
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict anomalies and return anomaly scores"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        anomaly_predictions = self.model.predict(X)
        anomaly_scores = self.model.decision_function(X)
        
        return anomaly_predictions, anomaly_scores
    
    def detect_price_anomalies(self, 
                             data: pd.DataFrame,
                             threshold: float = -0.1) -> pd.DataFrame:
        """Detect price anomalies with business context"""
        if 'price' not in data.columns:
            raise ValueError("Price column not found")
        
        predictions, scores = self.predict(data)
        
        result = data.copy()
        result['anomaly_prediction'] = predictions
        result['anomaly_score'] = scores
        result['is_anomaly'] = (predictions == -1) | (scores < threshold)
        
        # Add business context
        if result['is_anomaly'].any():
            anomalies = result[result['is_anomaly']].copy()
            
            # Calculate price deviation from expected ranges
            if 'material_category' in data.columns:
                category_stats = data.groupby('material_category')['price'].agg(['mean', 'std'])
                
                for idx, row in anomalies.iterrows():
                    category = row['material_category']
                    if category in category_stats.index:
                        mean_price = category_stats.loc[category, 'mean']
                        std_price = category_stats.loc[category, 'std']
                        
                        result.loc[idx, 'price_deviation_sigma'] = (
                            (row['price'] - mean_price) / std_price if std_price > 0 else 0
                        )
        
        return result


class DemandForecastModel:
    """
    Prophet-based demand forecasting model
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = Prophet(**config.get('hyperparameters', {}))
        self.is_trained = False
        
    def train(self, data: pd.DataFrame) -> Dict[str, float]:
        """Train demand forecast model"""
        try:
            # Prepare data for Prophet (requires 'ds' and 'y' columns)
            if not all(col in data.columns for col in ['ds', 'y']):
                raise ValueError("Prophet requires 'ds' (datestamp) and 'y' (value) columns")
            
            self.model.fit(data)
            self.is_trained = True
            
            # Calculate metrics using cross-validation
            from prophet.diagnostics import cross_validation, performance_metrics
            
            df_cv = cross_validation(self.model, initial='180 days', period='30 days', horizon='30 days')
            df_metrics = performance_metrics(df_cv)
            
            metrics = {
                'mape': df_metrics['mape'].mean(),
                'mae': df_metrics['mae'].mean(),
                'rmse': df_metrics['rmse'].mean()
            }
            
            logger.info("Demand forecast model trained", metrics=metrics)
            return metrics
            
        except Exception as e:
            logger.error("Demand forecast training failed", error=str(e))
            raise
    
    def predict(self, periods: int = 30) -> pd.DataFrame:
        """Generate demand forecast"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        future = self.model.make_future_dataframe(periods=periods)
        forecast = self.model.predict(future)
        
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    
    def predict_custom_dates(self, dates: pd.DataFrame) -> pd.DataFrame:
        """Predict for specific dates"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        forecast = self.model.predict(dates)
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


class ShouldCostModel:
    """
    Should-cost modeling with component breakdown
    """
    
    def __init__(self):
        self.material_costs = {}
        self.labor_rates = {}
        self.overhead_factors = {}
        self.is_initialized = False
        
    async def initialize(self, cost_data: Dict[str, Any]) -> None:
        """Initialize should-cost model with cost data"""
        self.material_costs = cost_data.get('materials', {})
        self.labor_rates = cost_data.get('labor', {})
        self.overhead_factors = cost_data.get('overhead', {})
        self.is_initialized = True
        
        logger.info("Should-cost model initialized")
    
    def calculate_should_cost(self, 
                            material_specs: Dict[str, Any],
                            quantity: int = 1) -> Dict[str, Any]:
        """Calculate should-cost with component breakdown"""
        if not self.is_initialized:
            raise ValueError("Model not initialized")
        
        breakdown = {
            'material_cost': 0,
            'labor_cost': 0,
            'overhead_cost': 0,
            'total_cost': 0,
            'unit_cost': 0,
            'components': []
        }
        
        # Calculate material costs
        for component, specs in material_specs.items():
            component_cost = self._calculate_component_cost(component, specs)
            breakdown['components'].append({
                'component': component,
                'cost': component_cost,
                'specs': specs
            })
            breakdown['material_cost'] += component_cost
        
        # Calculate labor costs
        labor_hours = material_specs.get('labor_hours', 0)
        labor_rate = self.labor_rates.get('default', 50)  # $50/hour default
        breakdown['labor_cost'] = labor_hours * labor_rate
        
        # Calculate overhead
        base_cost = breakdown['material_cost'] + breakdown['labor_cost']
        overhead_factor = self.overhead_factors.get('default', 0.2)  # 20% default
        breakdown['overhead_cost'] = base_cost * overhead_factor
        
        # Total costs
        breakdown['total_cost'] = (
            breakdown['material_cost'] + 
            breakdown['labor_cost'] + 
            breakdown['overhead_cost']
        )
        breakdown['unit_cost'] = breakdown['total_cost'] / quantity if quantity > 0 else 0
        
        return breakdown
    
    def _calculate_component_cost(self, component: str, specs: Dict[str, Any]) -> float:
        """Calculate cost for individual component"""
        material_type = specs.get('material_type', 'default')
        weight = specs.get('weight', 0)  # in kg
        complexity_factor = specs.get('complexity', 1.0)
        
        # Base material cost
        cost_per_kg = self.material_costs.get(material_type, 10)  # $10/kg default
        base_cost = weight * cost_per_kg
        
        # Apply complexity factor
        adjusted_cost = base_cost * complexity_factor
        
        return adjusted_cost


class MLService:
    """
    Main ML service orchestrating all models and predictions
    """
    
    def __init__(self, model_registry: ModelRegistry):
        self.model_registry = model_registry
        self.feature_engineer = FeatureEngineer()
        self.feature_store = FeatureStore()
        self.should_cost_model = ShouldCostModel()
        self.redis_client: Optional[Redis] = None
        
        # Model instances
        self.price_model = None
        self.anomaly_model = None
        self.demand_model = None
        
        self.prediction_cache_ttl = settings.PREDICTION_CACHE_TTL
        
    async def initialize(self, redis_client: Redis) -> None:
        """Initialize ML service"""
        self.redis_client = redis_client
        self.feature_store = FeatureStore(redis_client)
        
        # Initialize should-cost model with default data
        await self.should_cost_model.initialize({
            'materials': {
                'steel': 2.5,  # $2.5/kg
                'aluminum': 4.0,
                'plastic': 1.2,
                'default': 3.0
            },
            'labor': {'default': 50},  # $50/hour
            'overhead': {'default': 0.25}  # 25%
        })
        
        logger.info("ML service initialized")
    
    async def predict_prices(self, 
                           items: List[Dict[str, Any]],
                           include_uncertainty: bool = True) -> List[Dict[str, Any]]:
        """Predict prices for multiple items"""
        try:
            # Convert to DataFrame
            df = pd.DataFrame(items)
            
            # Engineer features
            engineered_df = await self.feature_engineer.engineer_price_features(df)
            
            # Get model
            model = await self.model_registry.get_model('price_predictor')
            if model is None:
                # Fallback to simple heuristic
                return await self._fallback_price_prediction(items)
            
            # Make predictions
            if include_uncertainty:
                predictions, uncertainties = model.predict_with_uncertainty(engineered_df)
            else:
                predictions = model.predict(engineered_df)
                uncertainties = None
            
            # Format results
            results = []
            for i, item in enumerate(items):
                result = {
                    'item_id': item.get('item_id', f'item_{i}'),
                    'predicted_price': float(predictions[i]),
                    'confidence_interval': {
                        'lower': float(predictions[i] - uncertainties[i]) if uncertainties is not None else None,
                        'upper': float(predictions[i] + uncertainties[i]) if uncertainties is not None else None
                    },
                    'prediction_timestamp': datetime.utcnow().isoformat(),
                    'model_version': (await self.model_registry.get_model_metadata('price_predictor')).version
                }
                results.append(result)
            
            logger.info("Price predictions completed", item_count=len(items))
            return results
            
        except Exception as e:
            logger.error("Price prediction failed", error=str(e), exc_info=True)
            return await self._fallback_price_prediction(items)
    
    async def _fallback_price_prediction(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback price prediction using business rules"""
        results = []
        
        for i, item in enumerate(items):
            # Simple heuristic based on category and quantity
            base_price = 100  # Default base price
            
            category_multipliers = {
                'electronics': 1.5,
                'machinery': 2.0,
                'materials': 0.8,
                'services': 1.2
            }
            
            category = item.get('category', 'default')
            multiplier = category_multipliers.get(category, 1.0)
            
            quantity = item.get('quantity', 1)
            quantity_discount = max(0.7, 1 - (quantity / 1000) * 0.1)  # Volume discount
            
            predicted_price = base_price * multiplier * quantity_discount
            
            result = {
                'item_id': item.get('item_id', f'item_{i}'),
                'predicted_price': predicted_price,
                'confidence_interval': {
                    'lower': predicted_price * 0.9,
                    'upper': predicted_price * 1.1
                },
                'prediction_timestamp': datetime.utcnow().isoformat(),
                'model_version': 'fallback_1.0',
                'fallback_used': True
            }
            results.append(result)
        
        return results
    
    async def detect_anomalies(self, 
                             data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect pricing anomalies"""
        try:
            df = pd.DataFrame(data)
            
            # Engineer features for anomaly detection
            engineered_df = await self.feature_engineer.engineer_anomaly_features(df)
            
            # Get anomaly model
            model = await self.model_registry.get_model('anomaly_detector')
            if model is None:
                return await self._fallback_anomaly_detection(data)
            
            # Detect anomalies
            anomaly_results = model.detect_price_anomalies(engineered_df)
            
            # Format results
            results = []
            for idx, row in anomaly_results.iterrows():
                if row.get('is_anomaly', False):
                    result = {
                        'item_id': row.get('item_id', f'item_{idx}'),
                        'anomaly_score': float(row.get('anomaly_score', 0)),
                        'anomaly_type': self._classify_anomaly_type(row),
                        'severity': self._get_anomaly_severity(row.get('anomaly_score', 0)),
                        'explanation': self._explain_anomaly(row),
                        'detected_at': datetime.utcnow().isoformat()
                    }
                    results.append(result)
            
            logger.info("Anomaly detection completed", anomalies_found=len(results))
            return results
            
        except Exception as e:
            logger.error("Anomaly detection failed", error=str(e))
            return await self._fallback_anomaly_detection(data)
    
    def _classify_anomaly_type(self, row: pd.Series) -> str:
        """Classify type of anomaly"""
        price_deviation = row.get('price_deviation_sigma', 0)
        
        if abs(price_deviation) > 3:
            return 'extreme_price_deviation'
        elif row.get('quantity_material_zscore', 0) > 2:
            return 'unusual_quantity'
        else:
            return 'general_anomaly'
    
    def _get_anomaly_severity(self, anomaly_score: float) -> str:
        """Get severity level of anomaly"""
        if anomaly_score < -0.3:
            return 'high'
        elif anomaly_score < -0.1:
            return 'medium'
        else:
            return 'low'
    
    def _explain_anomaly(self, row: pd.Series) -> str:
        """Generate human-readable explanation of anomaly"""
        explanations = []
        
        price_deviation = row.get('price_deviation_sigma', 0)
        if abs(price_deviation) > 2:
            if price_deviation > 0:
                explanations.append(f"Price is {price_deviation:.1f} standard deviations above category average")
            else:
                explanations.append(f"Price is {abs(price_deviation):.1f} standard deviations below category average")
        
        quantity_zscore = row.get('quantity_material_zscore', 0)
        if abs(quantity_zscore) > 2:
            explanations.append(f"Unusual quantity for this material type")
        
        if not explanations:
            explanations.append("General pattern anomaly detected")
        
        return "; ".join(explanations)
    
    async def _fallback_anomaly_detection(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback anomaly detection using statistical methods"""
        results = []
        
        if not data:
            return results
        
        # Simple statistical approach
        prices = [item.get('price', 0) for item in data if 'price' in item]
        if not prices:
            return results
        
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        
        for i, item in enumerate(data):
            price = item.get('price', 0)
            if price > 0:
                z_score = (price - mean_price) / std_price if std_price > 0 else 0
                
                if abs(z_score) > 2:  # 2 sigma threshold
                    result = {
                        'item_id': item.get('item_id', f'item_{i}'),
                        'anomaly_score': -abs(z_score) / 3,  # Normalize to [-1, 0] range
                        'anomaly_type': 'statistical_outlier',
                        'severity': 'high' if abs(z_score) > 3 else 'medium',
                        'explanation': f"Price deviates {abs(z_score):.1f} standard deviations from mean",
                        'detected_at': datetime.utcnow().isoformat(),
                        'fallback_used': True
                    }
                    results.append(result)
        
        return results
    
    async def forecast_demand(self, 
                            material_id: str,
                            periods: int = 30) -> Dict[str, Any]:
        """Forecast demand for a material"""
        try:
            # Get demand model
            model = await self.model_registry.get_model('demand_forecaster')
            if model is None:
                return await self._fallback_demand_forecast(material_id, periods)
            
            # Generate forecast
            forecast = model.predict(periods)
            
            # Format results
            result = {
                'material_id': material_id,
                'forecast_periods': periods,
                'predictions': [],
                'generated_at': datetime.utcnow().isoformat(),
                'model_version': (await self.model_registry.get_model_metadata('demand_forecaster')).version
            }
            
            for _, row in forecast.iterrows():
                prediction = {
                    'date': row['ds'].isoformat() if hasattr(row['ds'], 'isoformat') else str(row['ds']),
                    'predicted_demand': float(row['yhat']),
                    'lower_bound': float(row['yhat_lower']),
                    'upper_bound': float(row['yhat_upper'])
                }
                result['predictions'].append(prediction)
            
            logger.info("Demand forecast completed", material_id=material_id, periods=periods)
            return result
            
        except Exception as e:
            logger.error("Demand forecasting failed", error=str(e))
            return await self._fallback_demand_forecast(material_id, periods)
    
    async def _fallback_demand_forecast(self, material_id: str, periods: int) -> Dict[str, Any]:
        """Fallback demand forecast using simple trend"""
        base_demand = 100  # Base demand
        trend = 0.02  # 2% growth per period
        seasonality = 0.1  # 10% seasonal variation
        
        predictions = []
        start_date = datetime.utcnow()
        
        for i in range(periods):
            date = start_date + timedelta(days=i)
            
            # Simple trend + seasonality
            trend_component = base_demand * (1 + trend) ** i
            seasonal_component = seasonality * np.sin(2 * np.pi * i / 30)  # 30-day cycle
            
            predicted_demand = trend_component * (1 + seasonal_component)
            
            prediction = {
                'date': date.isoformat(),
                'predicted_demand': predicted_demand,
                'lower_bound': predicted_demand * 0.8,
                'upper_bound': predicted_demand * 1.2
            }
            predictions.append(prediction)
        
        return {
            'material_id': material_id,
            'forecast_periods': periods,
            'predictions': predictions,
            'generated_at': datetime.utcnow().isoformat(),
            'model_version': 'fallback_1.0',
            'fallback_used': True
        }
    
    async def calculate_should_cost(self, 
                                  material_specs: Dict[str, Any],
                                  quantity: int = 1) -> Dict[str, Any]:
        """Calculate should-cost with breakdown"""
        try:
            breakdown = self.should_cost_model.calculate_should_cost(material_specs, quantity)
            
            # Add metadata
            breakdown.update({
                'calculated_at': datetime.utcnow().isoformat(),
                'quantity': quantity,
                'material_specs': material_specs
            })
            
            logger.info("Should-cost calculated", total_cost=breakdown['total_cost'])
            return breakdown
            
        except Exception as e:
            logger.error("Should-cost calculation failed", error=str(e))
            raise
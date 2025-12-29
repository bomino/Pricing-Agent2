"""
Model Monitoring and Drift Detection Service
"""
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import structlog
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score
from scipy import stats
from scipy.spatial.distance import jensenshannon
import json
import redis.asyncio as redis
from pathlib import Path

from .model_registry import ModelRegistry
from ..config import settings

logger = structlog.get_logger()


class DriftDetector:
    """Statistical drift detection for model inputs and outputs"""
    
    def __init__(self):
        self.drift_methods = {
            'ks_test': self._kolmogorov_smirnov_test,
            'js_divergence': self._jensen_shannon_divergence,
            'psi': self._population_stability_index,
            'statistical_test': self._statistical_test
        }
        
        self.drift_thresholds = {
            'ks_test': 0.05,  # p-value threshold
            'js_divergence': 0.1,  # JS divergence threshold
            'psi': 0.2,  # PSI threshold
            'statistical_test': 0.05  # p-value threshold
        }
    
    async def detect_feature_drift(self, 
                                 reference_data: pd.DataFrame,
                                 current_data: pd.DataFrame,
                                 feature_columns: List[str],
                                 method: str = 'ks_test') -> Dict[str, Any]:
        """Detect drift in input features"""
        
        if method not in self.drift_methods:
            raise ValueError(f"Unknown drift detection method: {method}")
        
        drift_results = {
            'overall_drift_detected': False,
            'method': method,
            'threshold': self.drift_thresholds[method],
            'feature_drift': {},
            'drift_score': 0.0,
            'detected_at': datetime.utcnow().isoformat()
        }
        
        drift_scores = []
        
        for feature in feature_columns:
            if feature in reference_data.columns and feature in current_data.columns:
                # Skip non-numeric features for certain methods
                if method in ['ks_test', 'statistical_test'] and not pd.api.types.is_numeric_dtype(reference_data[feature]):
                    continue
                
                drift_score, is_drift = await self.drift_methods[method](
                    reference_data[feature].dropna(),
                    current_data[feature].dropna()
                )
                
                drift_results['feature_drift'][feature] = {
                    'drift_score': drift_score,
                    'is_drift': is_drift,
                    'reference_samples': len(reference_data[feature].dropna()),
                    'current_samples': len(current_data[feature].dropna())
                }
                
                if is_drift:
                    drift_results['overall_drift_detected'] = True
                
                drift_scores.append(drift_score)
        
        # Calculate overall drift score
        if drift_scores:
            drift_results['drift_score'] = np.mean(drift_scores)
        
        drift_results['features_analyzed'] = len(drift_results['feature_drift'])
        drift_results['features_with_drift'] = sum(
            1 for f in drift_results['feature_drift'].values() if f['is_drift']
        )
        
        logger.info(
            "Feature drift detection completed",
            method=method,
            features_analyzed=drift_results['features_analyzed'],
            features_with_drift=drift_results['features_with_drift'],
            overall_drift=drift_results['overall_drift_detected']
        )
        
        return drift_results
    
    async def detect_prediction_drift(self,
                                    reference_predictions: np.ndarray,
                                    current_predictions: np.ndarray,
                                    method: str = 'ks_test') -> Dict[str, Any]:
        """Detect drift in model predictions"""
        
        if method not in self.drift_methods:
            raise ValueError(f"Unknown drift detection method: {method}")
        
        drift_score, is_drift = await self.drift_methods[method](
            reference_predictions,
            current_predictions
        )
        
        result = {
            'drift_detected': is_drift,
            'drift_score': drift_score,
            'method': method,
            'threshold': self.drift_thresholds[method],
            'reference_samples': len(reference_predictions),
            'current_samples': len(current_predictions),
            'detected_at': datetime.utcnow().isoformat()
        }
        
        # Additional statistics
        result['statistics'] = {
            'reference_mean': float(np.mean(reference_predictions)),
            'reference_std': float(np.std(reference_predictions)),
            'current_mean': float(np.mean(current_predictions)),
            'current_std': float(np.std(current_predictions)),
            'mean_shift': float(np.mean(current_predictions) - np.mean(reference_predictions)),
            'std_ratio': float(np.std(current_predictions) / np.std(reference_predictions)) if np.std(reference_predictions) > 0 else 1.0
        }
        
        return result
    
    async def _kolmogorov_smirnov_test(self, 
                                     reference: np.ndarray, 
                                     current: np.ndarray) -> Tuple[float, bool]:
        """Kolmogorov-Smirnov test for distribution comparison"""
        try:
            statistic, p_value = stats.ks_2samp(reference, current)
            is_drift = p_value < self.drift_thresholds['ks_test']
            return float(p_value), is_drift
        except Exception as e:
            logger.warning(f"KS test failed: {e}")
            return 1.0, False
    
    async def _jensen_shannon_divergence(self,
                                       reference: np.ndarray,
                                       current: np.ndarray) -> Tuple[float, bool]:
        """Jensen-Shannon divergence for distribution comparison"""
        try:
            # Create histograms
            combined = np.concatenate([reference, current])
            bins = np.histogram_bin_edges(combined, bins=50)
            
            ref_hist, _ = np.histogram(reference, bins=bins, density=True)
            curr_hist, _ = np.histogram(current, bins=bins, density=True)
            
            # Add small epsilon to avoid division by zero
            epsilon = 1e-10
            ref_hist += epsilon
            curr_hist += epsilon
            
            # Normalize
            ref_hist = ref_hist / np.sum(ref_hist)
            curr_hist = curr_hist / np.sum(curr_hist)
            
            # Calculate JS divergence
            js_distance = jensenshannon(ref_hist, curr_hist)
            is_drift = js_distance > self.drift_thresholds['js_divergence']
            
            return float(js_distance), is_drift
            
        except Exception as e:
            logger.warning(f"JS divergence calculation failed: {e}")
            return 0.0, False
    
    async def _population_stability_index(self,
                                        reference: np.ndarray,
                                        current: np.ndarray) -> Tuple[float, bool]:
        """Population Stability Index (PSI) calculation"""
        try:
            # Create quantile-based bins from reference data
            bins = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
            
            if len(bins) < 2:
                return 0.0, False
            
            # Calculate proportions for each bin
            ref_counts = np.histogram(reference, bins=bins)[0]
            curr_counts = np.histogram(current, bins=bins)[0]
            
            # Normalize to get proportions
            ref_props = ref_counts / np.sum(ref_counts)
            curr_props = curr_counts / np.sum(curr_counts)
            
            # Add small epsilon to avoid log(0)
            epsilon = 1e-10
            ref_props = np.maximum(ref_props, epsilon)
            curr_props = np.maximum(curr_props, epsilon)
            
            # Calculate PSI
            psi = np.sum((curr_props - ref_props) * np.log(curr_props / ref_props))
            is_drift = psi > self.drift_thresholds['psi']
            
            return float(psi), is_drift
            
        except Exception as e:
            logger.warning(f"PSI calculation failed: {e}")
            return 0.0, False
    
    async def _statistical_test(self,
                              reference: np.ndarray,
                              current: np.ndarray) -> Tuple[float, bool]:
        """Statistical test for mean and variance differences"""
        try:
            # T-test for means
            t_stat, t_p_value = stats.ttest_ind(reference, current, equal_var=False)
            
            # F-test for variances
            f_stat = np.var(current) / np.var(reference) if np.var(reference) > 0 else 1.0
            f_p_value = 2 * min(stats.f.cdf(f_stat, len(current)-1, len(reference)-1),
                               1 - stats.f.cdf(f_stat, len(current)-1, len(reference)-1))
            
            # Combined p-value using Fisher's method
            combined_p = stats.combine_pvalues([t_p_value, f_p_value], method='fisher')[1]
            
            is_drift = combined_p < self.drift_thresholds['statistical_test']
            
            return float(combined_p), is_drift
            
        except Exception as e:
            logger.warning(f"Statistical test failed: {e}")
            return 1.0, False


class PerformanceMonitor:
    """Monitor model performance metrics"""
    
    def __init__(self):
        self.performance_thresholds = {
            'regression': {
                'r2_score': {'min': 0.8, 'warning': 0.85},
                'mae': {'max': 0.15, 'warning': 0.12},
                'rmse': {'max': 0.20, 'warning': 0.17},
                'mape': {'max': 15.0, 'warning': 12.0}  # Mean Absolute Percentage Error
            },
            'classification': {
                'accuracy': {'min': 0.85, 'warning': 0.90},
                'precision': {'min': 0.80, 'warning': 0.85},
                'recall': {'min': 0.75, 'warning': 0.80}
            }
        }
    
    async def calculate_regression_metrics(self,
                                         y_true: np.ndarray,
                                         y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate regression performance metrics"""
        try:
            metrics = {}
            
            # Basic metrics
            metrics['mae'] = float(mean_absolute_error(y_true, y_pred))
            metrics['rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            metrics['r2_score'] = float(r2_score(y_true, y_pred))
            
            # MAPE (handling division by zero)
            mask = y_true != 0
            if np.any(mask):
                mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
                metrics['mape'] = float(mape)
            else:
                metrics['mape'] = float('inf')
            
            # Residual statistics
            residuals = y_true - y_pred
            metrics['residual_mean'] = float(np.mean(residuals))
            metrics['residual_std'] = float(np.std(residuals))
            
            # Prediction statistics
            metrics['pred_mean'] = float(np.mean(y_pred))
            metrics['pred_std'] = float(np.std(y_pred))
            metrics['true_mean'] = float(np.mean(y_true))
            metrics['true_std'] = float(np.std(y_true))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate regression metrics: {e}")
            return {}
    
    async def calculate_classification_metrics(self,
                                             y_true: np.ndarray,
                                             y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate classification performance metrics"""
        try:
            from sklearn.metrics import precision_score, recall_score, f1_score, classification_report
            
            metrics = {}
            
            metrics['accuracy'] = float(accuracy_score(y_true, y_pred))
            metrics['precision'] = float(precision_score(y_true, y_pred, average='weighted', zero_division=0))
            metrics['recall'] = float(recall_score(y_true, y_pred, average='weighted', zero_division=0))
            metrics['f1_score'] = float(f1_score(y_true, y_pred, average='weighted', zero_division=0))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate classification metrics: {e}")
            return {}
    
    async def evaluate_performance_degradation(self,
                                             current_metrics: Dict[str, float],
                                             baseline_metrics: Dict[str, float],
                                             model_type: str = 'regression') -> Dict[str, Any]:
        """Evaluate if model performance has degraded"""
        
        if model_type not in self.performance_thresholds:
            raise ValueError(f"Unknown model type: {model_type}")
        
        thresholds = self.performance_thresholds[model_type]
        
        evaluation = {
            'performance_degraded': False,
            'warning_triggered': False,
            'degraded_metrics': [],
            'warning_metrics': [],
            'metric_comparisons': {},
            'overall_score': 1.0,
            'evaluated_at': datetime.utcnow().isoformat()
        }
        
        for metric_name, metric_config in thresholds.items():
            if metric_name not in current_metrics:
                continue
            
            current_value = current_metrics[metric_name]
            baseline_value = baseline_metrics.get(metric_name)
            
            comparison = {
                'current': current_value,
                'baseline': baseline_value,
                'change': None,
                'change_percent': None,
                'status': 'ok'
            }
            
            if baseline_value is not None:
                comparison['change'] = current_value - baseline_value
                if baseline_value != 0:
                    comparison['change_percent'] = (comparison['change'] / baseline_value) * 100
            
            # Check thresholds
            if 'min' in metric_config:
                if current_value < metric_config['min']:
                    evaluation['performance_degraded'] = True
                    evaluation['degraded_metrics'].append(metric_name)
                    comparison['status'] = 'degraded'
                elif current_value < metric_config.get('warning', metric_config['min']):
                    evaluation['warning_triggered'] = True
                    evaluation['warning_metrics'].append(metric_name)
                    comparison['status'] = 'warning'
            
            if 'max' in metric_config:
                if current_value > metric_config['max']:
                    evaluation['performance_degraded'] = True
                    evaluation['degraded_metrics'].append(metric_name)
                    comparison['status'] = 'degraded'
                elif current_value > metric_config.get('warning', metric_config['max']):
                    evaluation['warning_triggered'] = True
                    evaluation['warning_metrics'].append(metric_name)
                    comparison['status'] = 'warning'
            
            evaluation['metric_comparisons'][metric_name] = comparison
        
        # Calculate overall performance score
        degraded_count = len(evaluation['degraded_metrics'])
        warning_count = len(evaluation['warning_metrics'])
        total_metrics = len(evaluation['metric_comparisons'])
        
        if total_metrics > 0:
            degradation_penalty = (degraded_count * 0.3 + warning_count * 0.1) / total_metrics
            evaluation['overall_score'] = max(0.0, 1.0 - degradation_penalty)
        
        return evaluation


class ModelMonitor:
    """Comprehensive model monitoring system"""
    
    def __init__(self, model_registry: ModelRegistry, redis_client: redis.Redis):
        self.model_registry = model_registry
        self.redis_client = redis_client
        self.drift_detector = DriftDetector()
        self.performance_monitor = PerformanceMonitor()
        
        # Monitoring configuration
        self.monitoring_config = {
            'drift_check_interval': timedelta(hours=6),
            'performance_check_interval': timedelta(hours=12),
            'data_retention_days': 30,
            'alert_thresholds': {
                'drift_score': 0.1,
                'performance_degradation': 0.15,
                'prediction_volume_change': 0.5  # 50% change in prediction volume
            }
        }
    
    async def monitor_model_health(self, model_name: str) -> Dict[str, Any]:
        """Comprehensive model health check"""
        health_report = {
            'model_name': model_name,
            'overall_health': 'healthy',
            'health_score': 1.0,
            'checks': {},
            'alerts': [],
            'recommendations': [],
            'monitored_at': datetime.utcnow().isoformat()
        }
        
        try:
            # Check 1: Model availability and basic health
            model_health = await self._check_model_availability(model_name)
            health_report['checks']['availability'] = model_health
            
            if not model_health['is_available']:
                health_report['overall_health'] = 'critical'
                health_report['health_score'] = 0.0
                health_report['alerts'].append({
                    'level': 'critical',
                    'message': f"Model {model_name} is not available",
                    'recommendation': 'Check model loading and dependencies'
                })
                return health_report
            
            # Check 2: Feature drift detection
            drift_check = await self._check_feature_drift(model_name)
            health_report['checks']['feature_drift'] = drift_check
            
            if drift_check.get('overall_drift_detected', False):
                health_report['health_score'] *= 0.7
                health_report['alerts'].append({
                    'level': 'warning',
                    'message': f"Feature drift detected in {len(drift_check.get('feature_drift', {}))} features",
                    'recommendation': 'Consider model retraining with recent data'
                })
            
            # Check 3: Prediction drift detection
            pred_drift_check = await self._check_prediction_drift(model_name)
            health_report['checks']['prediction_drift'] = pred_drift_check
            
            if pred_drift_check.get('drift_detected', False):
                health_report['health_score'] *= 0.8
                health_report['alerts'].append({
                    'level': 'warning',
                    'message': "Prediction drift detected",
                    'recommendation': 'Investigate changes in input data or model behavior'
                })
            
            # Check 4: Performance monitoring
            performance_check = await self._check_performance_degradation(model_name)
            health_report['checks']['performance'] = performance_check
            
            if performance_check.get('performance_degraded', False):
                health_report['health_score'] *= 0.5
                health_report['overall_health'] = 'degraded'
                health_report['alerts'].append({
                    'level': 'critical',
                    'message': f"Performance degraded in metrics: {performance_check.get('degraded_metrics', [])}",
                    'recommendation': 'Immediate model retraining required'
                })
            elif performance_check.get('warning_triggered', False):
                health_report['health_score'] *= 0.85
                health_report['alerts'].append({
                    'level': 'warning',
                    'message': f"Performance warnings in metrics: {performance_check.get('warning_metrics', [])}",
                    'recommendation': 'Schedule model retraining'
                })
            
            # Check 5: Prediction volume and patterns
            volume_check = await self._check_prediction_volume(model_name)
            health_report['checks']['prediction_volume'] = volume_check
            
            if volume_check.get('volume_change_significant', False):
                health_report['health_score'] *= 0.9
                health_report['alerts'].append({
                    'level': 'info',
                    'message': f"Prediction volume changed by {volume_check.get('volume_change_percent', 0):.1f}%",
                    'recommendation': 'Monitor for unexpected usage patterns'
                })
            
            # Determine overall health status
            if health_report['health_score'] >= 0.8:
                health_report['overall_health'] = 'healthy'
            elif health_report['health_score'] >= 0.6:
                health_report['overall_health'] = 'warning'
            elif health_report['health_score'] >= 0.3:
                health_report['overall_health'] = 'degraded'
            else:
                health_report['overall_health'] = 'critical'
            
            # Store monitoring results
            await self._store_monitoring_results(model_name, health_report)
            
            logger.info(
                "Model health check completed",
                model_name=model_name,
                overall_health=health_report['overall_health'],
                health_score=health_report['health_score'],
                alerts=len(health_report['alerts'])
            )
            
            return health_report
            
        except Exception as e:
            logger.error(f"Model health check failed: {e}", exc_info=True)
            health_report['overall_health'] = 'unknown'
            health_report['health_score'] = 0.0
            health_report['alerts'].append({
                'level': 'critical',
                'message': f"Health check failed: {str(e)}",
                'recommendation': 'Check monitoring system and model availability'
            })
            return health_report
    
    async def _check_model_availability(self, model_name: str) -> Dict[str, Any]:
        """Check if model is loaded and available"""
        try:
            model = await self.model_registry.get_model(model_name)
            metadata = await self.model_registry.get_model_metadata(model_name)
            
            return {
                'is_available': model is not None,
                'has_metadata': metadata is not None,
                'last_used': metadata.last_used.isoformat() if metadata else None,
                'prediction_count': metadata.prediction_count if metadata else 0,
                'model_version': metadata.version if metadata else None
            }
        except Exception as e:
            return {
                'is_available': False,
                'error': str(e)
            }
    
    async def _check_feature_drift(self, model_name: str) -> Dict[str, Any]:
        """Check for feature drift"""
        try:
            # Get reference data (baseline) and current data
            reference_data = await self._get_reference_data(model_name)
            current_data = await self._get_recent_data(model_name)
            
            if reference_data.empty or current_data.empty:
                return {
                    'drift_detected': False,
                    'message': 'Insufficient data for drift detection',
                    'reference_samples': len(reference_data),
                    'current_samples': len(current_data)
                }
            
            # Get model feature columns
            metadata = await self.model_registry.get_model_metadata(model_name)
            feature_columns = metadata.features if metadata else []
            
            if not feature_columns:
                return {
                    'drift_detected': False,
                    'message': 'No feature columns defined for model'
                }
            
            # Detect drift
            drift_results = await self.drift_detector.detect_feature_drift(
                reference_data, current_data, feature_columns, method='ks_test'
            )
            
            return drift_results
            
        except Exception as e:
            logger.error(f"Feature drift check failed: {e}")
            return {
                'drift_detected': False,
                'error': str(e)
            }
    
    async def _check_prediction_drift(self, model_name: str) -> Dict[str, Any]:
        """Check for prediction drift"""
        try:
            # Get historical predictions
            reference_predictions = await self._get_reference_predictions(model_name)
            current_predictions = await self._get_recent_predictions(model_name)
            
            if len(reference_predictions) == 0 or len(current_predictions) == 0:
                return {
                    'drift_detected': False,
                    'message': 'Insufficient prediction data for drift detection'
                }
            
            # Detect drift in predictions
            drift_results = await self.drift_detector.detect_prediction_drift(
                reference_predictions, current_predictions, method='ks_test'
            )
            
            return drift_results
            
        except Exception as e:
            logger.error(f"Prediction drift check failed: {e}")
            return {
                'drift_detected': False,
                'error': str(e)
            }
    
    async def _check_performance_degradation(self, model_name: str) -> Dict[str, Any]:
        """Check for model performance degradation"""
        try:
            # Get ground truth and predictions
            y_true, y_pred = await self._get_labeled_predictions(model_name)
            
            if len(y_true) == 0 or len(y_pred) == 0:
                return {
                    'performance_degraded': False,
                    'message': 'Insufficient labeled data for performance evaluation'
                }
            
            # Calculate current metrics
            current_metrics = await self.performance_monitor.calculate_regression_metrics(y_true, y_pred)
            
            # Get baseline metrics
            baseline_metrics = await self.model_registry.get_model_performance_metrics(model_name)
            
            if not baseline_metrics:
                return {
                    'performance_degraded': False,
                    'message': 'No baseline metrics available for comparison',
                    'current_metrics': current_metrics
                }
            
            # Evaluate degradation
            evaluation = await self.performance_monitor.evaluate_performance_degradation(
                current_metrics, baseline_metrics, model_type='regression'
            )
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Performance degradation check failed: {e}")
            return {
                'performance_degraded': False,
                'error': str(e)
            }
    
    async def _check_prediction_volume(self, model_name: str) -> Dict[str, Any]:
        """Check prediction volume patterns"""
        try:
            # Get prediction counts for last 24 hours vs previous 24 hours
            now = datetime.utcnow()
            recent_start = now - timedelta(hours=24)
            previous_start = now - timedelta(hours=48)
            
            recent_count = await self._get_prediction_count(model_name, recent_start, now)
            previous_count = await self._get_prediction_count(model_name, previous_start, recent_start)
            
            volume_change = 0
            volume_change_percent = 0
            
            if previous_count > 0:
                volume_change = recent_count - previous_count
                volume_change_percent = (volume_change / previous_count) * 100
            
            threshold = self.monitoring_config['alert_thresholds']['prediction_volume_change']
            volume_change_significant = abs(volume_change_percent) > (threshold * 100)
            
            return {
                'recent_count': recent_count,
                'previous_count': previous_count,
                'volume_change': volume_change,
                'volume_change_percent': volume_change_percent,
                'volume_change_significant': volume_change_significant,
                'threshold_percent': threshold * 100
            }
            
        except Exception as e:
            logger.error(f"Prediction volume check failed: {e}")
            return {
                'volume_change_significant': False,
                'error': str(e)
            }
    
    async def _get_reference_data(self, model_name: str, days_back: int = 30) -> pd.DataFrame:
        """Get reference data for drift detection"""
        # This would typically query your database for historical input data
        # For now, return empty DataFrame (implement based on your data storage)
        return pd.DataFrame()
    
    async def _get_recent_data(self, model_name: str, hours_back: int = 24) -> pd.DataFrame:
        """Get recent data for drift detection"""
        # This would typically query recent input data
        # For now, return empty DataFrame (implement based on your data storage)
        return pd.DataFrame()
    
    async def _get_reference_predictions(self, model_name: str, days_back: int = 30) -> np.ndarray:
        """Get reference predictions for drift detection"""
        # This would query historical predictions
        # For now, return empty array
        return np.array([])
    
    async def _get_recent_predictions(self, model_name: str, hours_back: int = 24) -> np.ndarray:
        """Get recent predictions for drift detection"""
        # This would query recent predictions
        # For now, return empty array
        return np.array([])
    
    async def _get_labeled_predictions(self, model_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """Get predictions with ground truth labels"""
        # This would query predictions that have been validated with actual outcomes
        # For now, return empty arrays
        return np.array([]), np.array([])
    
    async def _get_prediction_count(self, 
                                  model_name: str, 
                                  start_time: datetime, 
                                  end_time: datetime) -> int:
        """Get prediction count for time period"""
        try:
            # This would query your prediction logs
            # For now, return a placeholder count
            cache_key = f"prediction_count:{model_name}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_count = await self.redis_client.get(cache_key)
            
            if cached_count:
                return int(cached_count)
            
            # Placeholder implementation
            # In production, query your prediction logs database
            count = np.random.randint(50, 200)  # Random count for demonstration
            
            # Cache for 1 hour
            await self.redis_client.setex(cache_key, 3600, str(count))
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to get prediction count: {e}")
            return 0
    
    async def _store_monitoring_results(self, model_name: str, health_report: Dict[str, Any]):
        """Store monitoring results for historical analysis"""
        try:
            # Store in Redis with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            key = f"monitoring:{model_name}:{timestamp}"
            
            await self.redis_client.setex(
                key,
                self.monitoring_config['data_retention_days'] * 24 * 3600,  # Convert to seconds
                json.dumps(health_report, default=str)
            )
            
            # Also store latest result
            latest_key = f"monitoring:latest:{model_name}"
            await self.redis_client.setex(
                latest_key,
                24 * 3600,  # 24 hours
                json.dumps(health_report, default=str)
            )
            
        except Exception as e:
            logger.error(f"Failed to store monitoring results: {e}")
    
    async def get_monitoring_history(self, 
                                   model_name: str, 
                                   hours_back: int = 168) -> List[Dict[str, Any]]:
        """Get monitoring history for a model"""
        try:
            # Get monitoring keys for the specified time period
            pattern = f"monitoring:{model_name}:*"
            keys = await self.redis_client.keys(pattern)
            
            history = []
            for key in keys:
                data = await self.redis_client.get(key)
                if data:
                    monitoring_result = json.loads(data)
                    history.append(monitoring_result)
            
            # Sort by timestamp
            history.sort(key=lambda x: x.get('monitored_at', ''), reverse=True)
            
            return history[:100]  # Limit to last 100 results
            
        except Exception as e:
            logger.error(f"Failed to get monitoring history: {e}")
            return []
    
    async def create_monitoring_alert(self, 
                                    model_name: str, 
                                    alert_level: str, 
                                    message: str,
                                    metadata: Optional[Dict[str, Any]] = None):
        """Create and store monitoring alert"""
        try:
            alert = {
                'model_name': model_name,
                'level': alert_level,
                'message': message,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat(),
                'acknowledged': False
            }
            
            # Store alert
            alert_key = f"alert:{model_name}:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await self.redis_client.setex(alert_key, 7 * 24 * 3600, json.dumps(alert))  # 7 days
            
            # Add to alerts list
            alerts_list_key = f"alerts:{model_name}"
            await self.redis_client.lpush(alerts_list_key, json.dumps(alert))
            await self.redis_client.ltrim(alerts_list_key, 0, 99)  # Keep last 100 alerts
            
            logger.info(
                "Monitoring alert created",
                model_name=model_name,
                level=alert_level,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Failed to create monitoring alert: {e}")
    
    async def get_active_alerts(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active monitoring alerts"""
        try:
            if model_name:
                alerts_key = f"alerts:{model_name}"
                alerts_data = await self.redis_client.lrange(alerts_key, 0, -1)
            else:
                # Get alerts for all models
                pattern = "alerts:*"
                keys = await self.redis_client.keys(pattern)
                alerts_data = []
                
                for key in keys:
                    key_alerts = await self.redis_client.lrange(key, 0, -1)
                    alerts_data.extend(key_alerts)
            
            alerts = []
            for alert_json in alerts_data:
                try:
                    alert = json.loads(alert_json)
                    if not alert.get('acknowledged', False):
                        alerts.append(alert)
                except json.JSONDecodeError:
                    continue
            
            # Sort by creation time
            alerts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
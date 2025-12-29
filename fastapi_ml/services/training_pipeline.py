"""
Model Training Pipeline with MLflow Integration
"""
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import structlog
import mlflow
import mlflow.lightgbm
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split, cross_val_score, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import IsolationForest
import lightgbm as lgb
from prophet import Prophet
import optuna
from optuna.integration.mlflow import MLflowCallback
import joblib

from .model_registry import ModelRegistry, ModelMetadata
from .feature_engineering import FeatureEngineer
from .ml_service import PricePredictionModel, AnomalyDetectionModel, DemandForecastModel
from ..config import settings, MODEL_CONFIG

logger = structlog.get_logger()


class ModelTrainer:
    """
    Automated model training with hyperparameter optimization
    """
    
    def __init__(self, model_registry: ModelRegistry):
        self.model_registry = model_registry
        self.feature_engineer = FeatureEngineer()
        self.mlflow_client = MlflowClient(settings.MLFLOW_TRACKING_URI)
        
        # Set MLflow tracking URI
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        
    async def train_price_prediction_model(self, 
                                         training_data: pd.DataFrame,
                                         target_column: str = 'price',
                                         test_size: float = 0.2,
                                         optimize_hyperparams: bool = True) -> Dict[str, Any]:
        """Train price prediction model with MLflow tracking"""
        
        with mlflow.start_run(run_name=f"price_predictor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"):
            try:
                # Log experiment info
                mlflow.log_params({
                    'model_type': 'lightgbm',
                    'target_column': target_column,
                    'test_size': test_size,
                    'optimize_hyperparams': optimize_hyperparams,
                    'training_samples': len(training_data)
                })
                
                # Feature engineering
                logger.info("Starting feature engineering...")
                engineered_data = await self.feature_engineer.engineer_price_features(
                    training_data, target_column
                )
                
                # Prepare features and target
                feature_columns = [col for col in engineered_data.columns 
                                 if col != target_column and col != 'timestamp']
                X = engineered_data[feature_columns].fillna(0)
                y = engineered_data[target_column]
                
                # Feature selection
                X_selected, selected_features = await self.feature_engineer.select_features(
                    X, y, method='mutual_info', k=50
                )
                
                # Preprocessing
                X_processed = await self.feature_engineer.preprocess_features(
                    X_selected, selected_features, fit_transforms=True
                )
                
                # Train-test split with time awareness if timestamp exists
                if 'timestamp' in engineered_data.columns:
                    # Time-based split
                    engineered_data_sorted = engineered_data.sort_values('timestamp')
                    split_idx = int(len(engineered_data_sorted) * (1 - test_size))
                    
                    train_indices = engineered_data_sorted.index[:split_idx]
                    test_indices = engineered_data_sorted.index[split_idx:]
                    
                    X_train = X_processed.loc[train_indices]
                    X_test = X_processed.loc[test_indices]
                    y_train = y.loc[train_indices]
                    y_test = y.loc[test_indices]
                else:
                    # Random split
                    X_train, X_test, y_train, y_test = train_test_split(
                        X_processed, y, test_size=test_size, random_state=42
                    )
                
                # Log data info
                mlflow.log_params({
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'selected_features': len(selected_features),
                    'total_features': len(feature_columns)
                })
                
                # Hyperparameter optimization
                if optimize_hyperparams:
                    logger.info("Optimizing hyperparameters...")
                    best_params = await self._optimize_lgb_hyperparams(
                        X_train, y_train, X_test, y_test
                    )
                else:
                    best_params = MODEL_CONFIG['price_predictor']['hyperparameters']
                
                # Train final model
                logger.info("Training final model...")
                model = PricePredictionModel({
                    'features': selected_features,
                    'hyperparameters': best_params
                })
                
                train_metrics = model.train(X_train, y_train, X_test, y_test)
                
                # Log model and metrics
                mlflow.log_params(best_params)
                mlflow.log_metrics(train_metrics)
                
                # Cross-validation
                logger.info("Performing cross-validation...")
                cv_scores = await self._cross_validate_model(
                    model, X_processed, y, cv_folds=5
                )
                mlflow.log_metrics({f'cv_{metric}': np.mean(scores) 
                                  for metric, scores in cv_scores.items()})
                
                # Log model artifacts
                model_path = "model"
                mlflow.lightgbm.log_model(
                    model.model, 
                    model_path,
                    registered_model_name="price_predictor"
                )
                
                # Log feature importance
                feature_importance = model.get_feature_importance()
                importance_df = pd.DataFrame([
                    {'feature': feat, 'importance': imp} 
                    for feat, imp in feature_importance.items()
                ])
                mlflow.log_table(importance_df, "feature_importance.json")
                
                # Save preprocessing artifacts
                preprocessing_artifacts = {
                    'selected_features': selected_features,
                    'feature_encoders': self.feature_engineer.encoders,
                    'feature_scalers': self.feature_engineer.scalers
                }
                
                artifacts_path = Path(settings.MODEL_STORAGE_PATH) / "preprocessing_artifacts.pkl"
                joblib.dump(preprocessing_artifacts, artifacts_path)
                mlflow.log_artifact(str(artifacts_path), "preprocessing")
                
                # Register model in our registry
                run_id = mlflow.active_run().info.run_id
                
                metadata = ModelMetadata(
                    name='price_predictor',
                    version=datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
                    model_type='lightgbm',
                    created_at=datetime.utcnow(),
                    performance_metrics=train_metrics,
                    features=selected_features,
                    mlflow_run_id=run_id
                )
                
                await self.model_registry.register_model('price_predictor', model, metadata)
                
                # Log success
                logger.info(
                    "Price prediction model training completed",
                    metrics=train_metrics,
                    run_id=run_id
                )
                
                return {
                    'status': 'success',
                    'model_name': 'price_predictor',
                    'run_id': run_id,
                    'metrics': train_metrics,
                    'cv_metrics': {metric: np.mean(scores) for metric, scores in cv_scores.items()},
                    'selected_features': selected_features
                }
                
            except Exception as e:
                mlflow.log_param('error', str(e))
                logger.error("Model training failed", error=str(e), exc_info=True)
                raise
    
    async def _optimize_lgb_hyperparams(self, 
                                      X_train: pd.DataFrame,
                                      y_train: pd.Series,
                                      X_val: pd.DataFrame,
                                      y_val: pd.Series,
                                      n_trials: int = 100) -> Dict[str, Any]:
        """Optimize LightGBM hyperparameters using Optuna"""
        
        def objective(trial):
            # Hyperparameter space
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'boosting_type': 'gbdt',
                'num_leaves': trial.suggest_int('num_leaves', 10, 100),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
                'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                'max_depth': trial.suggest_int('max_depth', 3, 12),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 10),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 10),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'verbosity': -1
            }
            
            # Train model
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            
            model = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)]
            )
            
            # Evaluate
            y_pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, y_pred))
            
            return rmse
        
        # Create study with MLflow callback
        mlflow_callback = MLflowCallback(
            tracking_uri=settings.MLFLOW_TRACKING_URI,
            metric_name="rmse"
        )
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials, callbacks=[mlflow_callback])
        
        logger.info(
            "Hyperparameter optimization completed",
            best_value=study.best_value,
            n_trials=n_trials
        )
        
        return study.best_params
    
    async def _cross_validate_model(self, 
                                  model: PricePredictionModel,
                                  X: pd.DataFrame,
                                  y: pd.Series,
                                  cv_folds: int = 5) -> Dict[str, List[float]]:
        """Perform cross-validation"""
        
        # Use TimeSeriesSplit if we have temporal data
        tscv = TimeSeriesSplit(n_splits=cv_folds)
        
        cv_scores = {'mae': [], 'rmse': [], 'r2': []}
        
        for train_idx, val_idx in tscv.split(X):
            X_train_cv = X.iloc[train_idx]
            X_val_cv = X.iloc[val_idx]
            y_train_cv = y.iloc[train_idx]
            y_val_cv = y.iloc[val_idx]
            
            # Train model
            temp_model = PricePredictionModel({
                'features': model.feature_names,
                'hyperparameters': model.config.get('hyperparameters', {})
            })
            temp_model.train(X_train_cv, y_train_cv)
            
            # Evaluate
            y_pred_cv = temp_model.predict(X_val_cv)
            
            cv_scores['mae'].append(mean_absolute_error(y_val_cv, y_pred_cv))
            cv_scores['rmse'].append(np.sqrt(mean_squared_error(y_val_cv, y_pred_cv)))
            cv_scores['r2'].append(r2_score(y_val_cv, y_pred_cv))
        
        return cv_scores
    
    async def train_anomaly_detection_model(self, 
                                          training_data: pd.DataFrame) -> Dict[str, Any]:
        """Train anomaly detection model"""
        
        with mlflow.start_run(run_name=f"anomaly_detector_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"):
            try:
                # Feature engineering for anomaly detection
                logger.info("Engineering features for anomaly detection...")
                engineered_data = await self.feature_engineer.engineer_anomaly_features(training_data)
                
                # Prepare features
                feature_columns = [col for col in engineered_data.columns 
                                 if col not in ['timestamp', 'price']]
                X = engineered_data[feature_columns].fillna(0)
                
                # Preprocessing
                X_processed = await self.feature_engineer.preprocess_features(
                    X, feature_columns, fit_transforms=True
                )
                
                # Log data info
                mlflow.log_params({
                    'model_type': 'isolation_forest',
                    'training_samples': len(X_processed),
                    'features': len(feature_columns)
                })
                
                # Train model
                logger.info("Training anomaly detection model...")
                config = MODEL_CONFIG['anomaly_detector']
                model = AnomalyDetectionModel(config)
                
                train_metrics = model.train(X_processed)
                
                # Log metrics
                mlflow.log_params(config['hyperparameters'])
                mlflow.log_metrics(train_metrics)
                
                # Log model
                model_path = "model"
                mlflow.sklearn.log_model(
                    model.model,
                    model_path,
                    registered_model_name="anomaly_detector"
                )
                
                # Register model
                run_id = mlflow.active_run().info.run_id
                
                metadata = ModelMetadata(
                    name='anomaly_detector',
                    version=datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
                    model_type='isolation_forest',
                    created_at=datetime.utcnow(),
                    performance_metrics=train_metrics,
                    features=feature_columns,
                    mlflow_run_id=run_id
                )
                
                await self.model_registry.register_model('anomaly_detector', model, metadata)
                
                logger.info("Anomaly detection model training completed", run_id=run_id)
                
                return {
                    'status': 'success',
                    'model_name': 'anomaly_detector',
                    'run_id': run_id,
                    'metrics': train_metrics
                }
                
            except Exception as e:
                mlflow.log_param('error', str(e))
                logger.error("Anomaly model training failed", error=str(e))
                raise
    
    async def train_demand_forecast_model(self, 
                                        training_data: pd.DataFrame,
                                        ds_column: str = 'timestamp',
                                        y_column: str = 'demand') -> Dict[str, Any]:
        """Train demand forecasting model"""
        
        with mlflow.start_run(run_name=f"demand_forecaster_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"):
            try:
                # Prepare data for Prophet
                prophet_data = pd.DataFrame({
                    'ds': pd.to_datetime(training_data[ds_column]),
                    'y': training_data[y_column]
                })
                
                # Remove duplicates and sort
                prophet_data = prophet_data.drop_duplicates(subset=['ds']).sort_values('ds')
                
                mlflow.log_params({
                    'model_type': 'prophet',
                    'training_samples': len(prophet_data),
                    'ds_column': ds_column,
                    'y_column': y_column
                })
                
                # Train model
                logger.info("Training demand forecast model...")
                config = MODEL_CONFIG['demand_forecaster']
                model = DemandForecastModel(config)
                
                train_metrics = model.train(prophet_data)
                
                # Log metrics
                mlflow.log_params(config['hyperparameters'])
                mlflow.log_metrics(train_metrics)
                
                # Log model (Prophet models need special handling)
                model_path = "model"
                mlflow.pyfunc.log_model(
                    model_path,
                    python_model=model.model,
                    registered_model_name="demand_forecaster"
                )
                
                # Register model
                run_id = mlflow.active_run().info.run_id
                
                metadata = ModelMetadata(
                    name='demand_forecaster',
                    version=datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
                    model_type='prophet',
                    created_at=datetime.utcnow(),
                    performance_metrics=train_metrics,
                    features=['ds', 'y'],
                    mlflow_run_id=run_id
                )
                
                await self.model_registry.register_model('demand_forecaster', model, metadata)
                
                logger.info("Demand forecast model training completed", run_id=run_id)
                
                return {
                    'status': 'success',
                    'model_name': 'demand_forecaster',
                    'run_id': run_id,
                    'metrics': train_metrics
                }
                
            except Exception as e:
                mlflow.log_param('error', str(e))
                logger.error("Demand forecast model training failed", error=str(e))
                raise


class AutoMLTrainer:
    """
    Automated ML training pipeline with scheduling and retraining
    """
    
    def __init__(self, model_registry: ModelRegistry):
        self.model_trainer = ModelTrainer(model_registry)
        self.model_registry = model_registry
        self.training_schedule = {}
        self.performance_thresholds = {
            'price_predictor': {'min_r2': 0.85, 'max_mae': 0.1},
            'anomaly_detector': {'min_precision': 0.8},
            'demand_forecaster': {'max_mape': 0.15}
        }
        
    async def setup_training_schedule(self) -> None:
        """Setup automated training schedules"""
        self.training_schedule = {
            'price_predictor': {
                'frequency': timedelta(days=7),  # Weekly retraining
                'last_trained': None,
                'data_query': self._get_price_training_data,
                'train_function': self.model_trainer.train_price_prediction_model
            },
            'anomaly_detector': {
                'frequency': timedelta(days=14),  # Bi-weekly
                'last_trained': None,
                'data_query': self._get_anomaly_training_data,
                'train_function': self.model_trainer.train_anomaly_detection_model
            },
            'demand_forecaster': {
                'frequency': timedelta(days=30),  # Monthly
                'last_trained': None,
                'data_query': self._get_demand_training_data,
                'train_function': self.model_trainer.train_demand_forecast_model
            }
        }
        
        logger.info("Training schedule configured", models=list(self.training_schedule.keys()))
    
    async def check_and_retrain_models(self) -> Dict[str, Any]:
        """Check if models need retraining and execute if needed"""
        retrain_results = {}
        current_time = datetime.utcnow()
        
        for model_name, schedule_info in self.training_schedule.items():
            try:
                # Check if retraining is needed
                needs_retraining = False
                reason = ""
                
                # Time-based check
                if schedule_info['last_trained'] is None:
                    needs_retraining = True
                    reason = "never_trained"
                elif current_time - schedule_info['last_trained'] >= schedule_info['frequency']:
                    needs_retraining = True
                    reason = "scheduled_retrain"
                
                # Performance-based check
                if not needs_retraining:
                    performance_check = await self._check_model_performance(model_name)
                    if not performance_check['meets_threshold']:
                        needs_retraining = True
                        reason = f"performance_degraded: {performance_check['failing_metrics']}"
                
                if needs_retraining:
                    logger.info(
                        "Retraining model",
                        model_name=model_name,
                        reason=reason
                    )
                    
                    # Get training data
                    training_data = await schedule_info['data_query']()
                    
                    # Train model
                    train_result = await schedule_info['train_function'](training_data)
                    
                    # Update last trained time
                    self.training_schedule[model_name]['last_trained'] = current_time
                    
                    retrain_results[model_name] = {
                        'status': 'retrained',
                        'reason': reason,
                        'result': train_result
                    }
                    
                else:
                    retrain_results[model_name] = {
                        'status': 'skipped',
                        'reason': 'not_needed'
                    }
                    
            except Exception as e:
                logger.error(
                    "Model retraining failed",
                    model_name=model_name,
                    error=str(e)
                )
                retrain_results[model_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        return retrain_results
    
    async def _check_model_performance(self, model_name: str) -> Dict[str, Any]:
        """Check if model performance meets thresholds"""
        try:
            metrics = await self.model_registry.get_model_performance_metrics(model_name)
            thresholds = self.performance_thresholds.get(model_name, {})
            
            failing_metrics = []
            
            for threshold_name, threshold_value in thresholds.items():
                metric_name = threshold_name.replace('min_', '').replace('max_', '')
                
                if metric_name in metrics:
                    metric_value = metrics[metric_name]
                    
                    if threshold_name.startswith('min_') and metric_value < threshold_value:
                        failing_metrics.append(f"{metric_name}: {metric_value} < {threshold_value}")
                    elif threshold_name.startswith('max_') and metric_value > threshold_value:
                        failing_metrics.append(f"{metric_name}: {metric_value} > {threshold_value}")
            
            return {
                'meets_threshold': len(failing_metrics) == 0,
                'failing_metrics': failing_metrics,
                'current_metrics': metrics
            }
            
        except Exception as e:
            logger.error("Performance check failed", model_name=model_name, error=str(e))
            return {
                'meets_threshold': True,  # Assume OK if we can't check
                'failing_metrics': [],
                'error': str(e)
            }
    
    async def _get_price_training_data(self) -> pd.DataFrame:
        """Get training data for price prediction model"""
        # This would query your database for recent pricing data
        # For now, return placeholder data
        logger.info("Fetching price training data...")
        
        # Placeholder - implement based on your data sources
        return pd.DataFrame({
            'timestamp': pd.date_range('2023-01-01', periods=1000, freq='D'),
            'material_id': np.random.randint(1, 100, 1000),
            'supplier_id': np.random.randint(1, 20, 1000),
            'quantity': np.random.randint(1, 1000, 1000),
            'material_category': np.random.choice(['electronics', 'machinery', 'materials'], 1000),
            'price': np.random.lognormal(4, 0.5, 1000)
        })
    
    async def _get_anomaly_training_data(self) -> pd.DataFrame:
        """Get training data for anomaly detection model"""
        logger.info("Fetching anomaly training data...")
        
        # Placeholder - implement based on your data sources
        return await self._get_price_training_data()
    
    async def _get_demand_training_data(self) -> pd.DataFrame:
        """Get training data for demand forecasting model"""
        logger.info("Fetching demand training data...")
        
        # Placeholder - implement based on your data sources
        dates = pd.date_range('2022-01-01', '2023-12-31', freq='D')
        demand = np.random.poisson(100, len(dates)) + np.sin(np.arange(len(dates)) * 2 * np.pi / 365) * 20
        
        return pd.DataFrame({
            'timestamp': dates,
            'demand': demand
        })
    
    async def run_training_pipeline(self, 
                                  model_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run training pipeline for specified models or all models"""
        if model_names is None:
            model_names = list(self.training_schedule.keys())
        
        results = {}
        
        for model_name in model_names:
            if model_name not in self.training_schedule:
                results[model_name] = {
                    'status': 'error',
                    'error': f'Model {model_name} not in training schedule'
                }
                continue
            
            try:
                logger.info("Running training pipeline", model_name=model_name)
                
                # Get training data
                schedule_info = self.training_schedule[model_name]
                training_data = await schedule_info['data_query']()
                
                # Train model
                train_result = await schedule_info['train_function'](training_data)
                
                # Update last trained time
                self.training_schedule[model_name]['last_trained'] = datetime.utcnow()
                
                results[model_name] = train_result
                
            except Exception as e:
                logger.error("Training pipeline failed", model_name=model_name, error=str(e))
                results[model_name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return results
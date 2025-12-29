"""
ML model validation and testing framework.
"""
import pytest
import numpy as np
import pandas as pd
import joblib
import json
from typing import Dict, List, Any, Tuple, Optional
from unittest.mock import Mock, patch
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
import lightgbm as lgb
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class ModelTestResult:
    """Result of a model test."""
    test_name: str
    model_name: str
    status: str  # 'pass', 'fail', 'warning'
    score: float
    threshold: float
    details: Dict[str, Any]
    message: str


class MLModelTester:
    """Framework for testing ML models."""
    
    def __init__(self, model_path: str = None, model_object: Any = None):
        self.model_path = model_path
        self.model = model_object
        self.test_results = []
        
        if model_path and not model_object:
            self.load_model()
    
    def load_model(self):
        """Load model from file."""
        try:
            if self.model_path.endswith('.pkl'):
                self.model = joblib.load(self.model_path)
            elif self.model_path.endswith('.json'):
                # For LightGBM models
                self.model = lgb.Booster(model_file=self.model_path)
            else:
                raise ValueError(f"Unsupported model format: {self.model_path}")
        except Exception as e:
            raise ValueError(f"Failed to load model: {e}")
    
    def test_model_performance(self, X_test: pd.DataFrame, y_test: pd.Series, 
                             thresholds: Dict[str, float] = None) -> List[ModelTestResult]:
        """Test model performance metrics."""
        if thresholds is None:
            thresholds = {
                'mae': 50.0,  # Maximum acceptable MAE
                'rmse': 75.0,  # Maximum acceptable RMSE
                'r2': 0.7,    # Minimum acceptable R²
                'mape': 0.15  # Maximum acceptable MAPE (15%)
            }
        
        results = []
        
        # Make predictions
        try:
            if hasattr(self.model, 'predict'):
                y_pred = self.model.predict(X_test)
            else:
                # For LightGBM Booster
                y_pred = self.model.predict(X_test)
        except Exception as e:
            results.append(ModelTestResult(
                test_name="Prediction Generation",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=0.0,
                threshold=0.0,
                details={"error": str(e)},
                message=f"Failed to generate predictions: {e}"
            ))
            return results
        
        # Calculate metrics
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test, y_pred)
        
        # Calculate MAPE (Mean Absolute Percentage Error)
        mape = np.mean(np.abs((y_test - y_pred) / y_test))
        
        # Test MAE
        results.append(ModelTestResult(
            test_name="Mean Absolute Error",
            model_name=str(type(self.model).__name__),
            status="pass" if mae <= thresholds['mae'] else "fail",
            score=mae,
            threshold=thresholds['mae'],
            details={"mae": mae},
            message=f"MAE: {mae:.2f} (threshold: {thresholds['mae']})"
        ))
        
        # Test RMSE
        results.append(ModelTestResult(
            test_name="Root Mean Square Error",
            model_name=str(type(self.model).__name__),
            status="pass" if rmse <= thresholds['rmse'] else "fail",
            score=rmse,
            threshold=thresholds['rmse'],
            details={"rmse": rmse},
            message=f"RMSE: {rmse:.2f} (threshold: {thresholds['rmse']})"
        ))
        
        # Test R²
        results.append(ModelTestResult(
            test_name="R-squared Score",
            model_name=str(type(self.model).__name__),
            status="pass" if r2 >= thresholds['r2'] else "fail",
            score=r2,
            threshold=thresholds['r2'],
            details={"r2": r2},
            message=f"R²: {r2:.3f} (threshold: {thresholds['r2']})"
        ))
        
        # Test MAPE
        results.append(ModelTestResult(
            test_name="Mean Absolute Percentage Error",
            model_name=str(type(self.model).__name__),
            status="pass" if mape <= thresholds['mape'] else "fail",
            score=mape,
            threshold=thresholds['mape'],
            details={"mape": mape},
            message=f"MAPE: {mape:.3f} (threshold: {thresholds['mape']})"
        ))
        
        return results
    
    def test_prediction_consistency(self, X_test: pd.DataFrame, n_runs: int = 5) -> ModelTestResult:
        """Test prediction consistency across multiple runs."""
        predictions = []
        
        for _ in range(n_runs):
            if hasattr(self.model, 'predict'):
                pred = self.model.predict(X_test)
            else:
                pred = self.model.predict(X_test)
            predictions.append(pred)
        
        # Calculate variance across runs
        predictions_array = np.array(predictions)
        variance = np.var(predictions_array, axis=0)
        max_variance = np.max(variance)
        mean_variance = np.mean(variance)
        
        # Threshold: predictions should be consistent (low variance)
        threshold = 1.0  # Maximum acceptable variance
        
        return ModelTestResult(
            test_name="Prediction Consistency",
            model_name=str(type(self.model).__name__),
            status="pass" if max_variance <= threshold else "fail",
            score=max_variance,
            threshold=threshold,
            details={
                "max_variance": max_variance,
                "mean_variance": mean_variance,
                "std_variance": np.std(variance)
            },
            message=f"Max prediction variance: {max_variance:.4f} (threshold: {threshold})"
        )
    
    def test_feature_importance_stability(self, X_train: pd.DataFrame, y_train: pd.Series, 
                                        n_bootstraps: int = 10) -> ModelTestResult:
        """Test stability of feature importances."""
        if not hasattr(self.model, 'feature_importances_'):
            return ModelTestResult(
                test_name="Feature Importance Stability",
                model_name=str(type(self.model).__name__),
                status="warning",
                score=0.0,
                threshold=0.0,
                details={},
                message="Model does not support feature importance"
            )
        
        importance_scores = []
        
        for _ in range(n_bootstraps):
            # Bootstrap sample
            X_boot, y_boot = self._bootstrap_sample(X_train, y_train)
            
            # Train model on bootstrap sample
            model_copy = self._create_model_copy()
            model_copy.fit(X_boot, y_boot)
            
            if hasattr(model_copy, 'feature_importances_'):
                importance_scores.append(model_copy.feature_importances_)
        
        if not importance_scores:
            return ModelTestResult(
                test_name="Feature Importance Stability",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=0.0,
                threshold=0.0,
                details={},
                message="Could not calculate feature importances"
            )
        
        # Calculate stability metrics
        importance_array = np.array(importance_scores)
        importance_std = np.std(importance_array, axis=0)
        importance_mean = np.mean(importance_array, axis=0)
        
        # Coefficient of variation for each feature
        cv = importance_std / (importance_mean + 1e-8)
        max_cv = np.max(cv)
        
        # Threshold: feature importances should be stable (low CV)
        threshold = 0.3  # Maximum acceptable coefficient of variation
        
        return ModelTestResult(
            test_name="Feature Importance Stability",
            model_name=str(type(self.model).__name__),
            status="pass" if max_cv <= threshold else "fail",
            score=max_cv,
            threshold=threshold,
            details={
                "max_cv": max_cv,
                "mean_cv": np.mean(cv),
                "feature_cv": dict(zip(X_train.columns, cv))
            },
            message=f"Max feature importance CV: {max_cv:.3f} (threshold: {threshold})"
        )
    
    def test_prediction_bounds(self, X_test: pd.DataFrame, 
                             expected_range: Tuple[float, float] = (0, 10000)) -> ModelTestResult:
        """Test that predictions fall within expected bounds."""
        try:
            if hasattr(self.model, 'predict'):
                predictions = self.model.predict(X_test)
            else:
                predictions = self.model.predict(X_test)
        except Exception as e:
            return ModelTestResult(
                test_name="Prediction Bounds",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=0.0,
                threshold=0.0,
                details={"error": str(e)},
                message=f"Failed to generate predictions: {e}"
            )
        
        min_pred = np.min(predictions)
        max_pred = np.max(predictions)
        
        # Check bounds
        within_bounds = (min_pred >= expected_range[0] and max_pred <= expected_range[1])
        
        # Count outliers
        outliers = np.sum((predictions < expected_range[0]) | (predictions > expected_range[1]))
        outlier_percentage = outliers / len(predictions)
        
        return ModelTestResult(
            test_name="Prediction Bounds",
            model_name=str(type(self.model).__name__),
            status="pass" if within_bounds and outlier_percentage <= 0.01 else "fail",
            score=outlier_percentage,
            threshold=0.01,
            details={
                "min_prediction": min_pred,
                "max_prediction": max_pred,
                "expected_range": expected_range,
                "outliers": int(outliers),
                "outlier_percentage": outlier_percentage
            },
            message=f"Predictions range: [{min_pred:.2f}, {max_pred:.2f}], outliers: {outlier_percentage:.2%}"
        )
    
    def test_input_validation(self, X_test: pd.DataFrame) -> List[ModelTestResult]:
        """Test model behavior with invalid inputs."""
        results = []
        
        # Test with missing values
        X_missing = X_test.copy()
        X_missing.iloc[0, 0] = np.nan
        
        try:
            if hasattr(self.model, 'predict'):
                pred_missing = self.model.predict(X_missing)
            else:
                pred_missing = self.model.predict(X_missing)
            
            # Check if predictions contain NaN
            has_nan = np.any(np.isnan(pred_missing))
            
            results.append(ModelTestResult(
                test_name="Missing Value Handling",
                model_name=str(type(self.model).__name__),
                status="pass" if not has_nan else "fail",
                score=float(has_nan),
                threshold=0.0,
                details={"predictions_with_nan": int(np.sum(np.isnan(pred_missing)))},
                message=f"Model {'handles' if not has_nan else 'fails with'} missing values"
            ))
        
        except Exception as e:
            results.append(ModelTestResult(
                test_name="Missing Value Handling",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=1.0,
                threshold=0.0,
                details={"error": str(e)},
                message=f"Model fails with missing values: {e}"
            ))
        
        # Test with extreme values
        X_extreme = X_test.copy()
        numeric_cols = X_extreme.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) > 0:
            X_extreme[numeric_cols[0]] = 999999  # Extreme value
            
            try:
                if hasattr(self.model, 'predict'):
                    pred_extreme = self.model.predict(X_extreme)
                else:
                    pred_extreme = self.model.predict(X_extreme)
                
                # Check for unrealistic predictions
                unrealistic = np.any((pred_extreme < 0) | (pred_extreme > 1000000))
                
                results.append(ModelTestResult(
                    test_name="Extreme Value Handling",
                    model_name=str(type(self.model).__name__),
                    status="pass" if not unrealistic else "warning",
                    score=float(unrealistic),
                    threshold=0.0,
                    details={
                        "extreme_predictions": pred_extreme.tolist() if len(pred_extreme) <= 10 else "too_many"
                    },
                    message=f"Model {'handles' if not unrealistic else 'produces unrealistic predictions for'} extreme values"
                ))
            
            except Exception as e:
                results.append(ModelTestResult(
                    test_name="Extreme Value Handling",
                    model_name=str(type(self.model).__name__),
                    status="fail",
                    score=1.0,
                    threshold=0.0,
                    details={"error": str(e)},
                    message=f"Model fails with extreme values: {e}"
                ))
        
        return results
    
    def test_model_fairness(self, X_test: pd.DataFrame, y_test: pd.Series,
                          sensitive_feature: str) -> ModelTestResult:
        """Test model fairness across different groups."""
        if sensitive_feature not in X_test.columns:
            return ModelTestResult(
                test_name="Model Fairness",
                model_name=str(type(self.model).__name__),
                status="warning",
                score=0.0,
                threshold=0.0,
                details={},
                message=f"Sensitive feature '{sensitive_feature}' not found in data"
            )
        
        try:
            if hasattr(self.model, 'predict'):
                predictions = self.model.predict(X_test)
            else:
                predictions = self.model.predict(X_test)
        except Exception as e:
            return ModelTestResult(
                test_name="Model Fairness",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=0.0,
                threshold=0.0,
                details={"error": str(e)},
                message=f"Failed to generate predictions: {e}"
            )
        
        # Calculate performance by group
        unique_groups = X_test[sensitive_feature].unique()
        group_performance = {}
        
        for group in unique_groups:
            mask = X_test[sensitive_feature] == group
            if np.sum(mask) > 0:
                group_mae = mean_absolute_error(y_test[mask], predictions[mask])
                group_performance[str(group)] = group_mae
        
        if len(group_performance) < 2:
            return ModelTestResult(
                test_name="Model Fairness",
                model_name=str(type(self.model).__name__),
                status="warning",
                score=0.0,
                threshold=0.0,
                details=group_performance,
                message="Not enough groups to assess fairness"
            )
        
        # Calculate fairness metric (difference in MAE between groups)
        mae_values = list(group_performance.values())
        fairness_gap = max(mae_values) - min(mae_values)
        
        # Threshold: fairness gap should be small
        threshold = 10.0  # Maximum acceptable difference in MAE
        
        return ModelTestResult(
            test_name="Model Fairness",
            model_name=str(type(self.model).__name__),
            status="pass" if fairness_gap <= threshold else "fail",
            score=fairness_gap,
            threshold=threshold,
            details={
                "group_performance": group_performance,
                "fairness_gap": fairness_gap
            },
            message=f"Fairness gap (MAE difference): {fairness_gap:.2f} (threshold: {threshold})"
        )
    
    def test_model_drift(self, X_reference: pd.DataFrame, X_current: pd.DataFrame,
                        drift_threshold: float = 0.1) -> ModelTestResult:
        """Test for model drift by comparing feature distributions."""
        try:
            # Calculate statistical distance between distributions
            drift_scores = []
            
            for column in X_reference.select_dtypes(include=[np.number]).columns:
                if column in X_current.columns:
                    # Use Kolmogorov-Smirnov test
                    from scipy.stats import ks_2samp
                    _, p_value = ks_2samp(X_reference[column], X_current[column])
                    drift_scores.append(1 - p_value)  # Higher score = more drift
            
            max_drift = max(drift_scores) if drift_scores else 0
            mean_drift = np.mean(drift_scores) if drift_scores else 0
            
            return ModelTestResult(
                test_name="Model Drift Detection",
                model_name=str(type(self.model).__name__),
                status="pass" if max_drift <= drift_threshold else "warning",
                score=max_drift,
                threshold=drift_threshold,
                details={
                    "max_drift_score": max_drift,
                    "mean_drift_score": mean_drift,
                    "drift_scores_by_feature": dict(zip(
                        X_reference.select_dtypes(include=[np.number]).columns,
                        drift_scores
                    ))
                },
                message=f"Max drift score: {max_drift:.3f} (threshold: {drift_threshold})"
            )
        
        except Exception as e:
            return ModelTestResult(
                test_name="Model Drift Detection",
                model_name=str(type(self.model).__name__),
                status="fail",
                score=1.0,
                threshold=drift_threshold,
                details={"error": str(e)},
                message=f"Drift detection failed: {e}"
            )
    
    def _bootstrap_sample(self, X: pd.DataFrame, y: pd.Series) -> Tuple[pd.DataFrame, pd.Series]:
        """Generate bootstrap sample."""
        n_samples = len(X)
        indices = np.random.choice(n_samples, size=n_samples, replace=True)
        return X.iloc[indices], y.iloc[indices]
    
    def _create_model_copy(self):
        """Create a copy of the model for testing."""
        if hasattr(self.model, 'get_params'):
            # Scikit-learn model
            model_class = type(self.model)
            params = self.model.get_params()
            return model_class(**params)
        else:
            # For other models, return the original (not ideal but functional)
            return self.model
    
    def run_all_tests(self, X_test: pd.DataFrame, y_test: pd.Series,
                     X_train: pd.DataFrame = None, y_train: pd.Series = None,
                     X_reference: pd.DataFrame = None,
                     sensitive_feature: str = None) -> List[ModelTestResult]:
        """Run all model validation tests."""
        all_results = []
        
        # Performance tests
        performance_results = self.test_model_performance(X_test, y_test)
        all_results.extend(performance_results)
        
        # Consistency tests
        consistency_result = self.test_prediction_consistency(X_test)
        all_results.append(consistency_result)
        
        # Bounds tests
        bounds_result = self.test_prediction_bounds(X_test)
        all_results.append(bounds_result)
        
        # Input validation tests
        validation_results = self.test_input_validation(X_test)
        all_results.extend(validation_results)
        
        # Feature importance stability (if training data provided)
        if X_train is not None and y_train is not None:
            importance_result = self.test_feature_importance_stability(X_train, y_train)
            all_results.append(importance_result)
        
        # Fairness tests (if sensitive feature provided)
        if sensitive_feature:
            fairness_result = self.test_model_fairness(X_test, y_test, sensitive_feature)
            all_results.append(fairness_result)
        
        # Drift tests (if reference data provided)
        if X_reference is not None:
            drift_result = self.test_model_drift(X_reference, X_test)
            all_results.append(drift_result)
        
        return all_results


def generate_model_test_report(results: List[ModelTestResult], output_file: str = "model_test_report.json"):
    """Generate model testing report."""
    
    passed_tests = [r for r in results if r.status == "pass"]
    failed_tests = [r for r in results if r.status == "fail"]
    warning_tests = [r for r in results if r.status == "warning"]
    
    summary = {
        "total_tests": len(results),
        "passed": len(passed_tests),
        "failed": len(failed_tests),
        "warnings": len(warning_tests),
        "pass_rate": len(passed_tests) / len(results) if results else 0
    }
    
    report = {
        "summary": summary,
        "test_results": [
            {
                "test_name": r.test_name,
                "model_name": r.model_name,
                "status": r.status,
                "score": r.score,
                "threshold": r.threshold,
                "details": r.details,
                "message": r.message
            }
            for r in results
        ],
        "failed_tests": [
            {
                "test_name": r.test_name,
                "message": r.message,
                "details": r.details
            }
            for r in failed_tests
        ],
        "recommendations": _generate_model_recommendations(failed_tests, warning_tests)
    }
    
    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate summary
    summary_file = output_file.replace('.json', '_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("MODEL VALIDATION REPORT\n")
        f.write("=" * 30 + "\n\n")
        
        f.write(f"Total Tests: {summary['total_tests']}\n")
        f.write(f"Passed: {summary['passed']}\n")
        f.write(f"Failed: {summary['failed']}\n")
        f.write(f"Warnings: {summary['warnings']}\n")
        f.write(f"Pass Rate: {summary['pass_rate']:.1%}\n\n")
        
        if failed_tests:
            f.write("FAILED TESTS:\n")
            f.write("-" * 15 + "\n")
            for test in failed_tests:
                f.write(f"• {test.test_name}: {test.message}\n")
            f.write("\n")
        
        if warning_tests:
            f.write("WARNING TESTS:\n")
            f.write("-" * 15 + "\n")
            for test in warning_tests:
                f.write(f"• {test.test_name}: {test.message}\n")
            f.write("\n")
        
        f.write("RECOMMENDATIONS:\n")
        f.write("-" * 15 + "\n")
        for rec in report["recommendations"]:
            f.write(f"• {rec}\n")
    
    print(f"Model test report saved to: {output_file}")
    print(f"Summary saved to: {summary_file}")


def _generate_model_recommendations(failed_tests: List[ModelTestResult], 
                                  warning_tests: List[ModelTestResult]) -> List[str]:
    """Generate recommendations based on test results."""
    recommendations = []
    
    test_names = [t.test_name for t in failed_tests + warning_tests]
    
    if any("Performance" in name or "Error" in name for name in test_names):
        recommendations.append("Retrain model with more data or tune hyperparameters to improve performance")
    
    if any("Consistency" in name for name in test_names):
        recommendations.append("Investigate model instability - consider ensemble methods or regularization")
    
    if any("Bounds" in name for name in test_names):
        recommendations.append("Add input validation and output clipping to constrain predictions")
    
    if any("Fairness" in name for name in test_names):
        recommendations.append("Investigate bias in training data and consider fairness-aware ML techniques")
    
    if any("Drift" in name for name in test_names):
        recommendations.append("Retrain model with recent data or implement adaptive learning")
    
    if any("Importance" in name for name in test_names):
        recommendations.append("Review feature engineering and consider feature selection techniques")
    
    recommendations.extend([
        "Implement continuous model monitoring in production",
        "Establish model retraining schedule based on performance degradation",
        "Document model limitations and expected operating conditions"
    ])
    
    return recommendations


# Example usage and test fixtures
@pytest.fixture
def sample_model():
    """Create a sample model for testing."""
    np.random.seed(42)
    X = np.random.randn(1000, 5)
    y = X.sum(axis=1) + np.random.randn(1000) * 0.1
    
    model = RandomForestRegressor(n_estimators=10, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def sample_data():
    """Create sample test data."""
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(100, 5), columns=[f'feature_{i}' for i in range(5)])
    y = pd.Series(X.sum(axis=1) + np.random.randn(100) * 0.1)
    return X, y


class TestMLModelValidation:
    """Test cases for ML model validation."""
    
    def test_model_performance_evaluation(self, sample_model, sample_data):
        """Test model performance evaluation."""
        X, y = sample_data
        tester = MLModelTester(model_object=sample_model)
        
        results = tester.test_model_performance(X, y)
        
        assert len(results) == 4  # MAE, RMSE, R², MAPE
        assert all(isinstance(r, ModelTestResult) for r in results)
        assert all(r.test_name in ["Mean Absolute Error", "Root Mean Square Error", "R-squared Score", "Mean Absolute Percentage Error"] for r in results)
    
    def test_prediction_consistency(self, sample_model, sample_data):
        """Test prediction consistency."""
        X, y = sample_data
        tester = MLModelTester(model_object=sample_model)
        
        result = tester.test_prediction_consistency(X)
        
        assert isinstance(result, ModelTestResult)
        assert result.test_name == "Prediction Consistency"
        assert result.status in ["pass", "fail"]
    
    def test_input_validation(self, sample_model, sample_data):
        """Test input validation."""
        X, y = sample_data
        tester = MLModelTester(model_object=sample_model)
        
        results = tester.test_input_validation(X)
        
        assert len(results) >= 1
        assert all(isinstance(r, ModelTestResult) for r in results)
    
    def test_prediction_bounds(self, sample_model, sample_data):
        """Test prediction bounds."""
        X, y = sample_data
        tester = MLModelTester(model_object=sample_model)
        
        result = tester.test_prediction_bounds(X, expected_range=(-10, 10))
        
        assert isinstance(result, ModelTestResult)
        assert result.test_name == "Prediction Bounds"
    
    def test_full_validation_suite(self, sample_model, sample_data):
        """Test running the full validation suite."""
        X, y = sample_data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.5, random_state=42)
        
        tester = MLModelTester(model_object=sample_model)
        
        results = tester.run_all_tests(
            X_test, y_test,
            X_train=X_train, y_train=y_train
        )
        
        assert len(results) >= 5  # At least basic tests
        assert all(isinstance(r, ModelTestResult) for r in results)
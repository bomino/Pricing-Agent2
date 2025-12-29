"""
Model drift detection and monitoring tests.
"""
import pytest
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from scipy import stats
from unittest.mock import Mock, patch
import warnings
warnings.filterwarnings('ignore')


@dataclass
class DriftDetectionResult:
    """Result of drift detection test."""
    drift_type: str  # 'data_drift', 'concept_drift', 'performance_drift'
    is_drift_detected: bool
    drift_score: float
    threshold: float
    confidence: float
    affected_features: List[str]
    details: Dict[str, Any]
    recommendation: str


class DataDriftDetector:
    """Detect drift in input data distributions."""
    
    def __init__(self, reference_data: pd.DataFrame, significance_level: float = 0.05):
        self.reference_data = reference_data
        self.significance_level = significance_level
        self.feature_stats = self._calculate_reference_stats()
    
    def _calculate_reference_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculate statistics for reference data."""
        stats = {}
        for column in self.reference_data.select_dtypes(include=[np.number]).columns:
            stats[column] = {
                'mean': self.reference_data[column].mean(),
                'std': self.reference_data[column].std(),
                'min': self.reference_data[column].min(),
                'max': self.reference_data[column].max(),
                'q25': self.reference_data[column].quantile(0.25),
                'q75': self.reference_data[column].quantile(0.75)
            }
        return stats
    
    def detect_statistical_drift(self, current_data: pd.DataFrame) -> DriftDetectionResult:
        """Detect drift using statistical tests."""
        drift_scores = {}
        p_values = {}
        affected_features = []
        
        for column in self.reference_data.select_dtypes(include=[np.number]).columns:
            if column in current_data.columns:
                # Kolmogorov-Smirnov test
                ks_stat, ks_p = stats.ks_2samp(
                    self.reference_data[column],
                    current_data[column]
                )
                
                drift_scores[column] = ks_stat
                p_values[column] = ks_p
                
                if ks_p < self.significance_level:
                    affected_features.append(column)
        
        # Overall drift score (maximum KS statistic)
        max_drift_score = max(drift_scores.values()) if drift_scores else 0
        is_drift = len(affected_features) > 0
        
        return DriftDetectionResult(
            drift_type="data_drift",
            is_drift_detected=is_drift,
            drift_score=max_drift_score,
            threshold=self.significance_level,
            confidence=1 - min(p_values.values()) if p_values else 0,
            affected_features=affected_features,
            details={
                "drift_scores": drift_scores,
                "p_values": p_values,
                "test_method": "kolmogorov_smirnov"
            },
            recommendation="Retrain model if significant drift is detected" if is_drift else "No action needed"
        )
    
    def detect_distribution_drift(self, current_data: pd.DataFrame) -> DriftDetectionResult:
        """Detect drift using distribution comparison."""
        distribution_distances = {}
        affected_features = []
        threshold = 0.1  # Distance threshold
        
        for column in self.reference_data.select_dtypes(include=[np.number]).columns:
            if column in current_data.columns:
                # Calculate Wasserstein distance
                try:
                    distance = stats.wasserstein_distance(
                        self.reference_data[column],
                        current_data[column]
                    )
                    distribution_distances[column] = distance
                    
                    # Normalize by reference data range for comparison
                    ref_range = self.feature_stats[column]['max'] - self.feature_stats[column]['min']
                    normalized_distance = distance / ref_range if ref_range > 0 else distance
                    
                    if normalized_distance > threshold:
                        affected_features.append(column)
                
                except Exception as e:
                    distribution_distances[column] = float('inf')
                    affected_features.append(column)
        
        max_distance = max(distribution_distances.values()) if distribution_distances else 0
        is_drift = len(affected_features) > 0
        
        return DriftDetectionResult(
            drift_type="data_drift",
            is_drift_detected=is_drift,
            drift_score=max_distance,
            threshold=threshold,
            confidence=0.8 if is_drift else 0.9,
            affected_features=affected_features,
            details={
                "distribution_distances": distribution_distances,
                "test_method": "wasserstein_distance",
                "threshold": threshold
            },
            recommendation="Investigate feature changes and consider model retraining" if is_drift else "Distribution is stable"
        )
    
    def detect_outlier_drift(self, current_data: pd.DataFrame) -> DriftDetectionResult:
        """Detect drift using outlier detection."""
        # Fit isolation forest on reference data
        scaler = StandardScaler()
        reference_scaled = scaler.fit_transform(
            self.reference_data.select_dtypes(include=[np.number])
        )
        
        isolation_forest = IsolationForest(contamination=0.1, random_state=42)
        isolation_forest.fit(reference_scaled)
        
        # Check current data for outliers
        current_scaled = scaler.transform(
            current_data.select_dtypes(include=[np.number])
        )
        outlier_scores = isolation_forest.decision_function(current_scaled)
        outlier_predictions = isolation_forest.predict(current_scaled)
        
        outlier_rate = np.mean(outlier_predictions == -1)
        expected_outlier_rate = 0.1  # Based on contamination parameter
        
        # Drift detected if outlier rate is significantly higher than expected
        threshold = expected_outlier_rate + 0.05  # 5% tolerance
        is_drift = outlier_rate > threshold
        
        return DriftDetectionResult(
            drift_type="data_drift",
            is_drift_detected=is_drift,
            drift_score=outlier_rate,
            threshold=threshold,
            confidence=0.7,
            affected_features=["all_features"],
            details={
                "outlier_rate": outlier_rate,
                "expected_outlier_rate": expected_outlier_rate,
                "outlier_scores": outlier_scores.tolist(),
                "test_method": "isolation_forest"
            },
            recommendation="Check for data quality issues or population changes" if is_drift else "Outlier rate within expected range"
        )


class ConceptDriftDetector:
    """Detect concept drift (changes in target relationship)."""
    
    def __init__(self, model, window_size: int = 100):
        self.model = model
        self.window_size = window_size
        self.reference_performance = None
    
    def set_reference_performance(self, X_ref: pd.DataFrame, y_ref: pd.Series):
        """Set reference performance metrics."""
        predictions = self.model.predict(X_ref)
        self.reference_performance = {
            'mae': np.mean(np.abs(y_ref - predictions)),
            'mse': np.mean((y_ref - predictions) ** 2),
            'predictions': predictions,
            'targets': y_ref.values
        }
    
    def detect_performance_drift(self, X_current: pd.DataFrame, y_current: pd.Series) -> DriftDetectionResult:
        """Detect drift based on performance degradation."""
        if self.reference_performance is None:
            return DriftDetectionResult(
                drift_type="concept_drift",
                is_drift_detected=False,
                drift_score=0,
                threshold=0,
                confidence=0,
                affected_features=[],
                details={"error": "No reference performance set"},
                recommendation="Set reference performance first"
            )
        
        # Calculate current performance
        predictions = self.model.predict(X_current)
        current_mae = np.mean(np.abs(y_current - predictions))
        current_mse = np.mean((y_current - predictions) ** 2)
        
        # Calculate performance degradation
        mae_degradation = (current_mae - self.reference_performance['mae']) / self.reference_performance['mae']
        mse_degradation = (current_mse - self.reference_performance['mse']) / self.reference_performance['mse']
        
        # Thresholds for significant degradation
        threshold = 0.2  # 20% degradation
        
        is_drift = mae_degradation > threshold or mse_degradation > threshold
        drift_score = max(mae_degradation, mse_degradation)
        
        return DriftDetectionResult(
            drift_type="concept_drift",
            is_drift_detected=is_drift,
            drift_score=drift_score,
            threshold=threshold,
            confidence=0.8 if is_drift else 0.9,
            affected_features=["target_relationship"],
            details={
                "reference_mae": self.reference_performance['mae'],
                "current_mae": current_mae,
                "mae_degradation": mae_degradation,
                "reference_mse": self.reference_performance['mse'],
                "current_mse": current_mse,
                "mse_degradation": mse_degradation
            },
            recommendation="Retrain model with recent data" if is_drift else "Model performance is stable"
        )
    
    def detect_prediction_drift(self, X_current: pd.DataFrame) -> DriftDetectionResult:
        """Detect drift in prediction distributions."""
        if self.reference_performance is None:
            return DriftDetectionResult(
                drift_type="concept_drift",
                is_drift_detected=False,
                drift_score=0,
                threshold=0,
                confidence=0,
                affected_features=[],
                details={"error": "No reference performance set"},
                recommendation="Set reference performance first"
            )
        
        current_predictions = self.model.predict(X_current)
        reference_predictions = self.reference_performance['predictions']
        
        # Statistical test on prediction distributions
        ks_stat, ks_p = stats.ks_2samp(reference_predictions, current_predictions)
        
        threshold = 0.05
        is_drift = ks_p < threshold
        
        return DriftDetectionResult(
            drift_type="concept_drift",
            is_drift_detected=is_drift,
            drift_score=ks_stat,
            threshold=threshold,
            confidence=1 - ks_p,
            affected_features=["predictions"],
            details={
                "ks_statistic": ks_stat,
                "p_value": ks_p,
                "reference_pred_mean": np.mean(reference_predictions),
                "current_pred_mean": np.mean(current_predictions),
                "reference_pred_std": np.std(reference_predictions),
                "current_pred_std": np.std(current_predictions)
            },
            recommendation="Investigate prediction distribution changes" if is_drift else "Prediction distribution is stable"
        )


class ModelDriftMonitor:
    """Comprehensive model drift monitoring."""
    
    def __init__(self, model, reference_data: pd.DataFrame, reference_targets: pd.Series = None):
        self.model = model
        self.data_drift_detector = DataDriftDetector(reference_data)
        self.concept_drift_detector = ConceptDriftDetector(model)
        
        if reference_targets is not None:
            self.concept_drift_detector.set_reference_performance(reference_data, reference_targets)
    
    def comprehensive_drift_check(self, current_data: pd.DataFrame, 
                                current_targets: pd.Series = None) -> List[DriftDetectionResult]:
        """Perform comprehensive drift detection."""
        results = []
        
        # Data drift tests
        statistical_drift = self.data_drift_detector.detect_statistical_drift(current_data)
        results.append(statistical_drift)
        
        distribution_drift = self.data_drift_detector.detect_distribution_drift(current_data)
        results.append(distribution_drift)
        
        outlier_drift = self.data_drift_detector.detect_outlier_drift(current_data)
        results.append(outlier_drift)
        
        # Concept drift tests (if targets available)
        if current_targets is not None:
            performance_drift = self.concept_drift_detector.detect_performance_drift(current_data, current_targets)
            results.append(performance_drift)
        
        prediction_drift = self.concept_drift_detector.detect_prediction_drift(current_data)
        results.append(prediction_drift)
        
        return results
    
    def generate_drift_summary(self, drift_results: List[DriftDetectionResult]) -> Dict[str, Any]:
        """Generate summary of drift detection results."""
        data_drift_detected = any(
            r.is_drift_detected for r in drift_results if r.drift_type == "data_drift"
        )
        concept_drift_detected = any(
            r.is_drift_detected for r in drift_results if r.drift_type == "concept_drift"
        )
        
        all_affected_features = set()
        for result in drift_results:
            all_affected_features.update(result.affected_features)
        
        max_drift_score = max(r.drift_score for r in drift_results)
        avg_confidence = np.mean([r.confidence for r in drift_results])
        
        # Overall drift status
        if data_drift_detected and concept_drift_detected:
            overall_status = "CRITICAL"
            recommendation = "Immediate model retraining recommended"
        elif data_drift_detected or concept_drift_detected:
            overall_status = "WARNING"
            recommendation = "Monitor closely and consider retraining"
        else:
            overall_status = "STABLE"
            recommendation = "No immediate action needed"
        
        return {
            "overall_status": overall_status,
            "data_drift_detected": data_drift_detected,
            "concept_drift_detected": concept_drift_detected,
            "affected_features": list(all_affected_features),
            "max_drift_score": max_drift_score,
            "average_confidence": avg_confidence,
            "total_tests": len(drift_results),
            "failed_tests": sum(1 for r in drift_results if r.is_drift_detected),
            "recommendation": recommendation,
            "detailed_results": [
                {
                    "drift_type": r.drift_type,
                    "is_drift_detected": r.is_drift_detected,
                    "drift_score": r.drift_score,
                    "affected_features": r.affected_features,
                    "details": r.details
                }
                for r in drift_results
            ]
        }


def generate_drift_monitoring_report(drift_summary: Dict[str, Any], 
                                   output_file: str = "drift_monitoring_report.json"):
    """Generate drift monitoring report."""
    import json
    
    with open(output_file, 'w') as f:
        json.dump(drift_summary, f, indent=2)
    
    # Generate human-readable summary
    summary_file = output_file.replace('.json', '_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("MODEL DRIFT MONITORING REPORT\n")
        f.write("=" * 35 + "\n\n")
        
        f.write(f"Overall Status: {drift_summary['overall_status']}\n")
        f.write(f"Data Drift Detected: {drift_summary['data_drift_detected']}\n")
        f.write(f"Concept Drift Detected: {drift_summary['concept_drift_detected']}\n")
        f.write(f"Total Tests: {drift_summary['total_tests']}\n")
        f.write(f"Failed Tests: {drift_summary['failed_tests']}\n")
        f.write(f"Max Drift Score: {drift_summary['max_drift_score']:.4f}\n")
        f.write(f"Average Confidence: {drift_summary['average_confidence']:.2%}\n\n")
        
        if drift_summary['affected_features']:
            f.write("Affected Features:\n")
            for feature in drift_summary['affected_features']:
                f.write(f"• {feature}\n")
            f.write("\n")
        
        f.write(f"Recommendation: {drift_summary['recommendation']}\n\n")
        
        f.write("Detailed Test Results:\n")
        f.write("-" * 25 + "\n")
        for result in drift_summary['detailed_results']:
            status = "DRIFT DETECTED" if result['is_drift_detected'] else "STABLE"
            f.write(f"• {result['drift_type'].upper()}: {status}\n")
            f.write(f"  Score: {result['drift_score']:.4f}\n")
            if result['affected_features']:
                f.write(f"  Affected: {', '.join(result['affected_features'])}\n")
            f.write("\n")
    
    print(f"Drift monitoring report saved to: {output_file}")
    print(f"Summary saved to: {summary_file}")


# Test fixtures and examples
@pytest.fixture
def reference_data():
    """Create reference dataset."""
    np.random.seed(42)
    data = pd.DataFrame({
        'feature1': np.random.normal(10, 2, 1000),
        'feature2': np.random.exponential(5, 1000),
        'feature3': np.random.uniform(0, 100, 1000),
        'feature4': np.random.gamma(2, 2, 1000)
    })
    return data


@pytest.fixture
def drifted_data():
    """Create dataset with drift."""
    np.random.seed(123)
    data = pd.DataFrame({
        'feature1': np.random.normal(12, 3, 500),  # Mean and std changed
        'feature2': np.random.exponential(7, 500),  # Scale changed
        'feature3': np.random.uniform(20, 120, 500),  # Range shifted
        'feature4': np.random.gamma(3, 2, 500)  # Shape changed
    })
    return data


@pytest.fixture
def stable_data():
    """Create stable dataset (no drift)."""
    np.random.seed(456)
    data = pd.DataFrame({
        'feature1': np.random.normal(10, 2, 500),
        'feature2': np.random.exponential(5, 500),
        'feature3': np.random.uniform(0, 100, 500),
        'feature4': np.random.gamma(2, 2, 500)
    })
    return data


@pytest.fixture
def sample_model():
    """Create sample model."""
    from sklearn.ensemble import RandomForestRegressor
    model = RandomForestRegressor(n_estimators=10, random_state=42)
    return model


class TestDriftDetection:
    """Test cases for drift detection."""
    
    def test_statistical_drift_detection(self, reference_data, drifted_data):
        """Test statistical drift detection."""
        detector = DataDriftDetector(reference_data)
        result = detector.detect_statistical_drift(drifted_data)
        
        assert isinstance(result, DriftDetectionResult)
        assert result.drift_type == "data_drift"
        assert result.is_drift_detected is True
        assert len(result.affected_features) > 0
    
    def test_no_drift_detection(self, reference_data, stable_data):
        """Test that no drift is detected in stable data."""
        detector = DataDriftDetector(reference_data)
        result = detector.detect_statistical_drift(stable_data)
        
        assert isinstance(result, DriftDetectionResult)
        assert result.drift_type == "data_drift"
        assert result.is_drift_detected is False
    
    def test_distribution_drift_detection(self, reference_data, drifted_data):
        """Test distribution-based drift detection."""
        detector = DataDriftDetector(reference_data)
        result = detector.detect_distribution_drift(drifted_data)
        
        assert isinstance(result, DriftDetectionResult)
        assert result.drift_type == "data_drift"
        assert result.drift_score >= 0
    
    def test_outlier_drift_detection(self, reference_data, drifted_data):
        """Test outlier-based drift detection."""
        detector = DataDriftDetector(reference_data)
        result = detector.detect_outlier_drift(drifted_data)
        
        assert isinstance(result, DriftDetectionResult)
        assert result.drift_type == "data_drift"
        assert 0 <= result.drift_score <= 1
    
    def test_concept_drift_detection(self, sample_model, reference_data):
        """Test concept drift detection."""
        # Create synthetic targets
        y_ref = reference_data.sum(axis=1) + np.random.normal(0, 1, len(reference_data))
        y_current = reference_data.iloc[:100].sum(axis=1) + np.random.normal(0, 5, 100)  # Higher noise
        
        # Fit model
        sample_model.fit(reference_data, y_ref)
        
        detector = ConceptDriftDetector(sample_model)
        detector.set_reference_performance(reference_data, y_ref)
        
        result = detector.detect_performance_drift(reference_data.iloc[:100], y_current)
        
        assert isinstance(result, DriftDetectionResult)
        assert result.drift_type == "concept_drift"
    
    def test_comprehensive_drift_monitoring(self, sample_model, reference_data, drifted_data):
        """Test comprehensive drift monitoring."""
        # Create synthetic targets
        y_ref = reference_data.sum(axis=1) + np.random.normal(0, 1, len(reference_data))
        y_current = drifted_data.sum(axis=1) + np.random.normal(0, 1, len(drifted_data))
        
        # Fit model
        sample_model.fit(reference_data, y_ref)
        
        monitor = ModelDriftMonitor(sample_model, reference_data, y_ref)
        results = monitor.comprehensive_drift_check(drifted_data, y_current)
        
        assert len(results) >= 4  # At least 4 different drift tests
        assert all(isinstance(r, DriftDetectionResult) for r in results)
        
        # Test summary generation
        summary = monitor.generate_drift_summary(results)
        
        assert "overall_status" in summary
        assert summary["total_tests"] == len(results)
        assert "recommendation" in summary
    
    def test_drift_monitoring_without_targets(self, sample_model, reference_data, drifted_data):
        """Test drift monitoring when targets are not available."""
        # Fit model on reference data
        y_ref = reference_data.sum(axis=1) + np.random.normal(0, 1, len(reference_data))
        sample_model.fit(reference_data, y_ref)
        
        monitor = ModelDriftMonitor(sample_model, reference_data)
        results = monitor.comprehensive_drift_check(drifted_data)
        
        # Should still perform data drift and prediction drift tests
        assert len(results) >= 3
        assert any(r.drift_type == "data_drift" for r in results)
    
    def test_drift_report_generation(self, sample_model, reference_data, drifted_data):
        """Test drift report generation."""
        y_ref = reference_data.sum(axis=1) + np.random.normal(0, 1, len(reference_data))
        sample_model.fit(reference_data, y_ref)
        
        monitor = ModelDriftMonitor(sample_model, reference_data, y_ref)
        results = monitor.comprehensive_drift_check(drifted_data)
        summary = monitor.generate_drift_summary(results)
        
        # Test report generation (mock file operations)
        with patch('builtins.open'), patch('json.dump'):
            generate_drift_monitoring_report(summary, "test_drift_report.json")
        
        assert "overall_status" in summary
        assert "detailed_results" in summary
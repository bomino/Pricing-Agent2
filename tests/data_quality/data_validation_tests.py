"""
Data quality testing framework for the AI Pricing Agent system.
"""
import pytest
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
import json
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


class ValidationSeverity(Enum):
    """Severity levels for data validation issues."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationRule:
    """Represents a data validation rule."""
    name: str
    description: str
    severity: ValidationSeverity
    validator_function: Callable
    columns: Optional[List[str]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of a data validation check."""
    rule_name: str
    status: str  # 'pass', 'fail', 'error'
    severity: ValidationSeverity
    message: str
    failed_count: int
    total_count: int
    failed_percentage: float
    sample_failures: List[Any]
    details: Dict[str, Any]
    execution_time: float


class DataQualityValidator:
    """Framework for data quality validation."""
    
    def __init__(self):
        self.rules = []
        self.results = []
        self.custom_validators = {}
    
    def add_rule(self, rule: ValidationRule):
        """Add a validation rule."""
        self.rules.append(rule)
    
    def add_custom_validator(self, name: str, validator_function: Callable):
        """Add a custom validator function."""
        self.custom_validators[name] = validator_function
    
    def validate_dataset(self, df: pd.DataFrame, rule_tags: List[str] = None) -> List[ValidationResult]:
        """Validate a dataset using all applicable rules."""
        results = []
        
        # Filter rules by tags if specified
        applicable_rules = self.rules
        if rule_tags:
            applicable_rules = [r for r in self.rules if any(tag in r.tags for tag in rule_tags)]
        
        for rule in applicable_rules:
            try:
                start_time = datetime.now()
                result = self._execute_rule(df, rule)
                execution_time = (datetime.now() - start_time).total_seconds()
                result.execution_time = execution_time
                results.append(result)
            except Exception as e:
                error_result = ValidationResult(
                    rule_name=rule.name,
                    status="error",
                    severity=rule.severity,
                    message=f"Rule execution failed: {str(e)}",
                    failed_count=0,
                    total_count=len(df),
                    failed_percentage=0.0,
                    sample_failures=[],
                    details={"error": str(e)},
                    execution_time=0.0
                )
                results.append(error_result)
        
        self.results.extend(results)
        return results
    
    def _execute_rule(self, df: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        """Execute a single validation rule."""
        # Determine which data to validate
        if rule.columns:
            # Rule applies to specific columns
            available_columns = [col for col in rule.columns if col in df.columns]
            if not available_columns:
                return ValidationResult(
                    rule_name=rule.name,
                    status="error",
                    severity=ValidationSeverity.WARNING,
                    message=f"No applicable columns found: {rule.columns}",
                    failed_count=0,
                    total_count=0,
                    failed_percentage=0.0,
                    sample_failures=[],
                    details={"missing_columns": rule.columns},
                    execution_time=0.0
                )
            validation_data = df[available_columns]
        else:
            # Rule applies to entire dataframe
            validation_data = df
        
        # Execute the validator function
        try:
            validation_result = rule.validator_function(validation_data, **rule.parameters)
            
            # Handle different return types from validator functions
            if isinstance(validation_result, tuple):
                is_valid, failed_indices, details = validation_result
            elif isinstance(validation_result, bool):
                is_valid = validation_result
                failed_indices = []
                details = {}
            else:
                # Assume it's a pandas Series of boolean values
                is_valid = validation_result.all()
                failed_indices = validation_result[~validation_result].index.tolist()
                details = {}
            
            # Calculate metrics
            total_count = len(validation_data) if hasattr(validation_data, '__len__') else len(df)
            failed_count = len(failed_indices)
            failed_percentage = (failed_count / total_count * 100) if total_count > 0 else 0
            
            # Get sample failures
            sample_failures = []
            if failed_indices and hasattr(validation_data, 'iloc'):
                sample_size = min(5, len(failed_indices))
                sample_indices = failed_indices[:sample_size]
                for idx in sample_indices:
                    try:
                        sample_failures.append(validation_data.iloc[idx].to_dict() if hasattr(validation_data.iloc[idx], 'to_dict') else str(validation_data.iloc[idx]))
                    except:
                        sample_failures.append(f"Index {idx}")
            
            # Determine status
            status = "pass" if is_valid else "fail"
            message = f"{rule.description} - {failed_count}/{total_count} records failed ({failed_percentage:.1f}%)"
            
            return ValidationResult(
                rule_name=rule.name,
                status=status,
                severity=rule.severity,
                message=message,
                failed_count=failed_count,
                total_count=total_count,
                failed_percentage=failed_percentage,
                sample_failures=sample_failures,
                details=details,
                execution_time=0.0
            )
        
        except Exception as e:
            return ValidationResult(
                rule_name=rule.name,
                status="error",
                severity=rule.severity,
                message=f"Validation execution failed: {str(e)}",
                failed_count=0,
                total_count=len(df),
                failed_percentage=0.0,
                sample_failures=[],
                details={"error": str(e)},
                execution_time=0.0
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of validation results."""
        if not self.results:
            return {"message": "No validation results available"}
        
        total_rules = len(self.results)
        passed_rules = len([r for r in self.results if r.status == "pass"])
        failed_rules = len([r for r in self.results if r.status == "fail"])
        error_rules = len([r for r in self.results if r.status == "error"])
        
        # Group by severity
        severity_counts = {}
        for severity in ValidationSeverity:
            severity_counts[severity.value] = len([r for r in self.results if r.severity == severity])
        
        # Critical failures
        critical_failures = [r for r in self.results if r.severity == ValidationSeverity.CRITICAL and r.status == "fail"]
        
        return {
            "total_rules": total_rules,
            "passed_rules": passed_rules,
            "failed_rules": failed_rules,
            "error_rules": error_rules,
            "pass_rate": passed_rules / total_rules if total_rules > 0 else 0,
            "severity_counts": severity_counts,
            "critical_failures": len(critical_failures),
            "data_quality_score": self._calculate_quality_score(),
            "recommendations": self._generate_recommendations()
        }
    
    def _calculate_quality_score(self) -> float:
        """Calculate overall data quality score (0-100)."""
        if not self.results:
            return 0.0
        
        # Weight by severity
        severity_weights = {
            ValidationSeverity.CRITICAL: 10,
            ValidationSeverity.ERROR: 5,
            ValidationSeverity.WARNING: 2,
            ValidationSeverity.INFO: 1
        }
        
        total_weight = 0
        failed_weight = 0
        
        for result in self.results:
            weight = severity_weights[result.severity]
            total_weight += weight
            
            if result.status == "fail":
                # Weight failure by percentage of failed records
                failure_impact = (result.failed_percentage / 100) * weight
                failed_weight += failure_impact
        
        if total_weight == 0:
            return 100.0
        
        quality_score = max(0, 100 - (failed_weight / total_weight * 100))
        return quality_score
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        critical_failures = [r for r in self.results if r.severity == ValidationSeverity.CRITICAL and r.status == "fail"]
        if critical_failures:
            recommendations.append("Address critical data quality issues immediately before using data")
        
        high_failure_rate_rules = [r for r in self.results if r.failed_percentage > 10 and r.status == "fail"]
        if high_failure_rate_rules:
            recommendations.append("Focus on rules with high failure rates (>10% of records)")
        
        error_rules = [r for r in self.results if r.status == "error"]
        if error_rules:
            recommendations.append("Fix validation rule execution errors")
        
        recommendations.extend([
            "Implement data quality monitoring in production pipeline",
            "Set up alerts for critical data quality issues",
            "Regularly review and update validation rules"
        ])
        
        return recommendations


# Common validation functions
def validate_not_null(data: Union[pd.DataFrame, pd.Series], **kwargs) -> tuple:
    """Validate that data is not null."""
    if isinstance(data, pd.DataFrame):
        is_valid = data.notna().all().all()
        null_mask = data.isna().any(axis=1)
        failed_indices = data[null_mask].index.tolist()
    else:
        is_valid = data.notna().all()
        failed_indices = data[data.isna()].index.tolist()
    
    return is_valid, failed_indices, {"null_count": len(failed_indices)}


def validate_range(data: pd.Series, min_val: float = None, max_val: float = None, **kwargs) -> tuple:
    """Validate that numeric data falls within specified range."""
    if not pd.api.types.is_numeric_dtype(data):
        return False, list(range(len(data))), {"error": "Non-numeric data"}
    
    valid_mask = pd.Series([True] * len(data), index=data.index)
    
    if min_val is not None:
        valid_mask &= (data >= min_val)
    
    if max_val is not None:
        valid_mask &= (data <= max_val)
    
    is_valid = valid_mask.all()
    failed_indices = data[~valid_mask].index.tolist()
    
    return is_valid, failed_indices, {
        "min_val": min_val,
        "max_val": max_val,
        "actual_min": data.min(),
        "actual_max": data.max()
    }


def validate_unique(data: pd.Series, **kwargs) -> tuple:
    """Validate that all values are unique."""
    is_valid = not data.duplicated().any()
    duplicated_mask = data.duplicated(keep=False)
    failed_indices = data[duplicated_mask].index.tolist()
    
    return is_valid, failed_indices, {
        "duplicate_count": len(failed_indices),
        "unique_values": data.nunique(),
        "total_values": len(data)
    }


def validate_pattern(data: pd.Series, pattern: str, **kwargs) -> tuple:
    """Validate that string data matches a regex pattern."""
    if not pd.api.types.is_string_dtype(data):
        return False, list(range(len(data))), {"error": "Non-string data"}
    
    try:
        regex = re.compile(pattern)
        valid_mask = data.astype(str).str.match(regex, na=False)
        is_valid = valid_mask.all()
        failed_indices = data[~valid_mask].index.tolist()
        
        return is_valid, failed_indices, {
            "pattern": pattern,
            "matching_count": valid_mask.sum()
        }
    
    except re.error as e:
        return False, list(range(len(data))), {"error": f"Invalid regex pattern: {e}"}


def validate_email_format(data: pd.Series, **kwargs) -> tuple:
    """Validate email format."""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return validate_pattern(data, email_pattern)


def validate_positive(data: pd.Series, **kwargs) -> tuple:
    """Validate that numeric data is positive."""
    return validate_range(data, min_val=0.000001)


def validate_date_format(data: pd.Series, date_format: str = None, **kwargs) -> tuple:
    """Validate date format."""
    if pd.api.types.is_datetime64_any_dtype(data):
        # Already datetime, assume valid
        return True, [], {"format": "datetime"}
    
    failed_indices = []
    
    for idx, value in data.items():
        if pd.isna(value):
            continue
        
        try:
            if date_format:
                datetime.strptime(str(value), date_format)
            else:
                pd.to_datetime(str(value))
        except (ValueError, TypeError):
            failed_indices.append(idx)
    
    is_valid = len(failed_indices) == 0
    
    return is_valid, failed_indices, {
        "expected_format": date_format or "flexible",
        "invalid_count": len(failed_indices)
    }


def validate_categorical(data: pd.Series, allowed_values: List[Any], **kwargs) -> tuple:
    """Validate that data contains only allowed categorical values."""
    valid_mask = data.isin(allowed_values)
    is_valid = valid_mask.all()
    failed_indices = data[~valid_mask].index.tolist()
    
    invalid_values = data[~valid_mask].unique().tolist()
    
    return is_valid, failed_indices, {
        "allowed_values": allowed_values,
        "invalid_values": invalid_values,
        "invalid_count": len(failed_indices)
    }


def validate_completeness(data: pd.DataFrame, required_columns: List[str], **kwargs) -> tuple:
    """Validate that required columns are present and not empty."""
    missing_columns = [col for col in required_columns if col not in data.columns]
    
    if missing_columns:
        return False, [], {"missing_columns": missing_columns}
    
    # Check for completely empty columns
    empty_columns = []
    for col in required_columns:
        if data[col].isna().all():
            empty_columns.append(col)
    
    is_valid = len(empty_columns) == 0
    
    return is_valid, [], {
        "required_columns": required_columns,
        "missing_columns": missing_columns,
        "empty_columns": empty_columns
    }


def validate_consistency(data: pd.DataFrame, column_pairs: List[tuple], **kwargs) -> tuple:
    """Validate consistency between related columns."""
    failed_indices = []
    consistency_checks = []
    
    for col1, col2 in column_pairs:
        if col1 in data.columns and col2 in data.columns:
            # Example: start_date should be <= end_date
            if 'date' in col1.lower() and 'date' in col2.lower():
                try:
                    date1 = pd.to_datetime(data[col1])
                    date2 = pd.to_datetime(data[col2])
                    invalid_mask = date1 > date2
                    failed_indices.extend(data[invalid_mask].index.tolist())
                    consistency_checks.append(f"{col1} <= {col2}")
                except:
                    consistency_checks.append(f"{col1} vs {col2} (conversion failed)")
    
    is_valid = len(failed_indices) == 0
    
    return is_valid, failed_indices, {
        "column_pairs": column_pairs,
        "consistency_checks": consistency_checks,
        "inconsistent_records": len(failed_indices)
    }


class DataQualityTestSuite:
    """Pre-configured test suites for common data quality scenarios."""
    
    @staticmethod
    def pricing_data_suite() -> DataQualityValidator:
        """Create validation suite for pricing data."""
        validator = DataQualityValidator()
        
        # Critical validations
        validator.add_rule(ValidationRule(
            name="pricing_not_null",
            description="Price fields must not be null",
            severity=ValidationSeverity.CRITICAL,
            validator_function=validate_not_null,
            columns=['price', 'unit_price', 'total_price'],
            tags=['pricing', 'critical']
        ))
        
        validator.add_rule(ValidationRule(
            name="pricing_positive",
            description="Prices must be positive",
            severity=ValidationSeverity.CRITICAL,
            validator_function=validate_positive,
            columns=['price', 'unit_price', 'total_price'],
            tags=['pricing', 'critical']
        ))
        
        validator.add_rule(ValidationRule(
            name="quantity_positive",
            description="Quantities must be positive",
            severity=ValidationSeverity.ERROR,
            validator_function=validate_positive,
            columns=['quantity'],
            tags=['pricing', 'business_logic']
        ))
        
        # Business logic validations
        validator.add_rule(ValidationRule(
            name="price_range",
            description="Prices should be within reasonable range",
            severity=ValidationSeverity.WARNING,
            validator_function=validate_range,
            columns=['price', 'unit_price'],
            parameters={'min_val': 0.01, 'max_val': 1000000},
            tags=['pricing', 'business_logic']
        ))
        
        # Data format validations
        validator.add_rule(ValidationRule(
            name="currency_code",
            description="Currency codes must be valid",
            severity=ValidationSeverity.ERROR,
            validator_function=validate_categorical,
            columns=['currency'],
            parameters={'allowed_values': ['USD', 'EUR', 'GBP', 'CAD', 'JPY']},
            tags=['pricing', 'format']
        ))
        
        return validator
    
    @staticmethod
    def supplier_data_suite() -> DataQualityValidator:
        """Create validation suite for supplier data."""
        validator = DataQualityValidator()
        
        # Critical validations
        validator.add_rule(ValidationRule(
            name="supplier_required_fields",
            description="Required supplier fields must be present",
            severity=ValidationSeverity.CRITICAL,
            validator_function=validate_completeness,
            parameters={'required_columns': ['name', 'email', 'status']},
            tags=['supplier', 'critical']
        ))
        
        validator.add_rule(ValidationRule(
            name="supplier_email_format",
            description="Supplier email must be valid format",
            severity=ValidationSeverity.ERROR,
            validator_function=validate_email_format,
            columns=['email'],
            tags=['supplier', 'format']
        ))
        
        validator.add_rule(ValidationRule(
            name="supplier_status",
            description="Supplier status must be valid",
            severity=ValidationSeverity.ERROR,
            validator_function=validate_categorical,
            columns=['status'],
            parameters={'allowed_values': ['active', 'inactive', 'pending', 'suspended']},
            tags=['supplier', 'business_logic']
        ))
        
        return validator
    
    @staticmethod
    def material_data_suite() -> DataQualityValidator:
        """Create validation suite for material data."""
        validator = DataQualityValidator()
        
        # Critical validations
        validator.add_rule(ValidationRule(
            name="material_code_unique",
            description="Material codes must be unique",
            severity=ValidationSeverity.CRITICAL,
            validator_function=validate_unique,
            columns=['code'],
            tags=['material', 'critical']
        ))
        
        validator.add_rule(ValidationRule(
            name="material_required_fields",
            description="Required material fields must be present",
            severity=ValidationSeverity.CRITICAL,
            validator_function=validate_completeness,
            parameters={'required_columns': ['code', 'name', 'unit_of_measure']},
            tags=['material', 'critical']
        ))
        
        # Format validations
        validator.add_rule(ValidationRule(
            name="material_code_format",
            description="Material codes must follow standard format",
            severity=ValidationSeverity.WARNING,
            validator_function=validate_pattern,
            columns=['code'],
            parameters={'pattern': r'^[A-Z]{2,3}[0-9]{3,6}$'},
            tags=['material', 'format']
        ))
        
        # Business logic validations
        validator.add_rule(ValidationRule(
            name="weight_positive",
            description="Material weight must be positive",
            severity=ValidationSeverity.WARNING,
            validator_function=validate_positive,
            columns=['weight'],
            tags=['material', 'business_logic']
        ))
        
        return validator


def generate_data_quality_report(results: List[ValidationResult], 
                                summary: Dict[str, Any],
                                output_file: str = "data_quality_report.json"):
    """Generate comprehensive data quality report."""
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "detailed_results": [
            {
                "rule_name": r.rule_name,
                "status": r.status,
                "severity": r.severity.value,
                "message": r.message,
                "failed_count": r.failed_count,
                "total_count": r.total_count,
                "failed_percentage": r.failed_percentage,
                "sample_failures": r.sample_failures[:3],  # Limit sample size
                "execution_time": r.execution_time,
                "details": r.details
            }
            for r in results
        ],
        "critical_issues": [
            {
                "rule_name": r.rule_name,
                "message": r.message,
                "failed_percentage": r.failed_percentage,
                "sample_failures": r.sample_failures[:3]
            }
            for r in results 
            if r.severity == ValidationSeverity.CRITICAL and r.status == "fail"
        ],
        "recommendations": summary.get("recommendations", [])
    }
    
    # Save JSON report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Generate human-readable summary
    summary_file = output_file.replace('.json', '_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("DATA QUALITY VALIDATION REPORT\n")
        f.write("=" * 40 + "\n\n")
        
        f.write(f"Overall Quality Score: {summary['data_quality_score']:.1f}/100\n")
        f.write(f"Total Rules Executed: {summary['total_rules']}\n")
        f.write(f"Passed: {summary['passed_rules']}\n")
        f.write(f"Failed: {summary['failed_rules']}\n")
        f.write(f"Errors: {summary['error_rules']}\n")
        f.write(f"Pass Rate: {summary['pass_rate']:.1%}\n\n")
        
        if summary['critical_failures'] > 0:
            f.write(f"⚠️  CRITICAL ISSUES FOUND: {summary['critical_failures']}\n\n")
            
            f.write("Critical Failures:\n")
            f.write("-" * 20 + "\n")
            for issue in report['critical_issues']:
                f.write(f"• {issue['rule_name']}: {issue['failed_percentage']:.1f}% failure rate\n")
                f.write(f"  {issue['message']}\n\n")
        
        f.write("Recommendations:\n")
        f.write("-" * 15 + "\n")
        for rec in report['recommendations']:
            f.write(f"• {rec}\n")
        
        f.write(f"\nDetailed results available in: {output_file}\n")
    
    print(f"Data quality report saved to: {output_file}")
    print(f"Summary saved to: {summary_file}")


# Test fixtures and examples
@pytest.fixture
def sample_pricing_data():
    """Create sample pricing data with quality issues."""
    return pd.DataFrame({
        'material_id': [1, 2, 3, 4, 5, 6],
        'supplier_id': [101, 102, 103, 104, 105, 106],
        'price': [100.50, -50.00, None, 999999.99, 25.75, 0.01],  # Negative and null prices
        'quantity': [1000, 500, 200, -100, 0, 1500],  # Negative quantity
        'currency': ['USD', 'EUR', 'INVALID', 'USD', 'GBP', None],  # Invalid currency
        'unit_price': [0.10, -0.10, 0.50, 999.99, 0.26, 0.01],
        'total_price': [100.0, -50.0, 100.0, -99999.0, 25.0, 15.0]
    })


@pytest.fixture
def sample_supplier_data():
    """Create sample supplier data with quality issues."""
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Supplier A', 'Supplier B', None, 'Supplier D', 'Supplier E'],
        'email': ['valid@email.com', 'invalid-email', 'test@domain.co', None, 'another@valid.com'],
        'status': ['active', 'inactive', 'unknown_status', 'active', 'pending']
    })


class TestDataQualityValidation:
    """Test cases for data quality validation."""
    
    def test_pricing_data_validation(self, sample_pricing_data):
        """Test pricing data validation suite."""
        validator = DataQualityTestSuite.pricing_data_suite()
        results = validator.validate_dataset(sample_pricing_data, rule_tags=['pricing'])
        
        assert len(results) > 0
        assert any(r.status == "fail" for r in results)  # Should have failures
        
        # Check specific validation results
        not_null_results = [r for r in results if r.rule_name == "pricing_not_null"]
        assert len(not_null_results) == 1
        assert not_null_results[0].status == "fail"  # Should fail due to null prices
        
        positive_results = [r for r in results if r.rule_name == "pricing_positive"]
        assert len(positive_results) == 1
        assert positive_results[0].status == "fail"  # Should fail due to negative prices
    
    def test_supplier_data_validation(self, sample_supplier_data):
        """Test supplier data validation suite."""
        validator = DataQualityTestSuite.supplier_data_suite()
        results = validator.validate_dataset(sample_supplier_data, rule_tags=['supplier'])
        
        assert len(results) > 0
        
        # Check email format validation
        email_results = [r for r in results if r.rule_name == "supplier_email_format"]
        assert len(email_results) == 1
        assert email_results[0].status == "fail"  # Should fail due to invalid emails
    
    def test_custom_validation_rule(self):
        """Test adding custom validation rules."""
        def validate_custom_business_rule(data, **kwargs):
            # Custom rule: price per unit should not exceed 1000
            if 'price' in data.columns and 'quantity' in data.columns:
                price_per_unit = data['price'] / data['quantity']
                valid_mask = price_per_unit <= 1000
                failed_indices = price_per_unit[~valid_mask].index.tolist()
                return valid_mask.all(), failed_indices, {"max_price_per_unit": price_per_unit.max()}
            return True, [], {}
        
        validator = DataQualityValidator()
        validator.add_rule(ValidationRule(
            name="custom_price_per_unit",
            description="Price per unit should not exceed 1000",
            severity=ValidationSeverity.WARNING,
            validator_function=validate_custom_business_rule,
            tags=['custom']
        ))
        
        test_data = pd.DataFrame({
            'price': [100, 2000, 50],
            'quantity': [1, 1, 10]  # Second row will have price per unit of 2000
        })
        
        results = validator.validate_dataset(test_data)
        
        assert len(results) == 1
        assert results[0].rule_name == "custom_price_per_unit"
        assert results[0].status == "fail"
    
    def test_validation_summary(self, sample_pricing_data):
        """Test validation summary generation."""
        validator = DataQualityTestSuite.pricing_data_suite()
        results = validator.validate_dataset(sample_pricing_data)
        summary = validator.get_summary()
        
        assert "total_rules" in summary
        assert "data_quality_score" in summary
        assert "recommendations" in summary
        assert summary["total_rules"] == len(results)
        assert 0 <= summary["data_quality_score"] <= 100
    
    def test_validation_with_no_failures(self):
        """Test validation with clean data (no failures expected)."""
        clean_data = pd.DataFrame({
            'price': [100.0, 200.0, 50.0],
            'quantity': [10, 5, 20],
            'currency': ['USD', 'USD', 'EUR'],
            'unit_price': [10.0, 40.0, 2.5],
            'total_price': [100.0, 200.0, 50.0]
        })
        
        validator = DataQualityTestSuite.pricing_data_suite()
        results = validator.validate_dataset(clean_data)
        
        # Most rules should pass with clean data
        passed_results = [r for r in results if r.status == "pass"]
        assert len(passed_results) > 0
        
        summary = validator.get_summary()
        assert summary["data_quality_score"] > 80  # Should have high quality score
    
    def test_report_generation(self, sample_pricing_data):
        """Test data quality report generation."""
        validator = DataQualityTestSuite.pricing_data_suite()
        results = validator.validate_dataset(sample_pricing_data)
        summary = validator.get_summary()
        
        # Test report generation (mock file operations)
        from unittest.mock import patch, mock_open
        
        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                generate_data_quality_report(results, summary, "test_report.json")
        
        # Verify summary structure
        assert "data_quality_score" in summary
        assert "recommendations" in summary
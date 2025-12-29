"""
ML test data fixtures and utilities.
"""
import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split
import joblib


class MLTestDataGenerator:
    """Generate realistic test data for ML model testing."""
    
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        np.random.seed(random_state)
    
    def generate_pricing_dataset(self, n_samples: int = 1000) -> pd.DataFrame:
        """Generate synthetic pricing dataset."""
        
        # Material types and their base prices
        material_types = {
            'steel': {'base_price': 1200, 'volatility': 0.2},
            'aluminum': {'base_price': 1800, 'volatility': 0.25},
            'plastic': {'base_price': 300, 'volatility': 0.15},
            'composite': {'base_price': 2500, 'volatility': 0.3},
            'copper': {'base_price': 8000, 'volatility': 0.35}
        }
        
        grades = {
            'steel': ['A36', 'A572', 'A514', '304SS', '316SS'],
            'aluminum': ['6061', '7075', '2024', '5052', '6063'],
            'plastic': ['ABS', 'PVC', 'HDPE', 'PP', 'PET'],
            'composite': ['Carbon', 'Fiberglass', 'Kevlar', 'Hybrid'],
            'copper': ['C101', 'C110', 'C260', 'C360', 'C464']
        }
        
        suppliers = ['SupplierA', 'SupplierB', 'SupplierC', 'SupplierD', 'SupplierE']
        supplier_tiers = {
            'SupplierA': 1, 'SupplierB': 1, 'SupplierC': 2, 
            'SupplierD': 2, 'SupplierE': 3
        }
        
        data = []
        
        for _ in range(n_samples):
            # Select material type
            material_type = np.random.choice(list(material_types.keys()))
            base_price = material_types[material_type]['base_price']
            volatility = material_types[material_type]['volatility']
            
            # Generate features
            record = {
                'material_type': material_type,
                'grade': np.random.choice(grades[material_type]),
                'thickness': np.random.uniform(1, 50),
                'width': np.random.uniform(10, 2000),
                'length': np.random.uniform(10, 5000),
                'weight': np.random.uniform(0.1, 10000),
                'quantity': np.random.randint(1, 10000),
                'supplier': np.random.choice(suppliers),
                'lead_time_days': np.random.randint(1, 120),
                'delivery_distance': np.random.uniform(10, 5000),
                'order_urgency': np.random.choice(['low', 'medium', 'high']),
                'market_condition': np.random.choice(['stable', 'volatile', 'declining', 'rising']),
                'season': np.random.choice(['spring', 'summer', 'fall', 'winter']),
                'certification_required': np.random.choice([True, False]),
                'custom_specifications': np.random.choice([True, False])
            }
            
            # Add supplier tier
            record['supplier_tier'] = supplier_tiers[record['supplier']]
            
            # Calculate volume (for volume-based pricing)
            if material_type in ['steel', 'aluminum']:
                volume = record['thickness'] * record['width'] * record['length'] / 1000000  # cm³
            else:
                volume = record['weight'] / 1000  # Approximate volume
            record['volume'] = volume
            
            # Generate realistic price based on features
            price = self._calculate_realistic_price(record, base_price, volatility)
            record['price_per_unit'] = price
            record['total_price'] = price * record['quantity']
            
            data.append(record)
        
        df = pd.DataFrame(data)
        return df
    
    def _calculate_realistic_price(self, record: Dict, base_price: float, volatility: float) -> float:
        """Calculate realistic price based on material features."""
        price = base_price
        
        # Volume effect (economies of scale)
        volume_factor = 1.0 - min(0.3, record['quantity'] / 50000)
        price *= volume_factor
        
        # Supplier tier effect
        tier_multipliers = {1: 0.95, 2: 1.0, 3: 1.15}
        price *= tier_multipliers[record['supplier_tier']]
        
        # Lead time effect
        if record['lead_time_days'] < 7:
            price *= 1.2  # Rush order premium
        elif record['lead_time_days'] > 60:
            price *= 0.95  # Long lead time discount
        
        # Market condition effect
        market_multipliers = {
            'stable': 1.0,
            'volatile': np.random.uniform(0.9, 1.1),
            'declining': np.random.uniform(0.85, 0.95),
            'rising': np.random.uniform(1.05, 1.15)
        }
        price *= market_multipliers[record['market_condition']]
        
        # Urgency premium
        urgency_multipliers = {'low': 1.0, 'medium': 1.05, 'high': 1.15}
        price *= urgency_multipliers[record['order_urgency']]
        
        # Certification premium
        if record['certification_required']:
            price *= 1.08
        
        # Custom specifications premium
        if record['custom_specifications']:
            price *= 1.12
        
        # Add material-specific variations
        if record['material_type'] == 'steel':
            grade_multipliers = {'A36': 1.0, 'A572': 1.05, 'A514': 1.25, '304SS': 1.8, '316SS': 2.2}
            price *= grade_multipliers.get(record['grade'], 1.0)
        
        # Add noise based on volatility
        noise_factor = np.random.normal(1.0, volatility * 0.5)
        price *= max(0.5, min(2.0, noise_factor))  # Clamp extreme values
        
        return round(price, 2)
    
    def generate_time_series_data(self, n_days: int = 365, materials: List[str] = None) -> pd.DataFrame:
        """Generate time series pricing data."""
        if materials is None:
            materials = ['MAT001', 'MAT002', 'MAT003', 'MAT004', 'MAT005']
        
        date_range = pd.date_range(start='2023-01-01', periods=n_days, freq='D')
        data = []
        
        for material in materials:
            base_price = np.random.uniform(50, 2000)
            trend = np.random.uniform(-0.001, 0.001)  # Daily trend
            volatility = np.random.uniform(0.01, 0.05)  # Daily volatility
            
            prices = []
            current_price = base_price
            
            for i, date in enumerate(date_range):
                # Add trend
                current_price *= (1 + trend)
                
                # Add seasonal effect
                seasonal_factor = 1 + 0.05 * np.sin(2 * np.pi * i / 365)
                current_price *= seasonal_factor
                
                # Add volatility
                current_price *= (1 + np.random.normal(0, volatility))
                
                # Ensure price doesn't go negative
                current_price = max(0.01, current_price)
                
                record = {
                    'date': date,
                    'material_id': material,
                    'price': round(current_price, 2),
                    'volume': np.random.randint(100, 5000),
                    'high': round(current_price * (1 + np.random.uniform(0, 0.02)), 2),
                    'low': round(current_price * (1 - np.random.uniform(0, 0.02)), 2),
                    'volatility': volatility
                }
                data.append(record)
        
        return pd.DataFrame(data)
    
    def generate_feature_engineering_data(self, n_samples: int = 1000) -> pd.DataFrame:
        """Generate data for testing feature engineering."""
        data = []
        
        for _ in range(n_samples):
            record = {
                # Categorical features
                'material_type': np.random.choice(['steel', 'aluminum', 'plastic']),
                'supplier_location': np.random.choice(['domestic', 'international']),
                'quality_rating': np.random.choice(['A', 'B', 'C']),
                
                # Numerical features
                'quantity': np.random.randint(1, 10000),
                'weight': np.random.uniform(0.1, 1000),
                'dimensions_x': np.random.uniform(1, 100),
                'dimensions_y': np.random.uniform(1, 100),
                'dimensions_z': np.random.uniform(1, 50),
                
                # Date features
                'order_date': pd.Timestamp('2023-01-01') + pd.Timedelta(days=np.random.randint(0, 365)),
                'delivery_date': pd.Timestamp('2023-01-01') + pd.Timedelta(days=np.random.randint(7, 400)),
                
                # Text features
                'description': f"Material description {np.random.randint(1000, 9999)}",
                'specifications': f"Spec-{np.random.choice(['A', 'B', 'C'])}-{np.random.randint(100, 999)}",
                
                # Boolean features
                'rush_order': np.random.choice([True, False]),
                'certified': np.random.choice([True, False]),
                'custom': np.random.choice([True, False]),
            }
            
            # Calculate target based on features
            price = 100  # Base price
            
            # Material type effect
            material_multipliers = {'steel': 1.0, 'aluminum': 1.5, 'plastic': 0.3}
            price *= material_multipliers[record['material_type']]
            
            # Quantity discount
            if record['quantity'] > 5000:
                price *= 0.85
            elif record['quantity'] > 1000:
                price *= 0.95
            
            # Quality premium
            quality_multipliers = {'A': 1.2, 'B': 1.0, 'C': 0.9}
            price *= quality_multipliers[record['quality_rating']]
            
            # Rush order premium
            if record['rush_order']:
                price *= 1.3
            
            # Add noise
            price *= (1 + np.random.normal(0, 0.1))
            
            record['price'] = max(1.0, round(price, 2))
            data.append(record)
        
        return pd.DataFrame(data)
    
    def generate_drift_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Generate reference and drifted datasets for drift detection testing."""
        # Reference dataset (normal distribution)
        reference_data = pd.DataFrame({
            'feature_1': np.random.normal(10, 2, 1000),
            'feature_2': np.random.exponential(5, 1000),
            'feature_3': np.random.uniform(0, 100, 1000),
            'feature_4': np.random.gamma(2, 2, 1000),
            'categorical': np.random.choice(['A', 'B', 'C'], 1000, p=[0.5, 0.3, 0.2])
        })
        
        # Drifted dataset (shifted distributions)
        drifted_data = pd.DataFrame({
            'feature_1': np.random.normal(12, 3, 500),  # Mean and std changed
            'feature_2': np.random.exponential(7, 500),  # Scale changed
            'feature_3': np.random.uniform(20, 120, 500),  # Range shifted
            'feature_4': np.random.gamma(3, 2, 500),  # Shape changed
            'categorical': np.random.choice(['A', 'B', 'C'], 500, p=[0.2, 0.3, 0.5])  # Distribution changed
        })
        
        return reference_data, drifted_data
    
    def save_test_datasets(self, output_dir: str = "test_data"):
        """Save all test datasets to files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Generate and save datasets
        datasets = {
            'pricing_data': self.generate_pricing_dataset(1000),
            'time_series_data': self.generate_time_series_data(365),
            'feature_engineering_data': self.generate_feature_engineering_data(500)
        }
        
        for name, data in datasets.items():
            filepath = output_path / f"{name}.csv"
            data.to_csv(filepath, index=False)
            print(f"Saved {name} to {filepath}")
        
        # Save drift datasets
        ref_data, drift_data = self.generate_drift_data()
        ref_data.to_csv(output_path / "reference_data.csv", index=False)
        drift_data.to_csv(output_path / "drifted_data.csv", index=False)
        
        return output_path


class MLModelFixtures:
    """Fixtures for ML models and related objects."""
    
    @staticmethod
    def create_dummy_model():
        """Create a dummy ML model for testing."""
        from sklearn.ensemble import RandomForestRegressor
        
        # Generate simple training data
        X, y = make_regression(n_samples=100, n_features=5, random_state=42)
        
        model = RandomForestRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)
        
        return model, X, y
    
    @staticmethod
    def create_model_metadata() -> Dict[str, Any]:
        """Create model metadata for testing."""
        return {
            'model_name': 'test_pricing_model',
            'version': '1.0.0',
            'created_at': '2024-01-15T10:00:00Z',
            'training_data_size': 10000,
            'features': [
                'material_type', 'grade', 'quantity', 'thickness',
                'width', 'length', 'supplier_tier', 'lead_time'
            ],
            'target': 'price_per_unit',
            'performance_metrics': {
                'mae': 45.2,
                'mse': 3250.8,
                'r2': 0.87,
                'mape': 0.12
            },
            'hyperparameters': {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'learning_rate': 0.1
            },
            'feature_importance': {
                'material_type': 0.25,
                'quantity': 0.20,
                'grade': 0.15,
                'thickness': 0.12,
                'supplier_tier': 0.10,
                'width': 0.08,
                'length': 0.06,
                'lead_time': 0.04
            }
        }
    
    @staticmethod
    def save_dummy_model(filepath: str = "test_model.pkl"):
        """Save a dummy model to file."""
        model, X, y = MLModelFixtures.create_dummy_model()
        
        model_package = {
            'model': model,
            'feature_names': [f'feature_{i}' for i in range(X.shape[1])],
            'metadata': MLModelFixtures.create_model_metadata()
        }
        
        joblib.dump(model_package, filepath)
        return filepath


class APITestDataFixtures:
    """Fixtures for API testing."""
    
    @staticmethod
    def prediction_request_valid():
        """Valid prediction request."""
        return {
            "material_specifications": {
                "material_type": "steel",
                "grade": "A36",
                "thickness": 10.0,
                "width": 1000.0,
                "length": 2000.0
            },
            "quantity": 100,
            "delivery_location": "New York, NY",
            "delivery_date": "2024-12-31",
            "supplier_preferences": {
                "tier": 1,
                "certified_only": True
            },
            "features": {
                "urgency": "normal",
                "payment_terms": "net_30",
                "quality_requirements": ["ISO9001"]
            }
        }
    
    @staticmethod
    def prediction_request_invalid():
        """Invalid prediction request for testing validation."""
        return {
            "material_specifications": {
                "material_type": "unknown_material",
                "grade": "",
                "thickness": -5.0,  # Invalid negative value
                "width": 0,  # Invalid zero value
                "length": "invalid"  # Invalid string value
            },
            "quantity": -100,  # Invalid negative quantity
            "delivery_date": "invalid-date",
            "features": {}
        }
    
    @staticmethod
    def batch_prediction_request():
        """Batch prediction request."""
        return {
            "requests": [
                APITestDataFixtures.prediction_request_valid(),
                {
                    "material_specifications": {
                        "material_type": "aluminum",
                        "grade": "6061",
                        "thickness": 5.0,
                        "width": 500.0,
                        "length": 1000.0
                    },
                    "quantity": 50,
                    "delivery_location": "Los Angeles, CA"
                }
            ]
        }
    
    @staticmethod
    def training_request():
        """Model training request."""
        return {
            "model_name": "test_training_model",
            "model_type": "random_forest",
            "data_source": "test_dataset",
            "features": [
                "material_type", "grade", "thickness", "width", 
                "length", "quantity", "supplier_tier"
            ],
            "target": "price_per_unit",
            "hyperparameters": {
                "n_estimators": 50,
                "max_depth": 8,
                "min_samples_split": 5
            },
            "validation_split": 0.2,
            "cross_validation": {
                "enabled": True,
                "folds": 5
            }
        }


def load_test_fixtures():
    """Load all test fixtures and return as dictionary."""
    generator = MLTestDataGenerator()
    
    fixtures = {
        'pricing_data': generator.generate_pricing_dataset(100),
        'time_series_data': generator.generate_time_series_data(30),
        'feature_data': generator.generate_feature_engineering_data(100),
        'drift_data': generator.generate_drift_data(),
        'model_fixtures': MLModelFixtures(),
        'api_fixtures': APITestDataFixtures()
    }
    
    return fixtures


if __name__ == "__main__":
    # Generate test data when run directly
    generator = MLTestDataGenerator()
    output_dir = generator.save_test_datasets()
    
    # Save dummy model
    model_path = MLModelFixtures.save_dummy_model(output_dir / "test_model.pkl")
    
    print(f"Test data and model saved to: {output_dir}")
    print("Available fixtures:")
    for name in load_test_fixtures().keys():
        print(f"  - {name}")
"""
File Parser Service for handling CSV, Excel, and Parquet files
"""
import pandas as pd
import io
import json
from typing import Dict, List, Tuple, Any, Optional
from django.core.files.uploadedfile import UploadedFile
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """
    Parse uploaded procurement data files and detect schemas
    """
    
    # Common procurement column patterns
    COLUMN_PATTERNS = {
        'supplier': [
            'supplier', 'vendor', 'supplier_name', 'vendor_name', 
            'supplier_code', 'vendor_code', 'supplier_id', 'vendor_id'
        ],
        'material': [
            'material', 'item', 'product', 'sku', 'part_number',
            'material_code', 'item_code', 'product_code', 'material_id'
        ],
        'description': [
            'description', 'item_description', 'material_description',
            'product_description', 'desc', 'item_desc'
        ],
        'quantity': [
            'quantity', 'qty', 'amount', 'volume', 'order_quantity',
            'ordered_qty', 'purchase_qty'
        ],
        'unit_price': [
            'unit_price', 'price', 'unit_cost', 'price_per_unit',
            'cost_per_unit', 'rate'
        ],
        'total_price': [
            'total_price', 'total', 'total_cost', 'amount', 'net_amount',
            'line_total', 'extended_price'
        ],
        'currency': [
            'currency', 'curr', 'currency_code'
        ],
        'po_number': [
            'po_number', 'purchase_order', 'po', 'order_number',
            'po_num', 'purchase_order_number'
        ],
        'date': [
            'date', 'order_date', 'purchase_date', 'po_date',
            'transaction_date', 'created_date'
        ],
        'uom': [
            'uom', 'unit', 'unit_of_measure', 'units', 'measurement_unit'
        ]
    }
    
    def __init__(self):
        self.data = None
        self.file_format = None
        self.detected_schema = {}
        
    def parse_file(self, file: UploadedFile, file_format: str) -> Tuple[pd.DataFrame, Dict]:
        """
        Parse uploaded file and return DataFrame with detected schema
        
        Args:
            file: Django UploadedFile object
            file_format: File format (csv, xlsx, xls, parquet)
            
        Returns:
            Tuple of (DataFrame, detected_schema_dict)
        """
        self.file_format = file_format
        
        try:
            if file_format == 'csv':
                self.data = self._parse_csv(file)
            elif file_format in ['xlsx', 'xls']:
                self.data = self._parse_excel(file)
            elif file_format == 'parquet':
                self.data = self._parse_parquet(file)
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
                
            # Detect schema
            self.detected_schema = self._detect_schema()
            
            # Basic data cleaning
            self.data = self._clean_data()
            
            return self.data, self.detected_schema
            
        except Exception as e:
            logger.error(f"Error parsing file: {str(e)}")
            raise
    
    def _parse_csv(self, file: UploadedFile) -> pd.DataFrame:
        """Parse CSV file with encoding detection"""
        # Try different encodings
        encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings:
            try:
                file.seek(0)
                return pd.read_csv(file, encoding=encoding, low_memory=False)
            except UnicodeDecodeError:
                continue
            except Exception as e:
                if encoding == encodings[-1]:
                    raise e
                    
        raise ValueError("Unable to detect file encoding")
    
    def _parse_excel(self, file: UploadedFile) -> pd.DataFrame:
        """Parse Excel file"""
        file.seek(0)
        excel_file = pd.ExcelFile(file)
        
        # If multiple sheets, use the first one or the one with most data
        if len(excel_file.sheet_names) > 1:
            sheet_data = {}
            for sheet in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet)
                if not df.empty:
                    sheet_data[sheet] = len(df)
            
            # Use sheet with most rows
            target_sheet = max(sheet_data, key=sheet_data.get)
            logger.info(f"Multiple sheets found. Using '{target_sheet}' with {sheet_data[target_sheet]} rows")
            return pd.read_excel(excel_file, sheet_name=target_sheet)
        else:
            return pd.read_excel(excel_file)
    
    def _parse_parquet(self, file: UploadedFile) -> pd.DataFrame:
        """Parse Parquet file"""
        file.seek(0)
        return pd.read_parquet(io.BytesIO(file.read()))
    
    def _detect_schema(self) -> Dict:
        """
        Detect column types and suggest mappings
        """
        schema = {
            'columns': {},
            'suggested_mappings': {},
            'data_types': {},
            'sample_values': {}
        }
        
        for col in self.data.columns:
            col_lower = str(col).lower().strip()
            
            # Detect data type
            dtype = str(self.data[col].dtype)
            schema['data_types'][col] = dtype
            
            # Get sample values (first 5 non-null values)
            sample = self.data[col].dropna().head(5).tolist()
            schema['sample_values'][col] = sample
            
            # Suggest mapping based on column name
            for field, patterns in self.COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if pattern in col_lower:
                        schema['suggested_mappings'][col] = field
                        break
                if col in schema['suggested_mappings']:
                    break
            
            # Column info
            schema['columns'][col] = {
                'original_name': col,
                'data_type': dtype,
                'null_count': int(self.data[col].isna().sum()),
                'unique_count': int(self.data[col].nunique()),
                'suggested_mapping': schema['suggested_mappings'].get(col, None)
            }
        
        return schema
    
    def _clean_data(self) -> pd.DataFrame:
        """
        Basic data cleaning
        """
        df = self.data.copy()
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Strip whitespace from string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' string with actual NaN
                df[col] = df[col].replace('nan', pd.NA)
        
        # Remove duplicate header rows (sometimes Excel exports have this)
        if len(df) > 1:
            first_row = df.iloc[0]
            if all(str(val).lower() == str(col).lower() 
                   for val, col in zip(first_row, df.columns) 
                   if pd.notna(val)):
                df = df.iloc[1:].reset_index(drop=True)
        
        return df
    
    def validate_required_fields(self, mapped_columns: Dict) -> List[str]:
        """
        Validate that minimum required fields are mapped
        """
        errors = []
        
        # Minimum required fields for procurement data
        required_fields = ['supplier', 'material', 'quantity', 'unit_price']
        
        for field in required_fields:
            if field not in mapped_columns.values():
                errors.append(f"Required field '{field}' is not mapped")
        
        return errors
    
    def get_preview_data(self, num_rows: int = 10) -> List[Dict]:
        """
        Get preview of parsed data
        """
        if self.data is None:
            return []
        
        preview_df = self.data.head(num_rows)
        return preview_df.to_dict('records')


class SchemaDetector:
    """
    Advanced schema detection using ML patterns
    """
    
    @staticmethod
    def detect_date_columns(df: pd.DataFrame) -> List[str]:
        """Detect columns that likely contain dates"""
        date_columns = []
        
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to parse as date
                try:
                    pd.to_datetime(df[col], errors='coerce')
                    non_null_dates = pd.to_datetime(df[col], errors='coerce').notna().sum()
                    if non_null_dates > len(df) * 0.5:  # At least 50% valid dates
                        date_columns.append(col)
                except:
                    pass
        
        return date_columns
    
    @staticmethod
    def detect_currency_columns(df: pd.DataFrame) -> List[str]:
        """Detect columns that likely contain currency values"""
        currency_columns = []
        currency_symbols = ['$', '€', '£', '¥', '₹']
        
        for col in df.columns:
            if df[col].dtype == 'object':
                sample = df[col].dropna().astype(str).head(100)
                if any(symbol in ''.join(sample) for symbol in currency_symbols):
                    currency_columns.append(col)
            elif pd.api.types.is_numeric_dtype(df[col]):
                # Check if column name suggests currency
                col_lower = str(col).lower()
                if any(term in col_lower for term in ['price', 'cost', 'amount', 'value']):
                    currency_columns.append(col)
        
        return currency_columns
    
    @staticmethod
    def detect_code_columns(df: pd.DataFrame) -> List[str]:
        """Detect columns that likely contain codes (supplier codes, material codes, etc.)"""
        code_columns = []
        
        for col in df.columns:
            if df[col].dtype == 'object':
                sample = df[col].dropna().head(100)
                # Check for code-like patterns (alphanumeric, consistent length, etc.)
                if sample.str.match(r'^[A-Z0-9\-\_]+$').sum() > len(sample) * 0.7:
                    code_columns.append(col)
        
        return code_columns
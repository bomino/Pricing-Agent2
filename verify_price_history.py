"""
Quick script to verify price history implementation
Run this after uploading test_procurement_data.csv
"""
import os
import sys
import django

# Add Django app to path
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from apps.pricing.models import Price, Material
from apps.procurement.models import Supplier, PurchaseOrder
from apps.data_ingestion.models import DataUpload

def verify_implementation():
    print("\n" + "="*60)
    print("PRICE HISTORY VERIFICATION")
    print("="*60)

    # Check counts
    prices = Price.objects.all()
    suppliers = Supplier.objects.all()
    materials = Material.objects.all()
    pos = PurchaseOrder.objects.all()
    uploads = DataUpload.objects.filter(status='completed')

    print(f"\n[OK] Total Prices: {prices.count()}")
    print(f"[OK] Total Suppliers: {suppliers.count()}")
    print(f"[OK] Total Materials: {materials.count()}")
    print(f"[OK] Total POs: {pos.count()}")
    print(f"[OK] Completed Uploads: {uploads.count()}")

    if prices.exists():
        print("\n" + "-"*40)
        print("PRICE RECORDS DETAIL:")
        print("-"*40)
        for price in prices[:5]:  # Show first 5
            print(f"\n{price.material.name if price.material else 'Unknown'}:")
            print(f"  - Price: ${price.price}")
            print(f"  - Date: {price.time.date()}")
            print(f"  - Supplier: {price.supplier.name if price.supplier else 'N/A'}")
            if price.metadata:
                print(f"  - PO Number: {price.metadata.get('po_number', 'N/A')}")

        # Check metadata
        first_price = prices.first()
        if first_price and first_price.metadata:
            print("\n" + "-"*40)
            print("METADATA STRUCTURE:")
            print("-"*40)
            print(f"Sample metadata: {first_price.metadata}")

        print("\n[SUCCESS] PHASE 1 COMPLETE: Price history is being recorded!")

    else:
        print("\n[WARNING] No price records found yet. Upload test data first.")

    # Check for analytics availability
    print("\n" + "-"*40)
    print("ANALYTICS READINESS:")
    print("-"*40)
    if prices.exists():
        print("[OK] Historical prices available for:")
        print("  - Trend analysis")
        print("  - Variance detection")
        print("  - ML model training")
        print("  - Benchmarking")
    else:
        print("[WARNING] Waiting for price data...")

if __name__ == "__main__":
    verify_implementation()
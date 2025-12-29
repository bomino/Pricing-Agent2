"""
Quick check for new price records after upload
"""
import os
import sys
import django

# Add Django app to path
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from apps.pricing.models import Price

# Check current count
current_count = Price.objects.count()
print(f"\nTotal Price Records: {current_count}")

if current_count == 520:
    print("[WAITING] Upload test_procurement_data.csv to add 5 new records")
elif current_count == 525:
    print("[SUCCESS] All 5 test records were added successfully!")

    # Show the newest 5 records
    newest_prices = Price.objects.order_by('-created_at')[:5]
    print("\nNewest Price Records:")
    print("-" * 40)
    for p in newest_prices:
        material_name = p.material.name if p.material else "Unknown"
        supplier_name = p.supplier.name if p.supplier else "N/A"
        print(f"{material_name}: ${p.price} from {supplier_name}")
elif current_count > 520:
    diff = current_count - 520
    print(f"[INFO] {diff} new records added since baseline (520)")
else:
    print(f"[INFO] Current count: {current_count}")
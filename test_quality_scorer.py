"""
Simple test for data quality scorer
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from apps.data_ingestion.models import DataUpload
from apps.data_ingestion.services.data_quality_scorer import DataQualityScorer

def test_scorer():
    print("Testing Data Quality Scorer")

    # Get the latest upload
    upload = DataUpload.objects.filter(status='ready_to_process').last()

    if not upload:
        print("No upload found")
        return

    print(f"Testing with upload: {upload.id}")
    print(f"Upload filename: {upload.original_filename}")

    try:
        scorer = DataQualityScorer()
        result = scorer.score_upload(str(upload.id))

        print(f"\nResult:")
        for key, value in result.items():
            if key == 'dimension_scores' and isinstance(value, dict):
                print(f"  {key}:")
                for dim, score in value.items():
                    print(f"    {dim}: {score}")
            else:
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Using LOCAL settings with SQLite database")
    test_scorer()
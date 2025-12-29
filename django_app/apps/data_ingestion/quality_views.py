"""
Views for data quality scoring and visualization
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import DataUpload
from .services.data_quality_scorer import DataQualityScorer
import json


@login_required
def data_quality_report(request, upload_id):
    """Display comprehensive data quality report"""
    upload = get_object_or_404(DataUpload, id=upload_id)

    # Generate quality score
    scorer = DataQualityScorer()
    quality_report = scorer.score_upload(upload_id)

    context = {
        'upload': upload,
        'report': quality_report,
        'dimension_scores_json': json.dumps(quality_report.get('dimension_scores', {})),
    }

    return render(request, 'data_ingestion/quality_report.html', context)


@login_required
def quality_score_api(request, upload_id):
    """API endpoint for getting quality scores"""
    try:
        upload = DataUpload.objects.get(id=upload_id)

        # Generate quality score
        scorer = DataQualityScorer()
        quality_report = scorer.score_upload(upload_id)

        return JsonResponse(quality_report)

    except DataUpload.DoesNotExist:
        return JsonResponse({'error': 'Upload not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
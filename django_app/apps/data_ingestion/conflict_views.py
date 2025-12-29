"""
Views for handling fuzzy matching conflict resolution
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.paginator import Paginator
from .models import DataUpload, MatchingConflict
from apps.procurement.models import Supplier
from apps.pricing.models import Material
import json


@login_required
def conflict_list(request, upload_id):
    """Display all pending conflicts for an upload"""
    upload = get_object_or_404(DataUpload, id=upload_id)

    # Get filter parameters
    conflict_type = request.GET.get('type', '')
    status = request.GET.get('status', 'pending')

    # Base queryset
    conflicts = upload.conflicts.all()

    # Apply filters
    if conflict_type:
        conflicts = conflicts.filter(conflict_type=conflict_type)
    if status:
        conflicts = conflicts.filter(status=status)

    # Statistics
    stats = {
        'total': upload.conflicts.count(),
        'pending': upload.conflicts.filter(status='pending').count(),
        'resolved': upload.conflicts.exclude(status='pending').count(),
        'supplier_conflicts': upload.conflicts.filter(conflict_type='supplier').count(),
        'material_conflicts': upload.conflicts.filter(conflict_type='material').count(),
        'auto_resolved': upload.conflicts.filter(status='auto_resolved').count(),
    }

    # Pagination
    paginator = Paginator(conflicts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'upload': upload,
        'page_obj': page_obj,
        'stats': stats,
        'current_type': conflict_type,
        'current_status': status,
    }

    return render(request, 'data_ingestion/conflict_list.html', context)


@login_required
def conflict_detail(request, conflict_id):
    """Display detailed view of a single conflict for resolution"""
    conflict = get_object_or_404(MatchingConflict, id=conflict_id)

    # Get additional context for resolution
    if conflict.conflict_type == 'supplier':
        # Get existing suppliers for comparison
        existing_suppliers = Supplier.objects.all()[:10]  # Show top 10 for context
        context_data = existing_suppliers
    else:
        # Get existing materials for comparison
        existing_materials = Material.objects.all()[:10]  # Show top 10 for context
        context_data = existing_materials

    context = {
        'conflict': conflict,
        'context_data': context_data,
        'staging_data': conflict.staging_record.raw_data if conflict.staging_record else {},
    }

    return render(request, 'data_ingestion/conflict_detail.html', context)


@login_required
@require_POST
def resolve_conflict(request, conflict_id):
    """Handle conflict resolution"""
    conflict = get_object_or_404(MatchingConflict, id=conflict_id)

    resolution_type = request.POST.get('resolution_type')
    matched_id = request.POST.get('matched_id')
    notes = request.POST.get('notes', '')

    if resolution_type == 'match' and matched_id:
        # Resolve as match to existing record
        conflict.resolve_as_match(matched_id, user=request.user)
        conflict.resolution_notes = notes
        conflict.save()

    elif resolution_type == 'new':
        # Resolve as new record
        conflict.resolve_as_new(user=request.user)
        conflict.resolution_notes = notes
        conflict.save()

    # Check if there are more conflicts to resolve
    next_conflict = MatchingConflict.objects.filter(
        upload=conflict.upload,
        status='pending'
    ).first()

    if next_conflict:
        return redirect('data_ingestion:conflict_detail', conflict_id=next_conflict.id)
    else:
        return redirect('data_ingestion:conflict_list', upload_id=conflict.upload.id)


@login_required
@require_POST
def bulk_resolve_conflicts(request):
    """Handle bulk resolution of conflicts"""
    conflict_ids = request.POST.getlist('conflict_ids')
    action = request.POST.get('action')

    conflicts = MatchingConflict.objects.filter(id__in=conflict_ids, status='pending')

    if action == 'auto_resolve':
        # Try to auto-resolve conflicts with high similarity
        resolved_count = 0
        for conflict in conflicts:
            if conflict.auto_resolve():
                resolved_count += 1

        return JsonResponse({
            'success': True,
            'resolved': resolved_count,
            'message': f'Auto-resolved {resolved_count} conflicts'
        })

    elif action == 'mark_as_new':
        # Mark all selected as new records
        for conflict in conflicts:
            conflict.resolve_as_new(user=request.user)

        return JsonResponse({
            'success': True,
            'resolved': conflicts.count(),
            'message': f'Marked {conflicts.count()} conflicts as new records'
        })

    return JsonResponse({'success': False, 'message': 'Invalid action'})


@login_required
def conflict_resolution_api(request, conflict_id):
    """API endpoint for AJAX-based conflict resolution"""
    if request.method == 'GET':
        conflict = get_object_or_404(MatchingConflict, id=conflict_id)

        # Return conflict details as JSON
        data = {
            'id': str(conflict.id),
            'type': conflict.conflict_type,
            'status': conflict.status,
            'incoming_value': conflict.incoming_value,
            'incoming_code': conflict.incoming_code,
            'potential_matches': conflict.potential_matches,
            'highest_similarity': conflict.highest_similarity,
            'staging_data': conflict.staging_record.raw_data if conflict.staging_record else {},
        }

        return JsonResponse(data)

    elif request.method == 'POST':
        conflict = get_object_or_404(MatchingConflict, id=conflict_id)

        try:
            body = json.loads(request.body)
            resolution_type = body.get('resolution_type')
            matched_id = body.get('matched_id')
            notes = body.get('notes', '')

            if resolution_type == 'match' and matched_id:
                conflict.resolve_as_match(matched_id, user=request.user)
                conflict.resolution_notes = notes
                conflict.save()
                message = 'Resolved as match'

            elif resolution_type == 'new':
                conflict.resolve_as_new(user=request.user)
                conflict.resolution_notes = notes
                conflict.save()
                message = 'Resolved as new record'

            else:
                return JsonResponse({'success': False, 'message': 'Invalid resolution type'})

            # Get next pending conflict
            next_conflict = MatchingConflict.objects.filter(
                upload=conflict.upload,
                status='pending'
            ).first()

            return JsonResponse({
                'success': True,
                'message': message,
                'next_conflict_id': str(next_conflict.id) if next_conflict else None
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Method not allowed'})
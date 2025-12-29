"""
Models for handling conflict resolution in fuzzy matching
"""
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from apps.procurement.models import Supplier
from apps.pricing.models import Material

User = get_user_model()


class MatchingConflict(BaseModel):
    """Records potential duplicate matches that need user resolution"""

    CONFLICT_TYPES = [
        ('supplier', 'Supplier Match'),
        ('material', 'Material Match'),
    ]

    RESOLUTION_STATUS = [
        ('pending', 'Pending Review'),
        ('resolved_match', 'Confirmed as Match'),
        ('resolved_new', 'Confirmed as New'),
        ('auto_resolved', 'Auto-Resolved'),
    ]

    upload = models.ForeignKey(
        'DataUpload',
        on_delete=models.CASCADE,
        related_name='conflicts'
    )
    staging_record = models.ForeignKey(
        'ProcurementDataStaging',
        on_delete=models.CASCADE,
        related_name='conflicts'
    )

    conflict_type = models.CharField(
        max_length=20,
        choices=CONFLICT_TYPES
    )
    status = models.CharField(
        max_length=20,
        choices=RESOLUTION_STATUS,
        default='pending'
    )

    # The incoming value that triggered the conflict
    incoming_value = models.CharField(max_length=255)
    incoming_code = models.CharField(max_length=100, blank=True, null=True)

    # Potential matches found (stored as JSON)
    potential_matches = models.JSONField(default=list)
    # Example: [
    #   {"id": "uuid", "name": "Supplier A", "code": "SUP001", "similarity": 0.92},
    #   {"id": "uuid", "name": "Supplier B", "code": "SUP002", "similarity": 0.85}
    # ]

    # Resolution details
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_conflicts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # If matched to existing record
    matched_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    matched_material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Confidence scores
    highest_similarity = models.FloatField(default=0.0)
    auto_resolve_threshold = models.FloatField(default=0.95)

    class Meta:
        ordering = ['-highest_similarity', 'created_at']
        indexes = [
            models.Index(fields=['upload', 'status']),
            models.Index(fields=['conflict_type', 'status']),
        ]

    def __str__(self):
        return f"{self.conflict_type} conflict: {self.incoming_value} ({self.status})"

    def resolve_as_match(self, matched_id, user=None):
        """Resolve conflict as a match to existing record"""
        from datetime import datetime

        self.status = 'resolved_match'
        self.resolved_by = user
        self.resolved_at = datetime.now()

        if self.conflict_type == 'supplier':
            self.matched_supplier_id = matched_id
        elif self.conflict_type == 'material':
            self.matched_material_id = matched_id

        self.save()

    def resolve_as_new(self, user=None):
        """Resolve conflict as a new record (not a match)"""
        from datetime import datetime

        self.status = 'resolved_new'
        self.resolved_by = user
        self.resolved_at = datetime.now()
        self.save()

    def auto_resolve(self):
        """Auto-resolve if similarity is above threshold"""
        if self.potential_matches and self.highest_similarity >= self.auto_resolve_threshold:
            best_match = max(self.potential_matches, key=lambda x: x.get('similarity', 0))
            self.resolve_as_match(best_match['id'])
            self.status = 'auto_resolved'
            self.save()
            return True
        return False
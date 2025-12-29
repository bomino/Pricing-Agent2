"""
Data Quality Scoring Service
Evaluates the quality of uploaded data based on completeness, consistency, and validity
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Avg, Count, StdDev, Q
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.pricing.models import Price, Material
from apps.procurement.models import Supplier
import logging

logger = logging.getLogger(__name__)


class DataQualityScorer:
    """
    Scores data quality on multiple dimensions:
    1. Completeness - Are all required fields present?
    2. Consistency - Do values follow expected patterns?
    3. Validity - Are values within reasonable ranges?
    4. Timeliness - How recent is the data?
    5. Uniqueness - Are there duplicate records?
    6. Accuracy - Do prices align with historical norms?
    """

    # Weights for different quality dimensions (sum to 1.0)
    WEIGHTS = {
        'completeness': 0.25,
        'consistency': 0.20,
        'validity': 0.20,
        'timeliness': 0.15,
        'uniqueness': 0.10,
        'accuracy': 0.10
    }

    # Required fields for high quality data
    REQUIRED_FIELDS = [
        'po_number', 'supplier_name', 'material_description',
        'unit_price', 'quantity', 'purchase_date'
    ]

    # Optional but valuable fields
    VALUABLE_FIELDS = [
        'supplier_code', 'material_code', 'delivery_date',
        'currency', 'unit_of_measure', 'payment_terms'
    ]

    def __init__(self):
        self.scores = {}
        self.details = {}
        self.recommendations = []

    def score_upload(self, upload_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive quality score for an upload
        """
        try:
            upload = DataUpload.objects.get(id=upload_id)
            staging_records = ProcurementDataStaging.objects.filter(upload=upload)

            if not staging_records.exists():
                return {
                    'overall_score': 0,
                    'message': 'No records to evaluate'
                }

            # Calculate individual dimension scores (with error handling for each)
            try:
                self.scores['completeness'] = self._score_completeness(staging_records)
            except Exception as e:
                logger.warning(f"Error in completeness scoring: {e}")
                self.scores['completeness'] = 0

            try:
                self.scores['consistency'] = self._score_consistency(staging_records)
            except Exception as e:
                logger.warning(f"Error in consistency scoring: {e}")
                self.scores['consistency'] = 0

            try:
                self.scores['validity'] = self._score_validity(staging_records)
            except Exception as e:
                logger.warning(f"Error in validity scoring: {e}")
                self.scores['validity'] = 0

            try:
                self.scores['timeliness'] = self._score_timeliness(staging_records)
            except Exception as e:
                logger.warning(f"Error in timeliness scoring: {e}")
                self.scores['timeliness'] = 0

            try:
                self.scores['uniqueness'] = self._score_uniqueness(staging_records)
            except Exception as e:
                logger.warning(f"Error in uniqueness scoring: {e}")
                self.scores['uniqueness'] = 0

            try:
                self.scores['accuracy'] = self._score_accuracy(staging_records, upload.organization)
            except Exception as e:
                logger.warning(f"Error in accuracy scoring: {e}")
                self.scores['accuracy'] = 0

            # Calculate weighted overall score
            overall_score = sum(
                self.scores[dim] * self.WEIGHTS[dim]
                for dim in self.WEIGHTS
            )

            # Ensure overall_score is a valid number
            if not isinstance(overall_score, (int, float)) or overall_score != overall_score:  # NaN check
                overall_score = 0.0

            overall_score = max(0, min(100, overall_score))  # Clamp to 0-100

            # Generate recommendations based on scores
            self._generate_recommendations()

            # Determine quality grade
            grade = self._get_quality_grade(overall_score)

            # Update upload with quality score (with error handling)
            try:
                upload.data_quality_score = Decimal(str(round(overall_score, 2)))
                upload.save()
            except Exception as save_error:
                logger.warning(f"Could not save quality score to upload: {save_error}")

            return {
                'overall_score': round(overall_score, 2),
                'grade': grade,
                'dimension_scores': self.scores,
                'details': self.details,
                'recommendations': self.recommendations,
                'record_count': staging_records.count(),
                'upload_id': str(upload_id)
            }

        except Exception as e:
            logger.error(f"Error scoring upload {upload_id}: {str(e)}")
            return {
                'overall_score': 0,
                'error': str(e)
            }

    def _score_completeness(self, records) -> float:
        """Score based on field completeness"""
        if not records.exists():
            return 0.0

        record_count = records.count()
        total_fields = len(self.REQUIRED_FIELDS) * record_count
        filled_fields = 0

        field_completion = {}
        for field in self.REQUIRED_FIELDS:
            count = records.exclude(
                Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})
            ).count()
            field_completion[field] = (count / record_count * 100) if record_count > 0 else 0
            filled_fields += count

        # Bonus for valuable optional fields
        bonus_points = 0
        for field in self.VALUABLE_FIELDS:
            count = records.exclude(
                Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})
            ).count()
            bonus_points += (count / record_count) * 0.05 if record_count > 0 else 0  # 5% bonus per field

        completeness_score = (filled_fields / total_fields) * 100 if total_fields > 0 else 0
        completeness_score = min(100, completeness_score + (bonus_points * 100))

        self.details['completeness'] = {
            'score': completeness_score,
            'field_completion': field_completion,
            'missing_critical': [
                f for f, pct in field_completion.items() if pct < 50
            ]
        }

        return completeness_score

    def _score_consistency(self, records) -> float:
        """Score based on data consistency patterns"""
        consistency_issues = []
        score = 100

        # Check date consistency
        records_with_dates = records.exclude(
            purchase_date__isnull=True,
            delivery_date__isnull=True
        )

        invalid_date_sequences = 0
        for record in records_with_dates[:100]:  # Sample check
            if record.delivery_date and record.purchase_date:
                if record.delivery_date < record.purchase_date:
                    invalid_date_sequences += 1

        if records_with_dates.count() > 0:
            date_consistency = (1 - invalid_date_sequences / min(100, records_with_dates.count())) * 100
            if date_consistency < 90:
                consistency_issues.append("Delivery dates before purchase dates detected")
                score -= 20

        # Check price consistency
        price_records = records.exclude(unit_price__isnull=True)
        if price_records.exists():
            prices = list(price_records.values_list('unit_price', flat=True))
            if prices:
                avg_price = sum(prices) / len(prices)
                # Check for extreme outliers (10x average)
                outliers = [p for p in prices if p > avg_price * 10 or p < avg_price * 0.1]
                if len(outliers) > len(prices) * 0.05:  # More than 5% outliers
                    consistency_issues.append("Significant price outliers detected")
                    score -= 15

        # Check currency consistency
        currencies = records.values('currency').distinct()
        if currencies.count() > 3:
            consistency_issues.append("Multiple currencies detected (>3)")
            score -= 10

        self.details['consistency'] = {
            'score': max(0, score),
            'issues': consistency_issues
        }

        return max(0, score)

    def _score_validity(self, records) -> float:
        """Score based on data validity"""
        validity_issues = []
        score = 100

        # Check for negative values
        negative_prices = records.filter(unit_price__lt=0).count()
        negative_quantities = records.filter(quantity__lt=0).count()

        if negative_prices > 0:
            validity_issues.append(f"{negative_prices} records with negative prices")
            score -= 25

        if negative_quantities > 0:
            validity_issues.append(f"{negative_quantities} records with negative quantities")
            score -= 25

        # Check for zero values where they shouldn't be
        zero_prices = records.filter(unit_price=0).count()
        zero_quantities = records.filter(quantity=0).count()

        if zero_prices > records.count() * 0.01:  # More than 1%
            validity_issues.append(f"{zero_prices} records with zero prices")
            score -= 10

        if zero_quantities > records.count() * 0.01:
            validity_issues.append(f"{zero_quantities} records with zero quantities")
            score -= 10

        # Check for invalid dates
        future_dates = records.filter(purchase_date__gt=datetime.now().date()).count()
        very_old_dates = records.filter(purchase_date__lt=datetime.now().date() - timedelta(days=1825)).count()  # 5 years

        if future_dates > 0:
            validity_issues.append(f"{future_dates} records with future purchase dates")
            score -= 15

        if very_old_dates > records.count() * 0.1:  # More than 10%
            validity_issues.append(f"{very_old_dates} records older than 5 years")
            score -= 5

        self.details['validity'] = {
            'score': max(0, score),
            'issues': validity_issues
        }

        return max(0, score)

    def _score_timeliness(self, records) -> float:
        """Score based on data recency"""
        score = 100

        dates = list(records.exclude(purchase_date__isnull=True).values_list('purchase_date', flat=True))
        if not dates:
            return 50  # No dates available

        latest_date = max(dates)
        oldest_date = min(dates)
        today = datetime.now().date()

        # Check recency of latest data
        days_old = (today - latest_date).days
        if days_old <= 30:
            recency_score = 100
        elif days_old <= 90:
            recency_score = 80
        elif days_old <= 180:
            recency_score = 60
        elif days_old <= 365:
            recency_score = 40
        else:
            recency_score = 20

        # Check data span
        data_span_days = (latest_date - oldest_date).days
        if data_span_days > 30:
            span_bonus = 10  # Good historical coverage
        else:
            span_bonus = 0

        score = min(100, recency_score + span_bonus)

        self.details['timeliness'] = {
            'score': score,
            'latest_date': str(latest_date),
            'oldest_date': str(oldest_date),
            'days_old': days_old,
            'data_span_days': data_span_days
        }

        return score

    def _score_uniqueness(self, records) -> float:
        """Score based on duplicate detection"""
        score = 100

        # Check for duplicate PO numbers
        po_numbers = records.exclude(po_number__isnull=True).values('po_number').annotate(
            count=Count('po_number')
        ).filter(count__gt=1)

        duplicate_pos = sum(item['count'] - 1 for item in po_numbers)

        if duplicate_pos > 0:
            duplicate_pct = (duplicate_pos / records.count()) * 100
            score = max(0, 100 - duplicate_pct * 2)  # 2% penalty per 1% duplicates

        self.details['uniqueness'] = {
            'score': score,
            'duplicate_records': duplicate_pos,
            'duplicate_percentage': round((duplicate_pos / records.count()) * 100, 2) if records.count() > 0 else 0
        }

        return score

    def _score_accuracy(self, records, organization) -> float:
        """Score based on comparison with historical data"""
        score = 100

        # Get historical price data
        historical_prices = Price.objects.filter(organization=organization)
        if not historical_prices.exists():
            # No historical data to compare
            return 80  # Neutral score

        # Sample check for price reasonableness
        materials_with_history = Material.objects.filter(
            organization=organization,
            prices__isnull=False
        ).distinct()

        outlier_count = 0
        checked_count = 0

        for record in records[:50]:  # Sample check
            if record.material_description and record.unit_price:
                # Try to find similar material in history
                similar_materials = materials_with_history.filter(
                    name__icontains=record.material_description[:20]
                )

                if similar_materials.exists():
                    checked_count += 1
                    # Get average historical price
                    avg_price = Price.objects.filter(
                        material__in=similar_materials
                    ).aggregate(avg=Avg('price'))['avg']

                    if avg_price:
                        # Check if current price is within reasonable range (50%-200% of average)
                        if record.unit_price < avg_price * 0.5 or record.unit_price > avg_price * 2:
                            outlier_count += 1

        if checked_count > 0:
            accuracy_rate = (1 - outlier_count / checked_count) * 100
            score = accuracy_rate
        else:
            score = 85  # Default if no comparison possible

        self.details['accuracy'] = {
            'score': score,
            'checked_records': checked_count,
            'outliers_found': outlier_count
        }

        return score

    def _generate_recommendations(self):
        """Generate actionable recommendations based on scores"""
        self.recommendations = []

        # Completeness recommendations
        if self.scores.get('completeness', 100) < 80:
            missing_fields = self.details.get('completeness', {}).get('missing_critical', [])
            if missing_fields:
                self.recommendations.append({
                    'priority': 'high',
                    'category': 'completeness',
                    'message': f"Critical fields missing data: {', '.join(missing_fields)}",
                    'action': 'Review source data and fill missing required fields'
                })

        # Consistency recommendations
        if self.scores.get('consistency', 100) < 80:
            issues = self.details.get('consistency', {}).get('issues', [])
            for issue in issues[:2]:  # Top 2 issues
                self.recommendations.append({
                    'priority': 'medium',
                    'category': 'consistency',
                    'message': issue,
                    'action': 'Review and correct data inconsistencies'
                })

        # Validity recommendations
        if self.scores.get('validity', 100) < 80:
            issues = self.details.get('validity', {}).get('issues', [])
            for issue in issues[:2]:
                self.recommendations.append({
                    'priority': 'high',
                    'category': 'validity',
                    'message': issue,
                    'action': 'Correct invalid values before processing'
                })

        # Timeliness recommendations
        if self.scores.get('timeliness', 100) < 60:
            days_old = self.details.get('timeliness', {}).get('days_old', 0)
            self.recommendations.append({
                'priority': 'low',
                'category': 'timeliness',
                'message': f"Latest data is {days_old} days old",
                'action': 'Consider uploading more recent data for better insights'
            })

        # Uniqueness recommendations
        if self.scores.get('uniqueness', 100) < 90:
            dup_pct = self.details.get('uniqueness', {}).get('duplicate_percentage', 0)
            self.recommendations.append({
                'priority': 'medium',
                'category': 'uniqueness',
                'message': f"{dup_pct}% duplicate records detected",
                'action': 'Review and remove duplicate entries'
            })

    def _get_quality_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
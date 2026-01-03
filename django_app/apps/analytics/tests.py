"""
Tests for Analytics app views, especially report management functionality.
"""
import json
import uuid
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from apps.core.models import Organization, OrganizationMembership
from apps.analytics.models import Report


class ReportManagementTestCase(TestCase):
    """Base test case with common setup for report management tests."""

    def setUp(self):
        """Set up test data."""
        # Create organization
        self.organization = Organization.objects.create(
            name='Test Organization',
            slug='test-org'
        )

        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create organization membership
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            role='admin'
        )

        # Create test report
        self.report = Report.objects.create(
            organization=self.organization,
            created_by=self.user,
            name='Test Report',
            description='A test report',
            report_type='spend_analysis',
            report_format='csv',
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date(),
            status='completed',
            generated_at=timezone.now(),
        )

        # Set up client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')


class ReportGenerateViewTests(ReportManagementTestCase):
    """Tests for ReportGenerateView."""

    def test_generate_report_success(self):
        """Test successful report generation."""
        url = reverse('analytics:report_generate')
        response = self.client.post(url, {
            'report_type': 'spend_analysis',
        })

        self.assertEqual(response.status_code, 200)
        # Check that a new report was created
        new_report = Report.objects.filter(
            organization=self.organization,
            report_type='spend_analysis'
        ).exclude(id=self.report.id).first()
        self.assertIsNotNone(new_report)
        self.assertEqual(new_report.status, 'completed')

    def test_generate_report_with_date_range(self):
        """Test report generation with custom date range."""
        url = reverse('analytics:report_generate')
        start_date = (timezone.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        end_date = timezone.now().strftime('%Y-%m-%d')

        response = self.client.post(url, {
            'report_type': 'supplier_performance',
            'date_range': f'{start_date} to {end_date}',
        })

        self.assertEqual(response.status_code, 200)

    def test_generate_report_unauthenticated(self):
        """Test that unauthenticated users cannot generate reports."""
        self.client.logout()
        url = reverse('analytics:report_generate')
        response = self.client.post(url, {
            'report_type': 'spend_analysis',
        })

        # Should redirect to login
        self.assertEqual(response.status_code, 302)


class ReportDownloadViewTests(ReportManagementTestCase):
    """Tests for ReportDownloadView."""

    def test_download_csv_report(self):
        """Test downloading report as CSV."""
        url = reverse('analytics:report_download', kwargs={'pk': self.report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_download_pdf_report(self):
        """Test downloading report as PDF."""
        url = reverse('analytics:report_download', kwargs={'pk': self.report.id})
        response = self.client.get(f'{url}?format=pdf')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_download_nonexistent_report(self):
        """Test downloading a report that doesn't exist."""
        fake_uuid = uuid.uuid4()
        url = reverse('analytics:report_download', kwargs={'pk': fake_uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_download_other_org_report(self):
        """Test that users cannot download reports from other organizations."""
        # Create another organization and report
        other_org = Organization.objects.create(
            name='Other Organization',
            slug='other-org'
        )
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        other_report = Report.objects.create(
            organization=other_org,
            created_by=other_user,
            name='Other Report',
            report_type='spend_analysis',
            report_format='csv',
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date(),
            status='completed',
        )

        url = reverse('analytics:report_download', kwargs={'pk': other_report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class ReportsRefreshViewTests(ReportManagementTestCase):
    """Tests for ReportsRefreshView (list refresh, not single report)."""

    def test_refresh_reports_list(self):
        """Test refreshing the reports list."""
        url = reverse('analytics:reports_refresh')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)


class ReportPreviewViewTests(ReportManagementTestCase):
    """Tests for ReportPreviewView (preview modal)."""

    def test_view_report_preview(self):
        """Test viewing report preview."""
        url = reverse('analytics:report_preview', kwargs={'pk': self.report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check template contains report info
        self.assertContains(response, 'Test Report')

    def test_view_nonexistent_report(self):
        """Test viewing a nonexistent report."""
        fake_uuid = uuid.uuid4()
        url = reverse('analytics:report_preview', kwargs={'pk': fake_uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class ReportShareViewTests(ReportManagementTestCase):
    """Tests for ReportShareView."""

    def test_get_share_modal(self):
        """Test getting the share modal."""
        url = reverse('analytics:report_share', kwargs={'pk': self.report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check template renders share modal content
        self.assertContains(response, 'Share', html=False)

    def test_share_report_via_email(self):
        """Test sharing report via email."""
        url = reverse('analytics:report_share', kwargs={'pk': self.report.id})
        response = self.client.post(url, {
            'share_method': 'email',
            'email_addresses': 'recipient@example.com',
            'include_file': True,
        })

        self.assertEqual(response.status_code, 200)

    def test_share_nonexistent_report(self):
        """Test sharing a nonexistent report."""
        fake_uuid = uuid.uuid4()
        url = reverse('analytics:report_share', kwargs={'pk': fake_uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class ReportScheduleViewTests(ReportManagementTestCase):
    """Tests for ReportScheduleView (edit existing schedule)."""

    def setUp(self):
        super().setUp()
        # Make the report scheduled
        self.report.is_scheduled = True
        self.report.schedule_frequency = 'weekly'
        self.report.next_run = timezone.now() + timedelta(days=7)
        self.report.save()

    def test_get_schedule_modal(self):
        """Test getting the schedule edit modal."""
        url = reverse('analytics:report_schedule', kwargs={'pk': self.report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schedule', html=False)

    def test_update_schedule(self):
        """Test updating a report schedule."""
        url = reverse('analytics:report_schedule', kwargs={'pk': self.report.id})
        response = self.client.post(url, {
            'frequency': 'daily',
            'start_date': timezone.now().strftime('%Y-%m-%d'),
            'enabled': True,
        })

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.schedule_frequency, 'daily')


class ReportDeleteViewTests(ReportManagementTestCase):
    """Tests for ReportDeleteView."""

    def test_delete_report_success(self):
        """Test successful report deletion."""
        report_id = self.report.id
        url = reverse('analytics:report_delete', kwargs={'pk': report_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, 200)
        # Verify report was deleted
        self.assertFalse(Report.objects.filter(id=report_id).exists())

    def test_delete_nonexistent_report(self):
        """Test deleting a nonexistent report."""
        fake_uuid = uuid.uuid4()
        url = reverse('analytics:report_delete', kwargs={'pk': fake_uuid})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, 404)


class ReportScheduleNewViewTests(ReportManagementTestCase):
    """Tests for ReportScheduleNewView (create new scheduled report)."""

    def test_get_schedule_new_modal(self):
        """Test getting the new schedule modal."""
        url = reverse('analytics:report_schedule_new')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_scheduled_report(self):
        """Test creating a new scheduled report."""
        url = reverse('analytics:report_schedule_new')
        initial_count = Report.objects.filter(is_scheduled=True).count()

        response = self.client.post(url, {
            'name': 'Weekly Spend Report',
            'report_type': 'spend_analysis',
            'frequency': 'weekly',
            'start_date': timezone.now().strftime('%Y-%m-%d'),
        })

        self.assertEqual(response.status_code, 200)
        # Check that a new scheduled report was created
        new_count = Report.objects.filter(is_scheduled=True).count()
        self.assertEqual(new_count, initial_count + 1)


class ReportBuilderViewTests(ReportManagementTestCase):
    """Tests for ReportBuilderView (custom report builder)."""

    def test_get_builder_modal(self):
        """Test getting the report builder modal."""
        url = reverse('analytics:report_builder')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_build_custom_report(self):
        """Test building a custom report."""
        url = reverse('analytics:report_builder')
        initial_count = Report.objects.filter(report_type='custom').count()

        response = self.client.post(url, {
            'name': 'Custom Analysis',
            'report_type': 'custom',
            'data_source': 'suppliers',
            'fields': json.dumps(['name', 'status', 'email']),
            'format': 'csv',
        })

        self.assertEqual(response.status_code, 200)


class ReportsTabViewTests(ReportManagementTestCase):
    """Tests for ReportsTabView (main reports tab)."""

    def test_get_reports_tab(self):
        """Test loading the reports tab."""
        url = reverse('analytics:reports_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check that report templates are in context
        self.assertIn('report_templates', response.context)
        self.assertIn('recent_reports', response.context)

    def test_reports_tab_shows_recent_reports(self):
        """Test that recent reports are displayed."""
        url = reverse('analytics:reports_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Our test report should be in recent reports
        recent_reports = response.context['recent_reports']
        self.assertIn(self.report, recent_reports)

    def test_reports_tab_shows_scheduled_reports(self):
        """Test that scheduled reports are displayed."""
        # Make the report scheduled
        self.report.is_scheduled = True
        self.report.schedule_frequency = 'weekly'
        self.report.next_run = timezone.now() + timedelta(days=7)
        self.report.save()

        url = reverse('analytics:reports_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        scheduled_reports = response.context['scheduled_reports']
        self.assertIn(self.report, scheduled_reports)


class AnalyticsTabViewTests(ReportManagementTestCase):
    """Tests for various analytics tab views."""

    def test_insights_tab(self):
        """Test loading the insights tab."""
        url = reverse('analytics:insights_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_trends_tab(self):
        """Test loading the trends tab."""
        url = reverse('analytics:trends_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check calculated context data
        self.assertIn('positive_trends', response.context)
        self.assertIn('areas_of_concern', response.context)
        self.assertIn('recommendations', response.context)

    def test_predictions_tab(self):
        """Test loading the predictions tab."""
        url = reverse('analytics:predictions_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check calculated context data
        self.assertIn('prediction_metrics', response.context)
        self.assertIn('ai_recommendations', response.context)
        self.assertIn('scenario_impact', response.context)

    def test_benchmarks_tab(self):
        """Test loading the benchmarks tab."""
        url = reverse('analytics:benchmarks_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check calculated context data
        self.assertIn('benchmarks', response.context)
        self.assertIn('summary_metrics', response.context)
        self.assertIn('improvement_opportunities', response.context)
        self.assertIn('maturity_assessment', response.context)


class ReportPDFGenerationTests(ReportManagementTestCase):
    """Tests for PDF report generation."""

    def test_spend_analysis_pdf(self):
        """Test generating spend analysis PDF."""
        self.report.report_type = 'spend_analysis'
        self.report.save()

        url = reverse('analytics:report_download', kwargs={'pk': self.report.id})
        response = self.client.get(f'{url}?format=pdf')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Check that PDF content is not empty
        self.assertTrue(len(response.content) > 0)

    def test_supplier_performance_pdf(self):
        """Test generating supplier performance PDF."""
        self.report.report_type = 'supplier_performance'
        self.report.save()

        url = reverse('analytics:report_download', kwargs={'pk': self.report.id})
        response = self.client.get(f'{url}?format=pdf')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_price_trends_pdf(self):
        """Test generating price trends PDF."""
        self.report.report_type = 'price_trends'
        self.report.save()

        url = reverse('analytics:report_download', kwargs={'pk': self.report.id})
        response = self.client.get(f'{url}?format=pdf')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')


class OrganizationIsolationTests(ReportManagementTestCase):
    """Tests to ensure organization data isolation."""

    def setUp(self):
        super().setUp()
        # Create another organization with its own reports
        self.other_org = Organization.objects.create(
            name='Other Organization',
            slug='other-org'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        OrganizationMembership.objects.create(
            user=self.other_user,
            organization=self.other_org,
            role='admin'
        )
        self.other_report = Report.objects.create(
            organization=self.other_org,
            created_by=self.other_user,
            name='Other Org Report',
            report_type='spend_analysis',
            report_format='csv',
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date(),
            status='completed',
        )

    def test_reports_tab_only_shows_own_org_reports(self):
        """Test that reports tab only shows current organization's reports."""
        url = reverse('analytics:reports_tab')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        recent_reports = response.context['recent_reports']
        # Should only contain our organization's report
        self.assertIn(self.report, recent_reports)
        self.assertNotIn(self.other_report, recent_reports)

    def test_cannot_delete_other_org_report(self):
        """Test that users cannot delete other organization's reports."""
        url = reverse('analytics:report_delete', kwargs={'pk': self.other_report.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, 404)
        # Report should still exist
        self.assertTrue(Report.objects.filter(id=self.other_report.id).exists())

    def test_cannot_download_other_org_report(self):
        """Test that users cannot download other organization's reports."""
        url = reverse('analytics:report_download', kwargs={'pk': self.other_report.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class BenchmarksCalculationTests(ReportManagementTestCase):
    """Tests for benchmark calculations."""

    def test_summary_metrics_calculation(self):
        """Test that summary metrics are calculated correctly."""
        url = reverse('analytics:benchmarks_tab')
        response = self.client.get(url)

        summary_metrics = response.context['summary_metrics']
        self.assertIn('performance_score', summary_metrics)
        self.assertIn('maturity_level', summary_metrics)
        self.assertIn('maturity_name', summary_metrics)
        self.assertIn('yoy_improvement', summary_metrics)

    def test_maturity_assessment_calculation(self):
        """Test that maturity assessment is calculated correctly."""
        url = reverse('analytics:benchmarks_tab')
        response = self.client.get(url)

        maturity = response.context['maturity_assessment']
        self.assertIn('level', maturity)
        self.assertIn('name', maturity)
        self.assertIn('progress_pct', maturity)
        self.assertIn('strengths', maturity)
        self.assertIn('next_requirements', maturity)
        # Progress should be level * 20
        self.assertEqual(maturity['progress_pct'], maturity['level'] * 20)

    def test_improvement_opportunities_calculation(self):
        """Test that improvement opportunities are calculated correctly."""
        url = reverse('analytics:benchmarks_tab')
        response = self.client.get(url)

        opportunities = response.context['improvement_opportunities']
        # Should be a list with at most 3 items
        self.assertIsInstance(opportunities, list)
        self.assertLessEqual(len(opportunities), 3)


class PredictionsCalculationTests(ReportManagementTestCase):
    """Tests for predictions tab calculations."""

    def test_prediction_metrics_calculation(self):
        """Test that prediction metrics are calculated correctly."""
        url = reverse('analytics:predictions_tab')
        response = self.client.get(url)

        metrics = response.context['prediction_metrics']
        self.assertIn('avg_price_change', metrics)
        self.assertIn('demand_forecast', metrics)
        self.assertIn('model_accuracy', metrics)
        self.assertIn('risk_alerts', metrics)

    def test_ai_recommendations_format(self):
        """Test that AI recommendations have correct format."""
        url = reverse('analytics:predictions_tab')
        response = self.client.get(url)

        recommendations = response.context['ai_recommendations']
        self.assertIsInstance(recommendations, list)
        for rec in recommendations:
            self.assertIn('title', rec)
            self.assertIn('description', rec)
            self.assertIn('color', rec)
            self.assertIn('icon', rec)

    def test_scenario_impact_calculation(self):
        """Test that scenario impact is calculated."""
        url = reverse('analytics:predictions_tab')
        response = self.client.get(url)

        impact = response.context['scenario_impact']
        self.assertIn('total_impact', impact)
        self.assertIn('current_spend', impact)

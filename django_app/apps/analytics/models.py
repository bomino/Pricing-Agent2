"""
Analytics and reporting models
"""
import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from apps.core.models import TimestampedModel, Organization
from django.contrib.auth.models import User


class Report(TimestampedModel):
    """Analytics reports and dashboards"""
    
    REPORT_TYPES = [
        ('price_analysis', 'Price Analysis'),
        ('spend_analysis', 'Spend Analysis'),
        ('supplier_performance', 'Supplier Performance'),
        ('cost_savings', 'Cost Savings'),
        ('market_intelligence', 'Market Intelligence'),
        ('risk_assessment', 'Risk Assessment'),
        ('compliance', 'Compliance Report'),
        ('custom', 'Custom Report'),
    ]
    
    REPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('dashboard', 'Interactive Dashboard'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('scheduled', 'Scheduled'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='reports')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    
    # Report configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    report_format = models.CharField(max_length=20, choices=REPORT_FORMATS, default='pdf')
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Filters and parameters
    filters = models.JSONField(default=dict, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    
    # Status and execution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    generated_at = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Sharing and access
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(User, blank=True, related_name='shared_reports')
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=20, blank=True)  # daily, weekly, monthly
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Results summary
    total_records = models.PositiveIntegerField(null=True, blank=True)
    summary_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'analytics_reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'report_type']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_scheduled', 'next_run']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.report_type}"
    
    def generate_report(self):
        """Generate the report"""
        self.status = 'generating'
        self.save()
        
        try:
            # Implement report generation logic
            self._execute_report_generation()
            
            self.status = 'completed'
            self.generated_at = timezone.now()
            
        except Exception as e:
            self.status = 'failed'
            # Log error details
            
        self.save()
    
    def _execute_report_generation(self):
        """Execute the actual report generation"""
        # Implement specific report generation logic based on report_type
        if self.report_type == 'price_analysis':
            return self._generate_price_analysis()
        elif self.report_type == 'spend_analysis':
            return self._generate_spend_analysis()
        # Add other report types
        
    def _generate_price_analysis(self):
        """Generate price analysis report"""
        # Implement price analysis report generation
        pass
    
    def _generate_spend_analysis(self):
        """Generate spend analysis report"""
        # Implement spend analysis report generation
        pass
    
    @property
    def is_expired(self):
        """Check if report data is considered expired (older than 30 days)"""
        if self.generated_at:
            return (timezone.now() - self.generated_at).days > 30
        return True


class DashboardMetric(TimestampedModel):
    """Dashboard metrics and KPIs"""
    
    METRIC_TYPES = [
        ('count', 'Count'),
        ('sum', 'Sum'),
        ('average', 'Average'),
        ('percentage', 'Percentage'),
        ('ratio', 'Ratio'),
        ('trend', 'Trend'),
        ('score', 'Score'),
    ]
    
    CALCULATION_METHODS = [
        ('sql', 'SQL Query'),
        ('aggregation', 'Django Aggregation'),
        ('api', 'External API'),
        ('ml_model', 'ML Model'),
        ('manual', 'Manual Entry'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('calculating', 'Calculating'),
        ('error', 'Error'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='dashboard_metrics')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_metrics')
    
    # Metric definition
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    category = models.CharField(max_length=100, blank=True)
    
    # Calculation configuration
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHODS)
    query = models.TextField(blank=True)  # SQL query or API endpoint
    aggregation_config = models.JSONField(default=dict, blank=True)
    
    # Current value
    current_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    previous_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    target_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Formatting and display
    unit = models.CharField(max_length=20, blank=True)  # %, $, units, etc.
    decimal_places = models.PositiveIntegerField(default=2)
    format_string = models.CharField(max_length=50, blank=True)
    
    # Status and refresh
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_calculated = models.DateTimeField(null=True, blank=True)
    refresh_frequency = models.PositiveIntegerField(default=3600)  # seconds
    next_refresh = models.DateTimeField(null=True, blank=True)
    
    # Visualization
    chart_type = models.CharField(max_length=50, blank=True)  # line, bar, pie, gauge, etc.
    chart_config = models.JSONField(default=dict, blank=True)
    
    # Alerting
    enable_alerts = models.BooleanField(default=False)
    alert_threshold_low = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    alert_threshold_high = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    class Meta:
        db_table = 'analytics_dashboard_metrics'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['category', 'metric_type']),
            models.Index(fields=['next_refresh']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.metric_type})"
    
    def calculate_value(self):
        """Calculate the current metric value"""
        self.status = 'calculating'
        self.save()
        
        try:
            if self.calculation_method == 'sql':
                value = self._calculate_from_sql()
            elif self.calculation_method == 'aggregation':
                value = self._calculate_from_aggregation()
            elif self.calculation_method == 'api':
                value = self._calculate_from_api()
            elif self.calculation_method == 'ml_model':
                value = self._calculate_from_ml_model()
            else:
                value = self.current_value
            
            self.previous_value = self.current_value
            self.current_value = value
            self.last_calculated = timezone.now()
            self.status = 'active'
            
            # Schedule next refresh
            self.next_refresh = timezone.now() + timezone.timedelta(seconds=self.refresh_frequency)
            
            # Check alerts
            if self.enable_alerts:
                self._check_alerts()
            
        except Exception as e:
            self.status = 'error'
            # Log error details
        
        self.save()
        return self.current_value
    
    def _calculate_from_sql(self):
        """Calculate value using SQL query"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute(self.query)
            result = cursor.fetchone()
            return Decimal(str(result[0])) if result and result[0] is not None else Decimal('0')
    
    def _calculate_from_aggregation(self):
        """Calculate value using Django aggregation"""
        # Implement Django ORM aggregation logic
        return Decimal('0')
    
    def _calculate_from_api(self):
        """Calculate value from external API"""
        # Implement API call logic
        return Decimal('0')
    
    def _calculate_from_ml_model(self):
        """Calculate value using ML model"""
        # Implement ML model prediction logic
        return Decimal('0')
    
    def _check_alerts(self):
        """Check if metric value triggers alerts"""
        if self.current_value is None:
            return
        
        if (self.alert_threshold_low and self.current_value < self.alert_threshold_low) or \
           (self.alert_threshold_high and self.current_value > self.alert_threshold_high):
            # Create alert
            Alert.objects.create(
                organization=self.organization,
                alert_type='metric_threshold',
                title=f"Metric Alert: {self.name}",
                message=f"Metric {self.name} value {self.current_value} is outside threshold range",
                severity='medium',
                source_type='dashboard_metric',
                source_id=str(self.id),
                data={
                    'metric_name': self.name,
                    'current_value': float(self.current_value),
                    'threshold_low': float(self.alert_threshold_low) if self.alert_threshold_low else None,
                    'threshold_high': float(self.alert_threshold_high) if self.alert_threshold_high else None,
                }
            )
    
    @property
    def value_change(self):
        """Calculate change from previous value"""
        if self.current_value and self.previous_value:
            return self.current_value - self.previous_value
        return None
    
    @property
    def value_change_percentage(self):
        """Calculate percentage change from previous value"""
        if self.current_value and self.previous_value and self.previous_value != 0:
            return ((self.current_value - self.previous_value) / self.previous_value) * 100
        return None
    
    @property
    def formatted_value(self):
        """Get formatted display value"""
        if self.current_value is None:
            return "N/A"
        
        if self.format_string:
            return self.format_string.format(value=self.current_value)
        
        # Default formatting
        value_str = f"{self.current_value:.{self.decimal_places}f}"
        if self.unit:
            if self.unit == '%':
                value_str += '%'
            elif self.unit == '$':
                value_str = '$' + value_str
            else:
                value_str += f' {self.unit}'
        
        return value_str


class Alert(TimestampedModel):
    """System alerts and notifications"""
    
    ALERT_TYPES = [
        ('price_spike', 'Price Spike'),
        ('price_drop', 'Price Drop'),
        ('supplier_issue', 'Supplier Issue'),
        ('contract_expiry', 'Contract Expiry'),
        ('budget_overrun', 'Budget Overrun'),
        ('quality_issue', 'Quality Issue'),
        ('delivery_delay', 'Delivery Delay'),
        ('compliance_violation', 'Compliance Violation'),
        ('system_error', 'System Error'),
        ('metric_threshold', 'Metric Threshold'),
        ('ml_anomaly', 'ML Anomaly Detection'),
        ('workflow', 'Workflow Alert'),
        ('custom', 'Custom Alert'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
        ('escalated', 'Escalated'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='alerts')
    
    # Alert definition
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    
    # Source information
    source_type = models.CharField(max_length=50, blank=True)  # model name that triggered alert
    source_id = models.UUIDField(null=True, blank=True)  # ID of the source object
    source_url = models.URLField(blank=True)
    
    # Status and resolution
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    acknowledged_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Notification settings
    email_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    
    # Additional data
    data = models.JSONField(default=dict, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Assigned users
    assigned_to = models.ManyToManyField(User, blank=True, related_name='assigned_alerts')
    
    class Meta:
        db_table = 'analytics_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status', 'severity']),
            models.Index(fields=['alert_type', 'status']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['source_type', 'source_id']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} - {self.title} ({self.severity})"
    
    def acknowledge(self, user, notes=''):
        """Acknowledge the alert"""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
    
    def resolve(self, user, notes=''):
        """Resolve the alert"""
        self.status = 'resolved'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
    
    def dismiss(self, user):
        """Dismiss the alert"""
        self.status = 'dismissed'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()
    
    def escalate(self):
        """Escalate the alert severity"""
        severity_order = ['low', 'medium', 'high', 'critical']
        current_index = severity_order.index(self.severity)
        if current_index < len(severity_order) - 1:
            self.severity = severity_order[current_index + 1]
            self.status = 'escalated'
            self.save()
    
    @property
    def is_expired(self):
        """Check if alert has expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def age_hours(self):
        """Calculate alert age in hours"""
        return (timezone.now() - self.created_at).total_seconds() / 3600
    
    @classmethod
    def create_alert(cls, organization, alert_type, title, message, severity='medium', 
                    source_type=None, source_id=None, data=None, expires_in_hours=None):
        """Create a new alert"""
        alert = cls.objects.create(
            organization=organization,
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity,
            source_type=source_type,
            source_id=source_id,
            data=data or {},
            expires_at=timezone.now() + timezone.timedelta(hours=expires_in_hours) if expires_in_hours else None
        )
        
        # Send notifications based on severity
        alert._send_notifications()
        
        return alert
    
    def _send_notifications(self):
        """Send notifications for the alert"""
        # Implement notification sending logic
        # This could integrate with email service, push notification service, etc.
        pass


class AnalyticsDashboard(TimestampedModel):
    """Dashboard configurations"""
    
    DASHBOARD_TYPES = [
        ('executive', 'Executive Dashboard'),
        ('procurement', 'Procurement Dashboard'),
        ('pricing', 'Pricing Dashboard'),
        ('supplier', 'Supplier Dashboard'),
        ('risk', 'Risk Dashboard'),
        ('custom', 'Custom Dashboard'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='dashboards')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_dashboards')
    
    # Dashboard configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES)
    
    # Layout and widgets
    layout_config = models.JSONField(default=dict, blank=True)
    widgets = models.ManyToManyField(DashboardMetric, blank=True, related_name='dashboards')
    
    # Access control
    is_public = models.BooleanField(default=False)
    allowed_users = models.ManyToManyField(User, blank=True, related_name='accessible_dashboards')
    
    # Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.PositiveIntegerField(default=300)  # seconds
    
    class Meta:
        db_table = 'analytics_dashboards'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'dashboard_type']),
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.dashboard_type})"


class DataQualityCheck(TimestampedModel):
    """Data quality monitoring and checks"""
    
    CHECK_TYPES = [
        ('completeness', 'Completeness Check'),
        ('accuracy', 'Accuracy Check'),
        ('consistency', 'Consistency Check'),
        ('timeliness', 'Timeliness Check'),
        ('validity', 'Validity Check'),
        ('uniqueness', 'Uniqueness Check'),
    ]
    
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
        ('running', 'Running'),
        ('error', 'Error'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='data_quality_checks')
    
    # Check definition
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    check_type = models.CharField(max_length=20, choices=CHECK_TYPES)
    table_name = models.CharField(max_length=100)
    column_name = models.CharField(max_length=100, blank=True)
    
    # Check configuration
    check_query = models.TextField()
    threshold_value = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    expected_value = models.TextField(blank=True)
    
    # Results
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='passed')
    last_run = models.DateTimeField(null=True, blank=True)
    current_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=True)
    schedule_frequency = models.CharField(max_length=20, default='daily')
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Alert settings
    create_alert_on_failure = models.BooleanField(default=True)
    alert_recipients = models.ManyToManyField(User, blank=True, related_name='dq_alert_recipients')
    
    class Meta:
        db_table = 'analytics_data_quality_checks'
        ordering = ['table_name', 'name']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['table_name', 'check_type']),
            models.Index(fields=['is_scheduled', 'next_run']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.table_name}"
    
    def run_check(self):
        """Execute the data quality check"""
        self.status = 'running'
        self.save()
        
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                cursor.execute(self.check_query)
                result = cursor.fetchone()
                
                if result:
                    self.current_value = Decimal(str(result[0]))
                    
                    # Determine pass/fail based on threshold
                    if self.threshold_value:
                        if self.current_value >= self.threshold_value:
                            self.status = 'passed'
                        else:
                            self.status = 'failed'
                    else:
                        self.status = 'passed'
                else:
                    self.status = 'error'
                
                self.last_run = timezone.now()
                
                # Schedule next run
                if self.is_scheduled:
                    if self.schedule_frequency == 'daily':
                        self.next_run = timezone.now() + timezone.timedelta(days=1)
                    elif self.schedule_frequency == 'weekly':
                        self.next_run = timezone.now() + timezone.timedelta(weeks=1)
                    elif self.schedule_frequency == 'hourly':
                        self.next_run = timezone.now() + timezone.timedelta(hours=1)
                
                # Create alert if check failed
                if self.status == 'failed' and self.create_alert_on_failure:
                    Alert.create_alert(
                        organization=self.organization,
                        alert_type='system_error',
                        title=f"Data Quality Check Failed: {self.name}",
                        message=f"Data quality check '{self.name}' failed for table {self.table_name}",
                        severity='medium',
                        source_type='data_quality_check',
                        source_id=str(self.id),
                        data={
                            'check_name': self.name,
                            'table_name': self.table_name,
                            'current_value': float(self.current_value) if self.current_value else None,
                            'threshold_value': float(self.threshold_value) if self.threshold_value else None,
                        }
                    )
        
        except Exception as e:
            self.status = 'error'
            # Log error details
        
        self.save()
        return self.status
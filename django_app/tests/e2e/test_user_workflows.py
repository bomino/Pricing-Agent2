"""
End-to-end tests for user workflows using Playwright.
"""
import pytest
import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from apps.core.models import Organization

User = get_user_model()


class PlaywrightE2ETest:
    """Base class for Playwright E2E tests."""
    
    @pytest.fixture(scope="session")
    async def browser_context(self):
        """Create browser context for tests."""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True
            )
            yield context
            await browser.close()
    
    @pytest.fixture
    async def page(self, browser_context: BrowserContext):
        """Create a new page for each test."""
        page = await browser_context.new_page()
        yield page
        await page.close()
    
    async def login_user(self, page: Page, email: str, password: str):
        """Helper method to log in a user."""
        await page.goto("http://localhost:8000/login/")
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/dashboard/")
    
    async def create_test_data(self):
        """Create test data for E2E tests."""
        self.organization = Organization.objects.create(
            name="E2E Test Organization",
            slug="e2e-test-org",
            is_active=True
        )
        
        self.user = User.objects.create_user(
            username="e2euser",
            email="e2e@test.com",
            password="testpass123",
            organization=self.organization
        )


@pytest.mark.e2e
class TestRFQWorkflow(PlaywrightE2ETest):
    """Test complete RFQ creation and management workflow."""
    
    @pytest.mark.asyncio
    async def test_create_rfq_workflow(self, page: Page):
        """Test the complete RFQ creation workflow."""
        await self.create_test_data()
        
        # Login
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to RFQ creation
        await page.click('a[href="/rfqs/"]')
        await page.click('button:has-text("Create RFQ")')
        
        # Fill RFQ form
        await page.fill('input[name="title"]', 'E2E Test RFQ')
        await page.fill('textarea[name="description"]', 'This is an E2E test RFQ')
        await page.select_option('select[name="category"]', 'Construction')
        
        # Add material line item
        await page.click('button:has-text("Add Material")')
        await page.fill('input[name="materials[0][description]"]', 'Steel Plates')
        await page.fill('input[name="materials[0][quantity]"]', '1000')
        await page.select_option('select[name="materials[0][unit]"]', 'kg')
        
        # Set delivery details
        await page.fill('input[name="delivery_date"]', '2024-12-31')
        await page.fill('input[name="delivery_location"]', 'New York, NY')
        
        # Submit RFQ
        await page.click('button[type="submit"]')
        
        # Wait for success message
        await page.wait_for_selector('.alert-success:has-text("RFQ created successfully")')
        
        # Verify RFQ was created
        await page.wait_for_url("**/rfqs/**")
        rfq_title = await page.inner_text('h1')
        assert 'E2E Test RFQ' in rfq_title
    
    @pytest.mark.asyncio
    async def test_rfq_supplier_invitation(self, page: Page):
        """Test inviting suppliers to an RFQ."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Create RFQ first (abbreviated)
        await page.goto("http://localhost:8000/rfqs/create/")
        await page.fill('input[name="title"]', 'Supplier Invitation Test')
        await page.click('button[type="submit"]')
        
        # Go to supplier invitation page
        await page.click('button:has-text("Invite Suppliers")')
        
        # Select suppliers
        await page.check('input[name="suppliers"][value="1"]')
        await page.check('input[name="suppliers"][value="2"]')
        
        # Set invitation message
        await page.fill('textarea[name="message"]', 'Please provide your best quote.')
        
        # Send invitations
        await page.click('button:has-text("Send Invitations")')
        
        # Verify success
        await page.wait_for_selector('.alert-success:has-text("Invitations sent")')
    
    @pytest.mark.asyncio
    async def test_rfq_quote_comparison(self, page: Page):
        """Test comparing quotes for an RFQ."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to RFQ with quotes
        await page.goto("http://localhost:8000/rfqs/1/")  # Assume RFQ exists
        
        # Go to quote comparison
        await page.click('button:has-text("Compare Quotes")')
        
        # Verify comparison table is loaded
        await page.wait_for_selector('table.quote-comparison')
        
        # Check that quotes are displayed
        quote_rows = await page.query_selector_all('tbody tr')
        assert len(quote_rows) > 0
        
        # Test sorting by price
        await page.click('th:has-text("Total Price")')
        
        # Test filtering
        await page.select_option('select[name="supplier_filter"]', 'Supplier A')
        
        # Test selecting winning quote
        await page.click('button.select-quote:first-child')
        await page.wait_for_selector('.alert-success:has-text("Quote selected")')


@pytest.mark.e2e
class TestPricingAnalyticsWorkflow(PlaywrightE2ETest):
    """Test pricing analytics and reporting workflow."""
    
    @pytest.mark.asyncio
    async def test_price_dashboard_navigation(self, page: Page):
        """Test navigating the price analytics dashboard."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to pricing dashboard
        await page.click('a[href="/pricing/"]')
        
        # Wait for dashboard to load
        await page.wait_for_selector('.pricing-dashboard')
        
        # Test price chart interaction
        chart = await page.query_selector('.price-chart')
        if chart:
            await chart.click()
        
        # Test time range selector
        await page.select_option('select[name="time_range"]', '30d')
        await page.wait_for_selector('.chart-updated')
        
        # Test material filter
        await page.fill('input[name="material_search"]', 'Steel')
        await page.keyboard.press('Enter')
        
        # Verify filtered results
        materials = await page.query_selector_all('.material-item')
        for material in materials:
            text = await material.inner_text()
            assert 'Steel' in text.lower() or 'steel' in text
    
    @pytest.mark.asyncio
    async def test_price_alert_creation(self, page: Page):
        """Test creating price alerts."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to materials page
        await page.goto("http://localhost:8000/materials/")
        
        # Select a material
        await page.click('.material-item:first-child')
        
        # Click create alert
        await page.click('button:has-text("Create Alert")')
        
        # Fill alert form
        await page.fill('input[name="alert_name"]', 'High Price Alert')
        await page.select_option('select[name="condition"]', 'above')
        await page.fill('input[name="threshold"]', '150.00')
        await page.check('input[name="email_notification"]')
        
        # Submit alert
        await page.click('button[type="submit"]')
        
        # Verify alert created
        await page.wait_for_selector('.alert-success:has-text("Alert created")')
    
    @pytest.mark.asyncio
    async def test_report_generation(self, page: Page):
        """Test generating pricing reports."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to reports
        await page.click('a[href="/reports/"]')
        
        # Select report type
        await page.select_option('select[name="report_type"]', 'price_analysis')
        
        # Set date range
        await page.fill('input[name="start_date"]', '2024-01-01')
        await page.fill('input[name="end_date"]', '2024-12-31')
        
        # Select materials
        await page.check('input[name="materials"][value="all"]')
        
        # Generate report
        await page.click('button:has-text("Generate Report")')
        
        # Wait for report to be generated
        await page.wait_for_selector('.report-ready', timeout=30000)
        
        # Test download
        download_promise = page.wait_for_event('download')
        await page.click('a:has-text("Download PDF")')
        download = await download_promise
        
        # Verify download
        assert download.suggested_filename.endswith('.pdf')


@pytest.mark.e2e
class TestSupplierWorkflow(PlaywrightE2ETest):
    """Test supplier management workflow."""
    
    @pytest.mark.asyncio
    async def test_supplier_registration(self, page: Page):
        """Test supplier registration process."""
        # Go to supplier registration
        await page.goto("http://localhost:8000/suppliers/register/")
        
        # Fill registration form
        await page.fill('input[name="company_name"]', 'E2E Test Supplier Ltd')
        await page.fill('input[name="contact_email"]', 'supplier@e2etest.com')
        await page.fill('input[name="contact_phone"]', '+1-555-123-4567')
        await page.fill('textarea[name="address"]', '123 Supplier St, Supplier City, SC 12345')
        
        # Select categories
        await page.check('input[name="categories"][value="construction"]')
        await page.check('input[name="categories"][value="materials"]')
        
        # Upload documents
        await page.set_input_files('input[name="business_license"]', 'test_files/business_license.pdf')
        await page.set_input_files('input[name="insurance_cert"]', 'test_files/insurance.pdf')
        
        # Submit registration
        await page.click('button[type="submit"]')
        
        # Wait for confirmation
        await page.wait_for_selector('.registration-success')
    
    @pytest.mark.asyncio
    async def test_supplier_portal_access(self, page: Page):
        """Test supplier portal access and quote submission."""
        # Login as supplier
        await page.goto("http://localhost:8000/suppliers/login/")
        await page.fill('input[name="email"]', 'supplier@test.com')
        await page.fill('input[name="password"]', 'supplierpass123')
        await page.click('button[type="submit"]')
        
        # Navigate to RFQs
        await page.click('a[href="/suppliers/rfqs/"]')
        
        # View RFQ details
        await page.click('.rfq-item:first-child')
        
        # Submit quote
        await page.click('button:has-text("Submit Quote")')
        
        # Fill quote form
        await page.fill('input[name="total_price"]', '15000.00')
        await page.fill('input[name="line_items[0][unit_price]"]', '15.00')
        await page.fill('textarea[name="notes"]', 'Best quality materials used.')
        
        # Set delivery terms
        await page.select_option('select[name="payment_terms"]', 'net_30')
        await page.fill('input[name="delivery_days"]', '14')
        
        # Submit quote
        await page.click('button[type="submit"]')
        
        # Verify submission
        await page.wait_for_selector('.quote-submitted')


@pytest.mark.e2e
class TestMLPredictionWorkflow(PlaywrightE2ETest):
    """Test ML prediction integration in user workflows."""
    
    @pytest.mark.asyncio
    async def test_real_time_price_prediction(self, page: Page):
        """Test real-time price prediction during RFQ creation."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to RFQ creation
        await page.goto("http://localhost:8000/rfqs/create/")
        
        # Fill material specifications
        await page.fill('input[name="materials[0][description]"]', 'Steel Plate A36')
        await page.fill('input[name="materials[0][quantity]"]', '1000')
        await page.select_option('select[name="materials[0][unit]"]', 'kg')
        
        # Fill additional specs that trigger prediction
        await page.fill('input[name="materials[0][thickness]"]', '10')
        await page.fill('input[name="materials[0][width]"]', '100')
        await page.fill('input[name="materials[0][length]"]', '200')
        
        # Wait for prediction to appear
        await page.wait_for_selector('.predicted-price', timeout=10000)
        
        # Verify prediction is displayed
        prediction_text = await page.inner_text('.predicted-price')
        assert '$' in prediction_text
        assert 'Confidence:' in prediction_text
    
    @pytest.mark.asyncio
    async def test_price_trend_analysis(self, page: Page):
        """Test price trend analysis features."""
        await self.create_test_data()
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        # Navigate to material detail page
        await page.goto("http://localhost:8000/materials/1/")
        
        # Click on price trends tab
        await page.click('tab:has-text("Price Trends")')
        
        # Wait for chart to load
        await page.wait_for_selector('.price-trend-chart')
        
        # Test different time ranges
        time_ranges = ['7d', '30d', '90d', '1y']
        for time_range in time_ranges:
            await page.click(f'button[data-range="{time_range}"]')
            await page.wait_for_selector('.chart-updated')
        
        # Test prediction overlay
        await page.check('input[name="show_predictions"]')
        await page.wait_for_selector('.prediction-overlay')


@pytest.mark.e2e
class TestMobileResponsiveness(PlaywrightE2ETest):
    """Test mobile responsiveness of key workflows."""
    
    @pytest.fixture
    async def mobile_page(self, browser_context: BrowserContext):
        """Create a mobile viewport page."""
        page = await browser_context.new_page()
        await page.set_viewport_size({"width": 375, "height": 812})  # iPhone X
        yield page
        await page.close()
    
    @pytest.mark.asyncio
    async def test_mobile_rfq_creation(self, mobile_page: Page):
        """Test RFQ creation on mobile device."""
        await self.create_test_data()
        
        # Login on mobile
        await mobile_page.goto("http://localhost:8000/login/")
        await mobile_page.fill('input[name="email"]', 'e2e@test.com')
        await mobile_page.fill('input[name="password"]', 'testpass123')
        await mobile_page.click('button[type="submit"]')
        
        # Open mobile menu
        await mobile_page.click('.mobile-menu-button')
        await mobile_page.click('a[href="/rfqs/"]')
        
        # Create RFQ on mobile
        await mobile_page.click('.create-rfq-mobile')
        
        # Fill form (should be mobile-optimized)
        await mobile_page.fill('input[name="title"]', 'Mobile RFQ Test')
        await mobile_page.fill('textarea[name="description"]', 'Testing mobile creation')
        
        # Use mobile-friendly date picker
        await mobile_page.click('input[name="delivery_date"]')
        await mobile_page.click('.datepicker-today')
        
        # Submit
        await mobile_page.click('button[type="submit"]')
        
        # Verify success
        await mobile_page.wait_for_selector('.mobile-success-message')
    
    @pytest.mark.asyncio
    async def test_mobile_dashboard_navigation(self, mobile_page: Page):
        """Test dashboard navigation on mobile."""
        await self.create_test_data()
        await self.login_user(mobile_page, "e2e@test.com", "testpass123")
        
        # Test mobile dashboard cards
        cards = await mobile_page.query_selector_all('.dashboard-card-mobile')
        assert len(cards) > 0
        
        # Test swipe navigation (if implemented)
        if await mobile_page.query_selector('.swipe-container'):
            # Simulate swipe
            await mobile_page.evaluate('document.querySelector(".swipe-container").dispatchEvent(new Event("swipeleft"))')
        
        # Test mobile charts
        await mobile_page.click('.chart-mobile')
        await mobile_page.wait_for_selector('.chart-fullscreen')


@pytest.mark.e2e
class TestPerformanceAndUsability(PlaywrightE2ETest):
    """Test performance and usability aspects."""
    
    @pytest.mark.asyncio
    async def test_page_load_performance(self, page: Page):
        """Test page load performance."""
        await self.create_test_data()
        
        # Measure login page load time
        start_time = asyncio.get_event_loop().time()
        await page.goto("http://localhost:8000/login/")
        await page.wait_for_load_state('networkidle')
        login_load_time = asyncio.get_event_loop().time() - start_time
        
        assert login_load_time < 3.0  # Should load within 3 seconds
        
        # Login and measure dashboard load time
        await self.login_user(page, "e2e@test.com", "testpass123")
        
        start_time = asyncio.get_event_loop().time()
        await page.goto("http://localhost:8000/dashboard/")
        await page.wait_for_load_state('networkidle')
        dashboard_load_time = asyncio.get_event_loop().time() - start_time
        
        assert dashboard_load_time < 5.0  # Should load within 5 seconds
    
    @pytest.mark.asyncio
    async def test_accessibility_features(self, page: Page):
        """Test accessibility features."""
        await self.create_test_data()
        await page.goto("http://localhost:8000/")
        
        # Test keyboard navigation
        await page.keyboard.press('Tab')
        focused_element = await page.evaluate('document.activeElement.tagName')
        assert focused_element in ['A', 'BUTTON', 'INPUT']
        
        # Test ARIA labels
        buttons = await page.query_selector_all('button[aria-label]')
        assert len(buttons) > 0
        
        # Test alt text for images
        images = await page.query_selector_all('img')
        for image in images:
            alt_text = await image.get_attribute('alt')
            assert alt_text is not None and alt_text.strip() != ''
    
    @pytest.mark.asyncio
    async def test_error_handling_ux(self, page: Page):
        """Test error handling user experience."""
        await page.goto("http://localhost:8000/login/")
        
        # Test form validation
        await page.click('button[type="submit"]')
        error_messages = await page.query_selector_all('.error-message')
        assert len(error_messages) > 0
        
        # Test network error handling
        await page.route('**/api/**', lambda route: route.abort())
        
        await page.fill('input[name="email"]', 'test@example.com')
        await page.fill('input[name="password"]', 'wrongpass')
        await page.click('button[type="submit"]')
        
        # Should show user-friendly error message
        await page.wait_for_selector('.connection-error')
        error_text = await page.inner_text('.connection-error')
        assert 'connection' in error_text.lower() or 'network' in error_text.lower()
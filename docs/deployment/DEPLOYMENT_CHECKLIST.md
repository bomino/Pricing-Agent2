# Deployment Checklist for Pricing Agent

## Pre-Deployment Steps

### 1. Database Preparation
- [ ] Backup existing database
  ```bash
  docker exec -it pricing_django python manage.py backup_database --format=sql
  ```
- [ ] Clean test data from database
  ```bash
  docker exec -it pricing_django python manage.py cleanup_database --keep-admin --dry-run
  docker exec -it pricing_django python manage.py cleanup_database --keep-admin
  ```
- [ ] Run all migrations
  ```bash
  docker exec -it pricing_django python manage.py migrate
  ```

### 2. Environment Configuration
- [ ] Copy `.env.production.template` to `.env.production`
- [ ] Set all required environment variables:
  - [ ] `SECRET_KEY` - Generate new secret key
  - [ ] `ALLOWED_HOSTS` - Set production domain(s)
  - [ ] `DB_PASSWORD` - Set secure database password
  - [ ] `EMAIL_HOST_USER` - Email account for notifications
  - [ ] `EMAIL_HOST_PASSWORD` - Email password
  - [ ] `SENTRY_DSN` - (Optional) Error tracking

### 3. Static Files
- [ ] Collect static files
  ```bash
  docker exec -it pricing_django python manage.py collectstatic --noinput
  ```
- [ ] Verify static files are served correctly
- [ ] Test CSS/JS loading in production mode
- [ ] Verify custom CSS blocks are rendering (check {% block extra_css %})
- [ ] Test gradient styles in analytics dashboard
- [ ] Confirm modal dialogs have proper styling

### 4. Security Checks
- [ ] Run Django security check
  ```bash
  docker exec -it pricing_django python manage.py check --deploy
  ```
- [ ] Verify HTTPS is configured
- [ ] Check CORS settings if API access needed
- [ ] Review and update `ADMIN_URL` path
- [ ] Ensure DEBUG=False in production

### 5. User Setup
- [ ] Create production superuser account
  ```bash
  docker exec -it pricing_django python manage.py createsuperuser
  ```
- [ ] Set up initial organization
  ```bash
  docker exec -it pricing_django python manage.py shell
  >>> from apps.core.models import Organization
  >>> Organization.objects.create(name='Your Company', code='COMPANY')
  ```
- [ ] Create user groups and permissions
  ```bash
  docker exec -it pricing_django python manage.py setup_rbac
  ```

## Deployment Steps

### 1. Docker Deployment
- [ ] Build production Docker image
  ```bash
  docker-compose -f docker-compose.prod.yml build
  ```
- [ ] Start services
  ```bash
  docker-compose -f docker-compose.prod.yml up -d
  ```
- [ ] Check container logs
  ```bash
  docker-compose -f docker-compose.prod.yml logs -f django
  ```

### 2. Database Setup
- [ ] Apply migrations
  ```bash
  docker-compose -f docker-compose.prod.yml exec django python manage.py migrate
  ```
- [ ] Load initial data (if needed)
  ```bash
  docker-compose -f docker-compose.prod.yml exec django python manage.py loaddata initial_data.json
  ```

### 3. Health Checks
- [ ] Test health endpoint: `curl https://yourdomain.com/health/`
- [ ] Verify login page loads: `https://yourdomain.com/accounts/login/`
- [ ] Check admin panel: `https://yourdomain.com/admin/`
- [ ] Test file upload functionality
- [ ] Verify analytics dashboard loads with gradient styling
- [ ] Test date range modal functionality
- [ ] Test report generation modal
- [ ] Verify all analytics tabs load via HTMX

### 4. Monitoring Setup
- [ ] Configure application monitoring (Sentry/New Relic)
- [ ] Set up log aggregation
- [ ] Configure uptime monitoring
- [ ] Set up database backup schedule

## Post-Deployment Verification

### Application Testing
- [ ] User can log in successfully
- [ ] File upload works correctly
- [ ] Analytics tabs load properly with HTMX
- [ ] Date range picker opens and applies filters
- [ ] Report generation modal works for all formats (PDF, Excel, CSV)
- [ ] Metric cards display with gradient backgrounds
- [ ] Tab switching maintains state
- [ ] Toast notifications appear for user actions
- [ ] Data ingestion pipeline processes files
- [ ] Logout functionality works with modal

### Performance Testing
- [ ] Page load times < 2 seconds
- [ ] File uploads handle 50MB files
- [ ] Database queries are optimized
- [ ] Static files are cached properly

### Security Verification
- [ ] HTTPS redirect works
- [ ] Session cookies are secure
- [ ] CSRF protection is active
- [ ] Admin URL is not default `/admin/`
- [ ] No debug information exposed

## Rollback Plan

### If Issues Occur:
1. Keep previous Docker image tagged
   ```bash
   docker tag pricing_agent:latest pricing_agent:backup
   ```

2. Database backup before deployment
   ```bash
   pg_dump -h localhost -U pricing_user pricing_agent > backup_$(date +%Y%m%d).sql
   ```

3. Quick rollback procedure:
   ```bash
   # Stop current containers
   docker-compose -f docker-compose.prod.yml down
   
   # Restore previous image
   docker tag pricing_agent:backup pricing_agent:latest
   
   # Restore database if needed
   psql -h localhost -U pricing_user pricing_agent < backup_YYYYMMDD.sql
   
   # Start services with previous version
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Maintenance Tasks

### Daily
- [ ] Check application logs for errors
- [ ] Monitor disk space usage
- [ ] Verify backup completion

### Weekly
- [ ] Review performance metrics
- [ ] Check for security updates
- [ ] Clean old file uploads
  ```bash
  docker exec -it pricing_django python manage.py cleanup_old_uploads --days=30
  ```

### Monthly
- [ ] Update dependencies
- [ ] Review and rotate logs
- [ ] Performance analysis
- [ ] Security audit

## Support Information

- **Documentation**: See `CLAUDE.md` and `PLAN.md`
- **Admin Guide**: `/docs/admin_guide.md`
- **API Documentation**: `/docs/api_reference.md`
- **Troubleshooting**: `/docs/troubleshooting.md`

## Emergency Contacts

- System Admin: [Your Name]
- Database Admin: [DBA Name]
- DevOps Lead: [DevOps Name]
- On-call rotation: [Link to schedule]

---

**Last Updated**: 2025-08-31
**Version**: 1.1.0
**Next Review**: 2025-11-31

## Changelog v1.1.0
- Enhanced analytics dashboard with modern gradient UI
- Fixed CSS loading issues in base template
- Added interactive date range and report generation modals
- Improved JavaScript function scoping for global accessibility
- Updated HTMX tab navigation with smooth transitions
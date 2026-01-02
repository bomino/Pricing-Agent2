# Phase 2: Celery Integration Plan

## Overview
Transform the synchronous data processing into an async, scalable system using Celery with Redis.

## Current Pain Points
- UI blocks during large file processing (>1000 rows)
- No progress visibility during processing
- Can't cancel long-running imports
- Server timeout on very large files

## Implementation Steps

### Step 1: Configure Celery (Day 1 Morning)

#### 1.1 Install Dependencies
```bash
# Add to requirements-simple.txt
celery==5.3.4
redis==5.0.1
django-celery-results==2.5.1
django-celery-beat==2.5.1
```

#### 1.2 Create Celery Configuration
```python
# django_app/pricing_agent/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')

app = Celery('pricing_agent')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

#### 1.3 Update Settings
```python
# settings_local.py additions
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
```

### Step 2: Create Async Tasks (Day 1 Afternoon)

#### 2.1 Processing Task
```python
# apps/data_ingestion/tasks.py
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from .services.optimized_processor import OptimizedDataProcessor

@shared_task(bind=True, name='process_procurement_data')
def process_procurement_data(self, upload_id):
    progress_recorder = ProgressRecorder(self)

    try:
        upload = DataUpload.objects.get(id=upload_id)
        upload.status = 'processing'
        upload.save()

        processor = OptimizedDataProcessor(
            upload=upload,
            progress_callback=lambda current, total:
                progress_recorder.set_progress(current, total)
        )

        result = processor.process()

        upload.status = 'completed'
        upload.processed_rows = result['processed']
        upload.save()

        return {
            'status': 'success',
            'processed': result['processed'],
            'created_suppliers': result['created_suppliers'],
            'created_materials': result['created_materials'],
            'created_pos': result['created_pos'],
            'created_prices': result.get('created_prices', 0)
        }

    except Exception as e:
        upload.status = 'failed'
        upload.error_message = str(e)
        upload.save()
        raise
```

### Step 3: Add Progress Tracking UI (Day 2 Morning)

#### 3.1 Progress Bar Component
```html
<!-- templates/data_ingestion/processing_progress.html -->
<div id="progress-container" class="mt-6">
    <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-semibold mb-4">Processing Progress</h3>

        <div class="relative pt-1">
            <div class="flex mb-2 items-center justify-between">
                <div>
                    <span class="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-blue-600 bg-blue-200">
                        <span id="progress-status">Processing...</span>
                    </span>
                </div>
                <div class="text-right">
                    <span id="progress-percent" class="text-xs font-semibold inline-block text-blue-600">
                        0%
                    </span>
                </div>
            </div>
            <div class="overflow-hidden h-2 mb-4 text-xs flex rounded bg-blue-200">
                <div id="progress-bar" style="width:0%"
                     class="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-500 transition-all duration-500">
                </div>
            </div>
            <div class="text-sm text-gray-600">
                <span id="progress-current">0</span> / <span id="progress-total">0</span> records processed
            </div>
        </div>

        <div id="processing-actions" class="mt-4 flex gap-2">
            <button onclick="cancelProcessing()" class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
                Cancel Processing
            </button>
        </div>
    </div>
</div>

<script>
function startProgressPolling(taskId) {
    const progressUrl = `/data-ingestion/progress/${taskId}/`;

    const poll = setInterval(() => {
        fetch(progressUrl)
            .then(response => response.json())
            .then(data => {
                updateProgress(data);

                if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                    clearInterval(poll);
                    handleCompletion(data);
                }
            });
    }, 1000);  // Poll every second
}

function updateProgress(data) {
    const percent = Math.round((data.current / data.total) * 100);
    document.getElementById('progress-percent').textContent = percent + '%';
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-current').textContent = data.current;
    document.getElementById('progress-total').textContent = data.total;
}
</script>
```

#### 3.2 Progress Endpoint
```python
# apps/data_ingestion/views.py
from celery.result import AsyncResult
from django.http import JsonResponse

def task_progress(request, task_id):
    result = AsyncResult(task_id)

    response_data = {
        'state': result.state,
        'current': 0,
        'total': 100,
    }

    if result.state == 'PENDING':
        response_data['status'] = 'Waiting to start...'
    elif result.state == 'PROGRESS':
        response_data.update(result.info)
    elif result.state == 'SUCCESS':
        response_data['current'] = 100
        response_data['total'] = 100
        response_data['result'] = result.info
    elif result.state == 'FAILURE':
        response_data['error'] = str(result.info)

    return JsonResponse(response_data)
```

### Step 4: Update Process View (Day 2 Afternoon)

```python
# Modified process_upload view
@login_required
def process_upload(request, upload_id):
    upload = get_object_or_404(DataUpload, id=upload_id)

    if request.method == 'POST':
        # Start async task
        task = process_procurement_data.delay(str(upload.id))

        # Store task ID for tracking
        upload.celery_task_id = task.id
        upload.save()

        # Redirect to progress page
        return redirect('data_ingestion:processing_progress', upload_id=upload.id)
```

## Testing Strategy

### 1. Small File Test (5 records)
- Should complete in <1 second
- Verify all entities created
- Check progress updates

### 2. Medium File Test (500 records)
- Should show meaningful progress
- Test cancel functionality
- Verify batch processing

### 3. Large File Test (5000+ records)
- Monitor memory usage
- Check for timeouts
- Verify chunked processing

## Monitoring & Operations

### Start Workers
```bash
# Development
celery -A pricing_agent worker --loglevel=info

# Production (with concurrency)
celery -A pricing_agent worker --loglevel=info --concurrency=4
```

### Monitor Tasks
```bash
# Using Flower (web UI)
pip install flower
celery -A pricing_agent flower

# Access at http://localhost:5555
```

### Clear Failed Tasks
```python
# Django shell
from celery import current_app
current_app.control.purge()
```

## Benefits After Implementation

1. **Non-blocking UI**: Users can navigate while processing
2. **Progress Visibility**: Real-time updates on processing status
3. **Cancellation**: Ability to stop long-running imports
4. **Scalability**: Can add more workers for parallel processing
5. **Reliability**: Automatic retry on failures
6. **Monitoring**: Full visibility into task queue

## Success Metrics

- [ ] UI remains responsive during 5000+ row uploads
- [ ] Progress bar updates smoothly
- [ ] Cancel button stops processing within 2 seconds
- [ ] Failed tasks show clear error messages
- [ ] Can process multiple uploads simultaneously
- [ ] Memory usage stays under 500MB per worker

## Next After Celery

Once Celery is working:
1. **Conflict Resolution UI** (Priority 2)
2. **Data Quality Scoring** (Priority 3)
3. **Analytics Integration** (Priority 4)
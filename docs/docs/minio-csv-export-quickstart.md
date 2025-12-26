# MinIO CSV Export - Quick Start Guide

This guide will help you get started with MinIO CSV export in Superset.

## Prerequisites

1. MinIO server running and accessible
2. Superset installed and configured
3. MinIO Python client installed: `pip install minio`

## Step 1: Setup MinIO (Docker)

If you don't have MinIO running, start it with Docker:

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Access MinIO Console at http://localhost:9001 with credentials:
- Username: `minioadmin`
- Password: `minioadmin`

## Step 2: Configure Superset

Add to your `superset_config.py`:

```python
# Enable MinIO CSV Export
MINIO_EXPORT_CONFIG = {
    "enabled": True,
    "endpoint": "localhost:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "bucket_name": "superset-exports",
    "secure": False,
    "region": None,
    "max_rows_per_file": 1000000,
    "file_retention_seconds": 604800,  # 7 days
}
```

## Step 3: Restart Superset

```bash
superset run -p 8088 --with-threads --reload --debugger
```

## Step 4: Test the Feature

### Option A: From SQL Lab

1. Navigate to SQL Lab
2. Execute a query that returns data
3. Click the "Export" dropdown
4. Select "Export to MinIO"
5. Wait for the export to complete
6. Click the download link in the notification

**Note**: The export uses **true streaming** - memory usage stays constant even for billions of rows. The data streams from database → CSV generator → MinIO without loading the full dataset into memory.

### Option B: From Chart/Explore

1. Create or open a chart
2. Click the "..." menu
3. Hover over "Export to CSV"
4. Select "Original (to MinIO)" or "Pivoted (to MinIO)"
5. Wait for the export to complete
6. Click the download link in the notification

## Step 5: Verify in MinIO

1. Open MinIO Console at http://localhost:9001
2. Navigate to the `superset-exports` bucket
3. You should see your exported files in the `exports/` folder
4. Files are named with timestamp: `exports/YYYYMMDD_HHMMSS_filename.csv`

## Example: Large Dataset Export

For datasets with more than 1,000,000 rows (default `max_rows_per_file`):

1. The export will automatically split into multiple CSV files
2. Files will be archived into a ZIP file
3. The ZIP file will be uploaded to MinIO
4. You'll receive a download link to the ZIP file

Example:
- Query returns 2.5 million rows
- Creates 3 files: `export_1.csv`, `export_2.csv`, `export_3.csv`
- Archives to: `export.zip`
- Uploads to MinIO as: `exports/20231225_120000_export.zip`

## Example: Using the API Directly

### SQL Lab Export

```bash
curl -X POST "http://localhost:8088/api/v1/sqllab/export_minio/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=YOUR_CLIENT_ID&filename=my_export.csv"
```

### Chart Data Export

```bash
curl -X POST "http://localhost:8088/api/v1/chart/123/data_minio/" \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": {
      "slice_id": 123,
      "viz_type": "table"
    }
  }'
```

Response:
```json
{
  "object_name": "exports/20231225_120000_my_export.csv",
  "download_url": "https://localhost:9000/superset-exports/exports/20231225_120000_my_export.csv?...",
  "total_rows": 150000,
  "file_count": 1,
  "filename": "20231225_120000_my_export.csv"
}
```

## Example: Cleanup Old Files

To clean up files older than the retention period:

```python
from superset.utils.minio_storage import MinIOStorageManager

manager = MinIOStorageManager()
deleted_count = manager.cleanup_old_files()
print(f"Deleted {deleted_count} old files")
```

Or create a scheduled task:

```python
# In your superset_config.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'cleanup-minio-exports': {
        'task': 'superset.tasks.cleanup_minio_exports',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

## Troubleshooting

### "MinIO export is not enabled"

**Solution:** Ensure `MINIO_EXPORT_CONFIG["enabled"]` is `True` in your config and restart Superset.

### "minio package is required"

**Solution:** Install the MinIO client:
```bash
pip install minio
```

### Connection Refused

**Solution:** Check that MinIO is running and the endpoint is correct:
```bash
curl http://localhost:9000/minio/health/live
```

### Access Denied

**Solution:** Verify your credentials are correct and the bucket exists:
```bash
# Using MinIO Client (mc)
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc ls myminio/superset-exports
```

### Files Not Downloading

**Solution:** 
1. Check the presigned URL hasn't expired (valid for 1 hour)
2. Ensure your browser can access the MinIO endpoint
3. Check MinIO bucket policies allow downloads

## Advanced Configuration

### Production Setup with Environment Variables

```python
import os

MINIO_EXPORT_CONFIG = {
    "enabled": os.getenv("MINIO_EXPORT_ENABLED", "false").lower() == "true",
    "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    "access_key": os.getenv("MINIO_ACCESS_KEY"),
    "secret_key": os.getenv("MINIO_SECRET_KEY"),
    "bucket_name": os.getenv("MINIO_BUCKET_NAME", "superset-exports"),
    "secure": os.getenv("MINIO_SECURE", "false").lower() == "true",
    "region": os.getenv("MINIO_REGION"),
    "max_rows_per_file": int(os.getenv("MINIO_MAX_ROWS_PER_FILE", "1000000")),
    "file_retention_seconds": int(os.getenv("MINIO_FILE_RETENTION_SECONDS", "604800")),
}
```

Then set environment variables:
```bash
export MINIO_EXPORT_ENABLED=true
export MINIO_ENDPOINT=minio.example.com:9000
export MINIO_ACCESS_KEY=your_access_key
export MINIO_SECRET_KEY=your_secret_key
export MINIO_SECURE=true
```

### Custom Presigned URL Expiry

By default, URLs expire after 1 hour. To customize:

```python
# In your custom export code
from superset.utils.minio_storage import MinIOStorageManager

manager = MinIOStorageManager()
url = manager.get_presigned_download_url(
    object_name="exports/file.csv",
    expiry_seconds=7200  # 2 hours
)
```

### Monitoring and Alerts

Set up monitoring for:
- MinIO storage usage
- Export success/failure rates
- Average export time
- File sizes

Example with Prometheus metrics:
```python
from superset import app
from prometheus_client import Counter, Histogram

minio_exports_total = Counter(
    'superset_minio_exports_total',
    'Total MinIO exports',
    ['status']
)

minio_export_duration = Histogram(
    'superset_minio_export_duration_seconds',
    'MinIO export duration'
)
```

## Next Steps

1. **Security**: Set up proper IAM policies for MinIO bucket access
2. **Monitoring**: Add logging and metrics for export operations
3. **Automation**: Create scheduled exports for regular reports
4. **Optimization**: Tune `max_rows_per_file` based on your data characteristics
5. **Scaling**: Set up MinIO in distributed mode for high availability

## Support

For issues and questions:
- Check the [full documentation](minio-csv-export.md)
- Review [configuration examples](minio-csv-export-config-example.py)
- Check Superset logs for error messages
- Verify MinIO server logs

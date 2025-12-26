# MinIO CSV Export Feature

## Overview

This feature enables exporting large CSV datasets to MinIO object storage, with automatic file splitting for very large datasets. This is useful when:

- Exporting datasets that are too large to handle in-memory
- Need to export data for later download
- Want to share exported data with others via presigned URLs
- Need to manage storage of exported files centrally

## Configuration

Add the following configuration to your `superset_config.py`:

```python
# Enable MinIO export
MINIO_EXPORT_CONFIG = {
    "enabled": True,  # Set to True to enable MinIO export
    "endpoint": "localhost:9000",  # MinIO server endpoint
    "access_key": "your_access_key",  # MinIO access key
    "secret_key": "your_secret_key",  # MinIO secret key
    "bucket_name": "superset-exports",  # Bucket name for exports
    "secure": False,  # Set to True for HTTPS
    "region": None,  # Optional: AWS region (for S3-compatible services)
    # Maximum rows per CSV file before splitting into multiple files
    "max_rows_per_file": 1000000,
    # File retention in seconds (default: 7 days)
    "file_retention_seconds": 604800,
}
```

## Dependencies

Install the MinIO Python client:

```bash
pip install minio
```

Or add it to your requirements:

```
minio>=7.0.0
```

## Features

### True Streaming Architecture

The implementation uses **end-to-end streaming** to handle datasets of any size without memory issues:

1. **Database Level**: Uses SQLAlchemy's `stream_results=True` with server-side cursors
2. **Batch Processing**: Fetches rows in configurable chunks (default: 1000 rows)
3. **Memory-Efficient Upload**: Streams data directly to MinIO using BytesIO buffers
4. **Lazy Evaluation**: Python generators ensure data flows through the pipeline lazily

**Memory footprint remains constant regardless of dataset size** - suitable for billions of rows.

### Automatic File Splitting

When exporting datasets larger than `max_rows_per_file`, the export automatically:
1. Splits data into multiple CSV files
2. Creates a ZIP archive containing all files
3. Uploads the ZIP to MinIO
4. Returns a presigned download URL

Example:
- Export with 2.5 million rows and `max_rows_per_file=1000000`
- Creates 3 CSV files: `export_1.csv`, `export_2.csv`, `export_3.csv`
- Archives them into `export.zip`
- Uploads to MinIO

### Presigned URLs

Download URLs are presigned and valid for 1 hour by default. This means:
- No authentication required to download
- URLs expire after 1 hour for security
- Can be shared with others

### File Retention

Old export files are automatically cleaned up based on `file_retention_seconds`:
- Default: 7 days (604800 seconds)
- Cleanup runs when triggered manually or via scheduled task
- Helps manage storage costs

## Usage

### From SQL Lab

1. Execute your SQL query
2. Click the "Export" dropdown
3. Select "Export to MinIO" option
4. Wait for the export to complete
5. Click the download link in the success notification

### From Chart/Explore View

1. Create or edit your chart
2. Click the "..." menu
3. Select "Export to CSV" > "Original (to MinIO)" or "Pivoted (to MinIO)"
4. Wait for the export to complete
5. Click the download link in the success notification

## API Endpoints

### SQL Lab Export

```
POST /api/v1/sqllab/export_minio/
Content-Type: application/x-www-form-urlencoded

client_id=<query_client_id>
filename=<optional_filename>
```

Response:
```json
{
  "object_name": "exports/20231225_120000_export.csv",
  "download_url": "https://minio.example.com/...",
  "total_rows": 1500000,
  "file_count": 2,
  "filename": "20231225_120000_export.zip"
}
```

### Chart Data Export

```
POST /api/v1/chart/<chart_id>/data_minio/
Content-Type: application/json

{
  "form_data": { ... }
}
```

Response: Same as SQL Lab export

## Architecture

### Backend Components

1. **MinIOStorageManager** (`superset/utils/minio_storage.py`)
   - Handles MinIO client initialization
   - Manages file uploads and downloads
   - Implements file splitting logic
   - Generates presigned URLs

2. **Export Commands**
   - `MinIOChartExportCommand` - For chart data exports
   - `MinIOSqlLabExportCommand` - For SQL Lab exports
   - Both extend existing streaming export commands

3. **API Endpoints**
   - `SqlLabRestApi.export_minio()` - SQL Lab export endpoint
   - `ChartDataRestApi.data_minio()` - Chart data export endpoint

### Frontend Components

1. **ExportToCSVDropdown** (`superset-frontend/src/explore/components/ExportToCSVDropdown/`)
   - Updated to include MinIO export options
   - Shows options only when MinIO is enabled

2. **useMinIOExport Hook** (`superset-frontend/src/hooks/useMinIOExport.ts`)
   - Manages MinIO export state
   - Handles API calls
   - Shows success/error notifications

## Security Considerations

1. **Credentials**: Store MinIO credentials securely, not in version control
2. **Access Control**: Same permissions as regular CSV export
3. **Presigned URLs**: Expire after 1 hour by default
4. **File Retention**: Automatically clean up old files
5. **Bucket Permissions**: Ensure bucket has appropriate access policies

## Troubleshooting

### "MinIO export is not enabled"

Check your configuration:
- Ensure `MINIO_EXPORT_CONFIG["enabled"]` is `True`
- Restart Superset after configuration changes

### "minio package is required"

Install the MinIO client:
```bash
pip install minio
```

### Connection errors

Verify:
- MinIO endpoint is accessible from Superset server
- Credentials are correct
- Bucket exists and is accessible

### Files not being cleaned up

- Implement a scheduled task to call `MinIOStorageManager.cleanup_old_files()`
- Or run manually via Flask shell

## Performance Tips

1. **Chunk Size**: Adjust `chunk_size` parameter for database query performance
2. **File Splitting**: Larger `max_rows_per_file` creates fewer files but larger ZIPs
3. **Retention**: Shorter retention periods save storage costs
4. **Network**: Place MinIO close to Superset for faster uploads

## Future Enhancements

Potential improvements:
- Progress tracking for large uploads
- Custom presigned URL expiry times
- Direct streaming to MinIO without intermediate buffering
- Support for other object storage backends (S3, GCS, Azure Blob)
- Scheduled exports with automatic MinIO storage

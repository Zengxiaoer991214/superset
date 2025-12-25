# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Example MinIO Configuration for Superset

Add this to your superset_config.py to enable MinIO CSV export.
"""

# ========================================
# MinIO CSV Export Configuration
# ========================================

# Enable MinIO export feature
MINIO_EXPORT_CONFIG = {
    # Set to True to enable MinIO export functionality
    "enabled": True,
    
    # MinIO server endpoint (without http:// or https://)
    # For local development: "localhost:9000"
    # For production: "minio.yourdomain.com:9000"
    "endpoint": "localhost:9000",
    
    # MinIO access credentials
    # IMPORTANT: Store these securely, use environment variables in production
    # Example: os.getenv("MINIO_ACCESS_KEY")
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    
    # Bucket name for storing exports
    # The bucket will be created automatically if it doesn't exist
    "bucket_name": "superset-exports",
    
    # Use HTTPS for secure connections
    # Set to True if your MinIO server uses SSL/TLS
    "secure": False,
    
    # AWS region (optional, only needed for S3-compatible services)
    "region": None,
    
    # Maximum rows per CSV file before splitting into multiple files
    # Large datasets will be split and archived into a ZIP file
    # Recommended: 500000 - 2000000 depending on your data
    "max_rows_per_file": 1000000,
    
    # File retention period in seconds
    # Files older than this will be cleaned up
    # Default: 7 days (604800 seconds)
    # Examples:
    #   - 1 day: 86400
    #   - 3 days: 259200
    #   - 7 days: 604800
    #   - 30 days: 2592000
    "file_retention_seconds": 604800,
}

# ========================================
# Production Best Practices
# ========================================

# For production, use environment variables for credentials:
"""
import os

MINIO_EXPORT_CONFIG = {
    "enabled": os.getenv("MINIO_EXPORT_ENABLED", "false").lower() == "true",
    "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    "access_key": os.getenv("MINIO_ACCESS_KEY", ""),
    "secret_key": os.getenv("MINIO_SECRET_KEY", ""),
    "bucket_name": os.getenv("MINIO_BUCKET_NAME", "superset-exports"),
    "secure": os.getenv("MINIO_SECURE", "false").lower() == "true",
    "region": os.getenv("MINIO_REGION"),
    "max_rows_per_file": int(os.getenv("MINIO_MAX_ROWS_PER_FILE", "1000000")),
    "file_retention_seconds": int(os.getenv("MINIO_FILE_RETENTION_SECONDS", "604800")),
}
"""

# ========================================
# Docker Compose Example
# ========================================

"""
# Add this to your docker-compose.yml to run MinIO alongside Superset:

services:
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"  # MinIO Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

volumes:
  minio_data:

# Then in your Superset service, add:
  superset:
    # ... other config ...
    depends_on:
      - minio
    environment:
      MINIO_EXPORT_ENABLED: "true"
      MINIO_ENDPOINT: "minio:9000"
      MINIO_ACCESS_KEY: "minioadmin"
      MINIO_SECRET_KEY: "minioadmin"
      MINIO_BUCKET_NAME: "superset-exports"
      MINIO_SECURE: "false"
"""

# ========================================
# Kubernetes Example
# ========================================

"""
# ConfigMap for Superset configuration:
apiVersion: v1
kind: ConfigMap
metadata:
  name: superset-minio-config
data:
  minio.py: |
    import os
    MINIO_EXPORT_CONFIG = {
        "enabled": True,
        "endpoint": os.getenv("MINIO_ENDPOINT"),
        "access_key": os.getenv("MINIO_ACCESS_KEY"),
        "secret_key": os.getenv("MINIO_SECRET_KEY"),
        "bucket_name": "superset-exports",
        "secure": True,
        "region": "us-east-1",
        "max_rows_per_file": 1000000,
        "file_retention_seconds": 604800,
    }

# Secret for MinIO credentials:
apiVersion: v1
kind: Secret
metadata:
  name: minio-credentials
type: Opaque
data:
  access-key: <base64-encoded-access-key>
  secret-key: <base64-encoded-secret-key>

# Deployment with environment variables:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: superset
spec:
  template:
    spec:
      containers:
      - name: superset
        env:
        - name: MINIO_ENDPOINT
          value: "minio.minio-system.svc.cluster.local:9000"
        - name: MINIO_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: access-key
        - name: MINIO_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: secret-key
"""

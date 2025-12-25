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
"""MinIO storage utilities for CSV export."""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timedelta
from typing import Any, Generator, TYPE_CHECKING

from flask import current_app as app

if TYPE_CHECKING:
    from minio import Minio

logger = logging.getLogger(__name__)


class MinIOStorageManager:
    """
    Manager for storing CSV exports in MinIO object storage.

    Handles:
    - MinIO client initialization
    - Bucket management
    - File upload with streaming support
    - ZIP archive creation for multiple files
    - Presigned URL generation for downloads
    - File cleanup and retention policies
    """

    def __init__(self) -> None:
        """Initialize MinIO storage manager with configuration from app config."""
        self._client: Minio | None = None
        self._config: dict[str, Any] = {}

    def _initialize_client(self) -> Minio:
        """Initialize and return MinIO client."""
        if self._client is not None:
            return self._client

        try:
            from minio import Minio
        except ImportError as ex:
            raise ImportError(
                "minio package is required for MinIO export. "
                "Install it with: pip install minio"
            ) from ex

        self._config = app.config.get("MINIO_EXPORT_CONFIG", {})

        if not self._config.get("enabled", False):
            raise ValueError("MinIO export is not enabled in configuration")

        endpoint = self._config.get("endpoint", "localhost:9000")
        access_key = self._config.get("access_key", "")
        secret_key = self._config.get("secret_key", "")
        secure = self._config.get("secure", False)
        region = self._config.get("region")

        if not access_key or not secret_key:
            raise ValueError(
                "MinIO access_key and secret_key must be configured "
                "in MINIO_EXPORT_CONFIG"
            )

        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

        # Ensure bucket exists
        bucket_name = self._config.get("bucket_name", "superset-exports")
        if not self._client.bucket_exists(bucket_name):
            self._client.make_bucket(bucket_name)
            logger.info("Created MinIO bucket: %s", bucket_name)

        return self._client

    def get_max_rows_per_file(self) -> int:
        """Get the maximum rows per file from config."""
        return self._config.get("max_rows_per_file", 1000000)

    def upload_csv_file(
        self,
        filename: str,
        csv_data: str | bytes,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload a single CSV file to MinIO.

        Args:
            filename: Name of the file
            csv_data: CSV data as string or bytes
            metadata: Optional metadata to attach to the file

        Returns:
            The object name in MinIO
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")

        # Convert string to bytes if needed
        if isinstance(csv_data, str):
            csv_data = csv_data.encode("utf-8")

        # Create BytesIO object for upload
        data_stream = io.BytesIO(csv_data)
        data_length = len(csv_data)

        # Generate object name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"exports/{timestamp}_{filename}"

        # Upload to MinIO
        client.put_object(
            bucket_name,
            object_name,
            data_stream,
            data_length,
            content_type="text/csv",
            metadata=metadata or {},
        )

        logger.info(
            "Uploaded CSV file to MinIO: %s (%.2f MB)",
            object_name,
            data_length / (1024 * 1024),
        )

        return object_name

    def upload_csv_files_as_zip(
        self,
        csv_files: list[tuple[str, str | bytes]],
        zip_filename: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload multiple CSV files as a ZIP archive to MinIO.

        Args:
            csv_files: List of tuples (filename, csv_data)
            zip_filename: Name of the ZIP file
            metadata: Optional metadata to attach to the file

        Returns:
            The object name in MinIO
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")

        # Create ZIP archive in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zip_file:
            for csv_filename, csv_data in csv_files:
                if isinstance(csv_data, str):
                    csv_data = csv_data.encode("utf-8")
                zip_file.writestr(csv_filename, csv_data)

        # Get ZIP data
        zip_data = zip_buffer.getvalue()
        zip_length = len(zip_data)

        # Generate object name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"exports/{timestamp}_{zip_filename}"

        # Upload to MinIO
        zip_stream = io.BytesIO(zip_data)
        client.put_object(
            bucket_name,
            object_name,
            zip_stream,
            zip_length,
            content_type="application/zip",
            metadata=metadata or {},
        )

        logger.info(
            "Uploaded ZIP archive to MinIO: %s (%.2f MB, %d files)",
            object_name,
            zip_length / (1024 * 1024),
            len(csv_files),
        )

        return object_name

    def get_presigned_download_url(
        self, object_name: str, expiry_seconds: int = 3600
    ) -> str:
        """
        Generate a presigned URL for downloading a file from MinIO.

        Args:
            object_name: Name of the object in MinIO
            expiry_seconds: URL expiry time in seconds (default: 1 hour)

        Returns:
            Presigned URL for download
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")

        url = client.presigned_get_object(
            bucket_name, object_name, expires=timedelta(seconds=expiry_seconds)
        )

        logger.info("Generated presigned URL for: %s (expires in %ds)", object_name, expiry_seconds)

        return url

    def cleanup_old_files(self) -> int:
        """
        Clean up old export files based on retention policy.

        Returns:
            Number of files deleted
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")
        retention_seconds = self._config.get("file_retention_seconds", 604800)

        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(seconds=retention_seconds)

        try:
            objects = client.list_objects(bucket_name, prefix="exports/", recursive=True)
            for obj in objects:
                # Check if object is older than retention period
                if obj.last_modified and obj.last_modified < cutoff_time:
                    client.remove_object(bucket_name, obj.object_name)
                    deleted_count += 1
                    logger.debug("Deleted old export file: %s", obj.object_name)

            if deleted_count > 0:
                logger.info("Cleaned up %d old export files from MinIO", deleted_count)

        except Exception as ex:
            logger.error("Error during MinIO cleanup: %s", ex)
            raise

        return deleted_count

    def _upload_file_streaming(
        self,
        file_buffer: io.BytesIO,
        object_name: str,
    ) -> None:
        """
        Upload a file buffer to MinIO.

        Args:
            file_buffer: BytesIO buffer containing file data
            object_name: Name of the object in MinIO
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")

        file_buffer.seek(0)
        file_length = file_buffer.getbuffer().nbytes

        client.put_object(
            bucket_name,
            object_name,
            file_buffer,
            file_length,
            content_type="text/csv" if object_name.endswith(".csv") else "application/zip",
        )

        logger.info(
            "Uploaded to MinIO: %s (%.2f MB)",
            object_name,
            file_length / (1024 * 1024),
        )

    def stream_csv_to_minio(
        self,
        csv_generator: Generator[str, None, None],
        filename: str,
        max_rows_per_file: int | None = None,
    ) -> tuple[str, int, int]:
        """
        Stream CSV data to MinIO, splitting into multiple files if needed.
        
        Uses streaming to avoid loading all data into memory. Files are uploaded
        as they reach the max_rows_per_file threshold.

        Args:
            csv_generator: Generator yielding CSV data chunks
            filename: Base filename for the export
            max_rows_per_file: Maximum rows per file (None = no splitting)

        Returns:
            Tuple of (object_name, total_rows, file_count)
        """
        if max_rows_per_file is None:
            max_rows_per_file = self.get_max_rows_per_file()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uploaded_files: list[str] = []  # Store object names, not data
        current_file_buffer = io.BytesIO()
        current_file_rows = 0
        total_rows = 0
        file_index = 1
        header: str | None = None

        def finalize_current_file() -> None:
            """Upload current file buffer to MinIO and reset."""
            nonlocal current_file_buffer, current_file_rows, file_index, uploaded_files

            if current_file_buffer.tell() > 0:
                # Generate object name
                csv_filename = (
                    f"{filename.replace('.csv', '')}_{file_index}.csv"
                    if len(uploaded_files) > 0
                    else filename
                )
                object_name = f"exports/{timestamp}_{csv_filename}"

                # Upload to MinIO
                self._upload_file_streaming(current_file_buffer, object_name)
                uploaded_files.append(object_name)

                # Reset for next file
                current_file_buffer = io.BytesIO()
                current_file_rows = 0
                file_index += 1

        for chunk in csv_generator:
            # Check for error marker
            if "__STREAM_ERROR__" in chunk:
                raise ValueError(chunk.split(":", 1)[1].strip())

            lines = chunk.split("\n")

            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue

                # First line is header
                if header is None:
                    header = line
                    current_file_buffer.write((line + "\n").encode("utf-8"))
                    continue

                # Check if we need to start a new file
                if current_file_rows >= max_rows_per_file:
                    finalize_current_file()
                    # Start new file with header
                    current_file_buffer.write((header + "\n").encode("utf-8"))

                current_file_buffer.write((line + "\n").encode("utf-8"))
                current_file_rows += 1
                total_rows += 1

        # Finalize last file
        finalize_current_file()

        if len(uploaded_files) == 0:
            raise ValueError("No data to export")

        # If multiple files, create a ZIP with references
        if len(uploaded_files) > 1:
            # Download files, create ZIP, and upload
            object_name = self._create_zip_from_uploaded_files(
                uploaded_files, f"exports/{timestamp}_{filename.replace('.csv', '.zip')}"
            )
        else:
            object_name = uploaded_files[0]

        return object_name, total_rows, len(uploaded_files)

    def _create_zip_from_uploaded_files(
        self,
        object_names: list[str],
        zip_object_name: str,
    ) -> str:
        """
        Create a ZIP archive from already uploaded CSV files.

        Args:
            object_names: List of object names in MinIO
            zip_object_name: Name for the ZIP archive

        Returns:
            The ZIP object name
        """
        client = self._initialize_client()
        bucket_name = self._config.get("bucket_name", "superset-exports")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zip_file:
            for object_name in object_names:
                # Download file from MinIO
                response = client.get_object(bucket_name, object_name)
                file_data = response.read()
                response.close()
                response.release_conn()

                # Add to ZIP with just the filename (no path)
                filename = object_name.split("/")[-1]
                zip_file.writestr(filename, file_data)

                # Delete the individual CSV file
                client.remove_object(bucket_name, object_name)

        # Upload ZIP
        self._upload_file_streaming(zip_buffer, zip_object_name)

        logger.info(
            "Created ZIP archive: %s (%d files)",
            zip_object_name,
            len(object_names),
        )

        return zip_object_name


def is_minio_export_enabled() -> bool:
    """Check if MinIO export is enabled in configuration."""
    config = app.config.get("MINIO_EXPORT_CONFIG", {})
    return config.get("enabled", False)

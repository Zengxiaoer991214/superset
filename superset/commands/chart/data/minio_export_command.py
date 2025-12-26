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
"""MinIO export command for chart data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from superset.commands.chart.data.streaming_export_command import (
    StreamingCSVExportCommand,
)
from superset.utils.minio_storage import MinIOStorageManager

if TYPE_CHECKING:
    from superset.common.query_context import QueryContext

logger = logging.getLogger(__name__)


class MinIOChartExportCommand(StreamingCSVExportCommand):
    """
    Command to export chart data to MinIO storage.

    This command:
    - Inherits from StreamingCSVExportCommand for data retrieval
    - Streams CSV data to MinIO instead of HTTP response
    - Supports splitting large datasets into multiple files
    - Returns MinIO object information for download
    """

    def __init__(
        self,
        query_context: QueryContext,
        filename: str,
        chunk_size: int = 1000,
    ):
        """
        Initialize the MinIO chart export command.

        Args:
            query_context: The query context containing datasource and query details
            filename: Base filename for the export
            chunk_size: Number of rows to fetch per database query (default: 1000)
        """
        super().__init__(query_context, chunk_size)
        self._filename = filename
        self._minio_manager = MinIOStorageManager()

    def run(self) -> dict[str, str | int]:
        """
        Execute the MinIO export.

        Returns:
            Dictionary containing:
            - object_name: The MinIO object name
            - download_url: Presigned URL for download
            - total_rows: Total number of rows exported
            - file_count: Number of files created
            - filename: Final filename
        """
        # Get the CSV generator from parent class
        csv_generator_callable = super().run()
        csv_generator = csv_generator_callable()

        # Stream to MinIO with automatic file splitting
        object_name, total_rows, file_count = self._minio_manager.stream_csv_to_minio(
            csv_generator, self._filename
        )

        # Generate presigned download URL (valid for 1 hour)
        download_url = self._minio_manager.get_presigned_download_url(
            object_name, expiry_seconds=3600
        )

        # Determine final filename
        final_filename = object_name.split("/")[-1]

        logger.info(
            "MinIO chart export completed: %s (%d rows, %d files)",
            object_name,
            total_rows,
            file_count,
        )

        return {
            "object_name": object_name,
            "download_url": download_url,
            "total_rows": total_rows,
            "file_count": file_count,
            "filename": final_filename,
        }

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
"""Tests for MinIO storage utilities."""

from unittest.mock import MagicMock, patch

import pytest

from superset.utils.minio_storage import is_minio_export_enabled, MinIOStorageManager


def test_is_minio_export_enabled_when_disabled(app_context: None) -> None:
    """Test that MinIO export is correctly detected as disabled."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {"enabled": False}
        assert is_minio_export_enabled() is False


def test_is_minio_export_enabled_when_enabled(app_context: None) -> None:
    """Test that MinIO export is correctly detected as enabled."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {"enabled": True}
        assert is_minio_export_enabled() is True


def test_minio_manager_initialization_fails_when_disabled(app_context: None) -> None:
    """Test that MinIO manager raises error when disabled."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {"enabled": False}
        manager = MinIOStorageManager()

        with pytest.raises(ValueError, match="MinIO export is not enabled"):
            manager._initialize_client()


def test_minio_manager_initialization_fails_without_credentials(
    app_context: None,
) -> None:
    """Test that MinIO manager raises error without credentials."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {
            "enabled": True,
            "endpoint": "localhost:9000",
            "access_key": "",
            "secret_key": "",
        }
        manager = MinIOStorageManager()

        with pytest.raises(
            ValueError, match="access_key and secret_key must be configured"
        ):
            manager._initialize_client()


@patch("superset.utils.minio_storage.Minio")
def test_minio_manager_initialization_success(
    mock_minio_class: MagicMock, app_context: None
) -> None:
    """Test successful MinIO manager initialization."""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_minio_class.return_value = mock_client

    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {
            "enabled": True,
            "endpoint": "localhost:9000",
            "access_key": "test_key",
            "secret_key": "test_secret",
            "bucket_name": "test-bucket",
            "secure": False,
            "region": None,
        }
        manager = MinIOStorageManager()
        client = manager._initialize_client()

        assert client is not None
        mock_minio_class.assert_called_once()
        mock_client.bucket_exists.assert_called_once_with("test-bucket")


@patch("superset.utils.minio_storage.Minio")
def test_minio_manager_creates_bucket_if_not_exists(
    mock_minio_class: MagicMock, app_context: None
) -> None:
    """Test that MinIO manager creates bucket if it doesn't exist."""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_minio_class.return_value = mock_client

    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {
            "enabled": True,
            "endpoint": "localhost:9000",
            "access_key": "test_key",
            "secret_key": "test_secret",
            "bucket_name": "test-bucket",
            "secure": False,
            "region": None,
        }
        manager = MinIOStorageManager()
        manager._initialize_client()

        mock_client.make_bucket.assert_called_once_with("test-bucket")


def test_get_max_rows_per_file_default(app_context: None) -> None:
    """Test that default max rows per file is returned."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {
            "enabled": True,
        }
        manager = MinIOStorageManager()
        assert manager.get_max_rows_per_file() == 1000000


def test_get_max_rows_per_file_custom(app_context: None) -> None:
    """Test that custom max rows per file is returned."""
    with patch("superset.utils.minio_storage.app") as mock_app:
        mock_app.config.get.return_value = {
            "enabled": True,
            "max_rows_per_file": 500000,
        }
        manager = MinIOStorageManager()
        assert manager.get_max_rows_per_file() == 500000

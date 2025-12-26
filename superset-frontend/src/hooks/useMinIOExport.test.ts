/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { SupersetClient } from '@superset-ui/core';
import { useMinIOExport } from './useMinIOExport';

jest.mock('@superset-ui/core', () => ({
  ...jest.requireActual('@superset-ui/core'),
  SupersetClient: {
    post: jest.fn(),
  },
}));

jest.mock('src/components/MessageToasts/withToasts', () => ({
  addSuccessToast: jest.fn(),
  addDangerToast: jest.fn(),
}));

const mockMinIOResult = {
  object_name: 'exports/20231225_120000_test.csv',
  download_url: 'https://minio.example.com/download/test.csv',
  total_rows: 1000,
  file_count: 1,
  filename: '20231225_120000_test.csv',
};

describe('useMinIOExport', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should initialize with correct default state', () => {
    const { result } = renderHook(() => useMinIOExport());

    expect(result.current.isExporting).toBe(false);
    expect(result.current.exportResult).toBe(null);
  });

  test('should handle successful export', async () => {
    const onSuccess = jest.fn();
    (SupersetClient.post as jest.Mock).mockResolvedValue({
      json: mockMinIOResult,
    });

    const { result } = renderHook(() => useMinIOExport({ onSuccess }));

    result.current.exportToMinIO('/api/v1/test/export', {
      test: 'data',
    });

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });

    expect(result.current.exportResult).toEqual(mockMinIOResult);
    expect(onSuccess).toHaveBeenCalledWith(mockMinIOResult);
  });

  test('should handle export error', async () => {
    const onError = jest.fn();
    const errorMessage = 'Export failed';
    (SupersetClient.post as jest.Mock).mockRejectedValue(
      new Error(errorMessage),
    );

    const { result } = renderHook(() => useMinIOExport({ onError }));

    result.current.exportToMinIO('/api/v1/test/export', {
      test: 'data',
    });

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });

    expect(result.current.exportResult).toBe(null);
    expect(onError).toHaveBeenCalledWith(errorMessage);
  });

  test('should prevent concurrent exports', async () => {
    (SupersetClient.post as jest.Mock).mockImplementation(
      () =>
        new Promise(resolve =>
          setTimeout(() => resolve({ json: mockMinIOResult }), 100),
        ),
    );

    const { result } = renderHook(() => useMinIOExport());

    result.current.exportToMinIO('/api/v1/test/export', { test: 'data' });
    result.current.exportToMinIO('/api/v1/test/export', { test: 'data' });

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });

    expect(SupersetClient.post).toHaveBeenCalledTimes(1);
  });

  test('downloadFromMinIO should open URL in new tab', () => {
    const mockWindowOpen = jest.fn();
    global.window.open = mockWindowOpen;

    const { result } = renderHook(() => useMinIOExport());
    const testUrl = 'https://minio.example.com/download/test.csv';

    result.current.downloadFromMinIO(testUrl);

    expect(mockWindowOpen).toHaveBeenCalledWith(testUrl, '_blank');
  });
});

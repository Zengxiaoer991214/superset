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
import { useState, useCallback } from 'react';
import { SupersetClient, t } from '@superset-ui/core';
import { addSuccessToast, addDangerToast } from 'src/components/MessageToasts/withToasts';

interface MinIOExportResult {
  object_name: string;
  download_url: string;
  total_rows: number;
  file_count: number;
  filename: string;
}

interface UseMinIOExportOptions {
  onSuccess?: (result: MinIOExportResult) => void;
  onError?: (error: string) => void;
}

export const useMinIOExport = (options: UseMinIOExportOptions = {}) => {
  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState<MinIOExportResult | null>(
    null,
  );

  const exportToMinIO = useCallback(
    async (url: string, payload: Record<string, any>) => {
      setIsExporting(true);
      setExportResult(null);

      try {
        const response = await SupersetClient.post({
          endpoint: url,
          postPayload: payload,
        });

        const result = response.json as MinIOExportResult;
        setExportResult(result);

        const message =
          result.file_count > 1
            ? t(
                'Export completed: %s rows in %s files. Click to download.',
                result.total_rows,
                result.file_count,
              )
            : t('Export completed: %s rows. Click to download.', result.total_rows);

        addSuccessToast(message, {
          onClick: () => {
            window.open(result.download_url, '_blank');
          },
        });

        options.onSuccess?.(result);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Export failed';
        addDangerToast(t('MinIO export failed: %s', errorMessage));
        options.onError?.(errorMessage);
      } finally {
        setIsExporting(false);
      }
    },
    [options],
  );

  const downloadFromMinIO = useCallback(
    (downloadUrl: string) => {
      window.open(downloadUrl, '_blank');
    },
    [],
  );

  return {
    isExporting,
    exportResult,
    exportToMinIO,
    downloadFromMinIO,
  };
};

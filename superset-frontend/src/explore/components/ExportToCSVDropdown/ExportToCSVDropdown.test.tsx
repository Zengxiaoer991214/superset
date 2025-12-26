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
import { render, screen, userEvent } from 'spec/helpers/testing-library';
import { ExportToCSVDropdown } from './index';

const exportCSVOriginal = jest.fn();
const exportCSVPivoted = jest.fn();
const exportCSVOriginalMinio = jest.fn();
const exportCSVPivotedMinio = jest.fn();

const setup = (minioEnabled = false) =>
  render(
    <ExportToCSVDropdown
      exportCSVOriginal={exportCSVOriginal}
      exportCSVPivoted={exportCSVPivoted}
      exportCSVOriginalMinio={exportCSVOriginalMinio}
      exportCSVPivotedMinio={exportCSVPivotedMinio}
      minioEnabled={minioEnabled}
    >
      <div>.CSV</div>
    </ExportToCSVDropdown>,
  );

test('Dropdown button with menu renders', () => {
  setup();

  expect(screen.getByText('.CSV')).toBeVisible();

  userEvent.click(screen.getByText('.CSV'));
  expect(screen.getByRole('menu')).toBeInTheDocument();
  expect(screen.getByText('Original')).toBeInTheDocument();
  expect(screen.getByText('Pivoted')).toBeInTheDocument();
});

test('Call export csv original on click', () => {
  setup();

  userEvent.click(screen.getByText('.CSV'));
  userEvent.click(screen.getByText('Original'));

  expect(exportCSVOriginal).toHaveBeenCalled();
});

test('Call export csv pivoted on click', () => {
  setup();

  userEvent.click(screen.getByText('.CSV'));
  userEvent.click(screen.getByText('Pivoted'));

  expect(exportCSVPivoted).toHaveBeenCalled();
});

test('MinIO options not shown when disabled', () => {
  setup(false);

  userEvent.click(screen.getByText('.CSV'));
  expect(screen.queryByText('Original (to MinIO)')).not.toBeInTheDocument();
  expect(screen.queryByText('Pivoted (to MinIO)')).not.toBeInTheDocument();
});

test('MinIO options shown when enabled', () => {
  setup(true);

  userEvent.click(screen.getByText('.CSV'));
  expect(screen.getByText('Original (to MinIO)')).toBeInTheDocument();
  expect(screen.getByText('Pivoted (to MinIO)')).toBeInTheDocument();
});

test('Call export original to MinIO on click', () => {
  setup(true);

  userEvent.click(screen.getByText('.CSV'));
  userEvent.click(screen.getByText('Original (to MinIO)'));

  expect(exportCSVOriginalMinio).toHaveBeenCalled();
});

test('Call export pivoted to MinIO on click', () => {
  setup(true);

  userEvent.click(screen.getByText('.CSV'));
  userEvent.click(screen.getByText('Pivoted (to MinIO)'));

  expect(exportCSVPivotedMinio).toHaveBeenCalled();
});

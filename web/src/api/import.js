import client from './client';

/**
 * Upload a CSV file and get a preview of parsed rows (nothing is saved).
 * @param {File} file - CSV file
 * @param {string|null} month - Optional YYYY-MM override
 * @returns {Promise<import('../hooks/useImport').CSVPreviewResponse>}
 */
export async function previewCSVImport(file, month = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (month) formData.append('month', month);

  const response = await client.post('/import/csv', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Confirm and persist selected CSV rows as actual expenses.
 * @param {Array} rows - Array of CSVConfirmRow objects
 * @returns {Promise<{imported: number, skipped: number}>}
 */
export async function confirmCSVImport(rows) {
  const response = await client.post('/import/csv/confirm', { rows });
  return response.data;
}

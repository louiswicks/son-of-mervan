import client from './client';

/**
 * Trigger a file download from a blob response.
 * @param {Blob} blob
 * @param {string} filename
 */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Download expenses as CSV for the given month range.
 * @param {string} fromMonth  YYYY-MM
 * @param {string} toMonth    YYYY-MM
 */
export async function exportCSV(fromMonth, toMonth) {
  const res = await client.get('/export/csv', {
    params: { from: fromMonth, to: toMonth },
    responseType: 'blob',
  });
  downloadBlob(res.data, `budget_export_${fromMonth}_${toMonth}.csv`);
}

/**
 * Download a monthly budget report as PDF.
 * @param {string} month  YYYY-MM
 */
export async function exportPDF(month) {
  const res = await client.get('/export/pdf', {
    params: { month },
    responseType: 'blob',
  });
  downloadBlob(res.data, `budget_report_${month}.pdf`);
}

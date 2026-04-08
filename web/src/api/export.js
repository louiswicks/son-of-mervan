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

/**
 * Fetch the tax-year spending summary as JSON.
 * @param {number} taxYear  e.g. 2024 for April 2024 – April 2025
 * @returns {Promise<object>} TaxSummaryResponse
 */
export async function getTaxSummary(taxYear) {
  const res = await client.get('/export/tax-summary', {
    params: { tax_year: taxYear },
  });
  return res.data;
}

/**
 * Download an SA302-style PDF for the given UK tax year.
 * @param {number} taxYear  e.g. 2024 for April 2024 – April 2025
 */
export async function exportTaxPDF(taxYear) {
  const res = await client.get('/export/tax-pdf', {
    params: { tax_year: taxYear },
    responseType: 'blob',
  });
  downloadBlob(res.data, `tax_summary_${taxYear}_${taxYear + 1}.pdf`);
}

/**
 * Download a full account data backup as JSON.
 * Rate-limited to 1 request/hour server-side.
 */
export async function exportFullBackup() {
  const today = new Date().toISOString().slice(0, 10);
  const res = await client.get('/export/full-backup', { responseType: 'blob' });
  downloadBlob(res.data, `backup-${today}.json`);
}

/**
 * Download recurring expenses as an iCalendar (.ics) file.
 */
export async function exportCalendar() {
  const res = await client.get('/export/calendar.ics', { responseType: 'blob' });
  downloadBlob(res.data, 'recurring-expenses.ics');
}

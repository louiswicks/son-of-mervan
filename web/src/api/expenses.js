import client from './client';

export const getMonthlyTracker = (month, params = {}) =>
  client.get(`/monthly-tracker/${month}`, { params }).then((r) => r.data);

export const saveMonthlyTracker = (month, payload) =>
  client.post(`/monthly-tracker/${month}`, payload).then((r) => r.data);

export const updateExpense = (id, payload) =>
  client.put(`/expenses/${id}`, payload).then((r) => r.data);

export const deleteExpense = (id) =>
  client.delete(`/expenses/${id}`).then((r) => r.data);

export const getAnnualOverview = (year) =>
  client.get('/overview/annual', { params: { year } }).then((r) => r.data);

export const searchExpenses = ({ q, category, from: fromMonth, to: toMonth, page = 1, per_page = 20 } = {}) => {
  const params = { page, per_page };
  if (q) params.q = q;
  if (category && category !== 'All') params.category = category;
  if (fromMonth) params.from = fromMonth;
  if (toMonth) params.to = toMonth;
  return client.get('/expenses/search', { params }).then((r) => ({
    ...r.data,
    totalCount: parseInt(r.headers['x-total-count'] || '0', 10),
  }));
};

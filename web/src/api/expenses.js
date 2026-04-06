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

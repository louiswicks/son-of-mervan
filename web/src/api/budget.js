import client from './client';

export const calculateBudget = (payload, commit = false) =>
  client
    .post('/calculate-budget', payload, { params: { commit } })
    .then((r) => r.data);

export const copyBudgetForward = (from_month, to_month) =>
  client
    .post('/budget/copy-forward', { from_month, to_month })
    .then((r) => r.data);

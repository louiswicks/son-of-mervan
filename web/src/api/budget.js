import client from './client';

export const calculateBudget = (payload, commit = false) =>
  client
    .post('/calculate-budget', payload, { params: { commit } })
    .then((r) => r.data);

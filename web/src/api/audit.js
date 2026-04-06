import client from "./client";

export const getExpenseAudit = (expenseId) =>
  client.get(`/audit/expenses/${expenseId}`).then((r) => r.data);

import client from "./client";

export const listDebts = () => client.get("/debts");
export const createDebt = (payload) => client.post("/debts", payload);
export const updateDebt = (id, payload) => client.put(`/debts/${id}`, payload);
export const deleteDebt = (id) => client.delete(`/debts/${id}`);
export const getPayoffPlan = (strategy = "avalanche") =>
  client.get(`/debts/payoff-plan?strategy=${strategy}`);

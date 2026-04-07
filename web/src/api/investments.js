import client from "./client";

export const listInvestments = () =>
  client.get("/investments").then((r) => r.data);

export const getPortfolioSummary = () =>
  client.get("/investments/summary").then((r) => r.data);

export const createInvestment = (payload) =>
  client.post("/investments", payload).then((r) => r.data);

export const updateInvestment = (id, payload) =>
  client.put(`/investments/${id}`, payload).then((r) => r.data);

export const deleteInvestment = (id) =>
  client.delete(`/investments/${id}`);

export const syncPrices = () =>
  client.post("/investments/sync-prices").then((r) => r.data);

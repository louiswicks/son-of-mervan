import client from "./client";

export const listRecurring = () =>
  client.get("/recurring-expenses").then((r) => r.data);

export const createRecurring = (payload) =>
  client.post("/recurring-expenses", payload).then((r) => r.data);

export const updateRecurring = (id, payload) =>
  client.put(`/recurring-expenses/${id}`, payload).then((r) => r.data);

export const deleteRecurring = (id) =>
  client.delete(`/recurring-expenses/${id}`);

export const triggerGenerate = () =>
  client.post("/recurring-expenses/generate").then((r) => r.data);

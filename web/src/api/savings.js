import client from "./client";

export const listGoals = () =>
  client.get("/savings-goals").then((r) => r.data);

export const createGoal = (payload) =>
  client.post("/savings-goals", payload).then((r) => r.data);

export const updateGoal = (id, payload) =>
  client.put(`/savings-goals/${id}`, payload).then((r) => r.data);

export const deleteGoal = (id) =>
  client.delete(`/savings-goals/${id}`);

export const listContributions = (goalId) =>
  client.get(`/savings-goals/${goalId}/contributions`).then((r) => r.data);

export const addContribution = (goalId, payload) =>
  client.post(`/savings-goals/${goalId}/contributions`, payload).then((r) => r.data);

export const deleteContribution = (goalId, contribId) =>
  client.delete(`/savings-goals/${goalId}/contributions/${contribId}`);

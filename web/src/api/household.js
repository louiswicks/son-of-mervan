// src/api/household.js
import client from "./client";

export const getMyHousehold = () => client.get("/households/me").then((r) => r.data);

export const createHousehold = (name) =>
  client.post("/households", { name }).then((r) => r.data);

export const inviteMember = (email) =>
  client.post("/households/invite", { email }).then((r) => r.data);

export const joinHousehold = (token) =>
  client.post("/households/join", { token }).then((r) => r.data);

export const removeMember = (userId) =>
  client.delete(`/households/members/${userId}`).then((r) => r.data);

export const dissolveHousehold = () =>
  client.delete("/households").then((r) => r.data);

export const getHouseholdBudget = (month) =>
  client.get("/households/budget", { params: { month } }).then((r) => r.data);

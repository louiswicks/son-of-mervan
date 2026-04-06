import client from "./client";

// ---------- Budget Alerts ----------

export const listAlerts = () =>
  client.get("/budget-alerts").then((r) => r.data);

export const createAlert = (payload) =>
  client.post("/budget-alerts", payload).then((r) => r.data);

export const updateAlert = (id, payload) =>
  client.put(`/budget-alerts/${id}`, payload).then((r) => r.data);

export const deleteAlert = (id) =>
  client.delete(`/budget-alerts/${id}`);

// ---------- Notifications ----------

export const listNotifications = () =>
  client.get("/notifications").then((r) => r.data);

export const markNotificationRead = (id) =>
  client.patch(`/notifications/${id}/read`).then((r) => r.data);

export const markAllRead = () =>
  client.patch("/notifications/read-all");

export const deleteNotification = (id) =>
  client.delete(`/notifications/${id}`);

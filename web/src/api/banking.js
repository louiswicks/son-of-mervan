import client from "./client";

export const getConnectUrl = () =>
  client.get("/banking/connect").then((r) => r.data);

export const listConnections = () =>
  client.get("/banking/connections").then((r) => r.data);

export const syncTransactions = (connectionId) => {
  const params = connectionId ? { connection_id: connectionId } : {};
  return client.post("/banking/sync", null, { params }).then((r) => r.data);
};

export const disconnectBank = (id) =>
  client.delete(`/banking/connections/${id}`).then((r) => r.data);

export const listDrafts = (page = 1, pageSize = 25) =>
  client
    .get("/banking/drafts", { params: { page, page_size: pageSize } })
    .then((r) => r.data);

export const reviewDraft = (id, action, category) =>
  client
    .patch(`/banking/drafts/${id}`, { action, ...(category ? { category } : {}) })
    .then((r) => r.data);

export const confirmAllDrafts = () =>
  client.post("/banking/drafts/confirm-all").then((r) => r.data);

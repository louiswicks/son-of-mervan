import client from "./client";

export const listSnapshots = () => client.get("/net-worth/snapshots");
export const createSnapshot = (data) => client.post("/net-worth/snapshots", data);
export const updateSnapshot = (id, data) => client.put(`/net-worth/snapshots/${id}`, data);
export const deleteSnapshot = (id) => client.delete(`/net-worth/snapshots/${id}`);

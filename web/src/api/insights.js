import client from "./client";

export const getMonthlySummary = (month) =>
  client.get("/insights/monthly-summary", { params: { month } }).then((r) => r.data);

export const getSpendingTrends = (months = 6) =>
  client.get("/insights/trends", { params: { months } }).then((r) => r.data);

export const getSpendingHeatmap = (year) =>
  client.get("/insights/heatmap", { params: year ? { year } : {} }).then((r) => r.data);

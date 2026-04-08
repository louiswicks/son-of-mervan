import client from "./client";
import { useAuthStore } from "../store/authStore";

export const getMonthlySummary = (month) =>
  client.get("/insights/monthly-summary", { params: { month } }).then((r) => r.data);

export const getSpendingTrends = (months = 6) =>
  client.get("/insights/trends", { params: { months } }).then((r) => r.data);

export const getSpendingHeatmap = (year) =>
  client.get("/insights/heatmap", { params: year ? { year } : {} }).then((r) => r.data);

export const getSpendingPace = (month) =>
  client.get("/insights/pace", { params: { month } }).then((r) => r.data);

export const suggestCategory = (name) =>
  client.get("/insights/suggest-category", { params: { name } }).then((r) => r.data);

export const getHealthScore = (month) =>
  client.get("/insights/health-score", { params: { month } }).then((r) => r.data);

export const getAnomalyDetection = (month, lookback = 3) =>
  client
    .get("/insights/anomalies", { params: { month, lookback } })
    .then((r) => r.data);

/**
 * Stream an AI financial review for the given month.
 * Uses native fetch() so the response body can be read as a stream.
 *
 * @param {string} month - "YYYY-MM"
 * @param {(chunk: string) => void} onChunk - called with each text delta
 * @param {() => void} onDone - called when the stream ends cleanly
 * @param {(err: Error) => void} onError - called on any error
 * @returns {Promise<void>}
 */
export async function requestAIReview(month, onChunk, onDone, onError) {
  const baseUrl =
    process.env.REACT_APP_API_URL ||
    "https://son-of-mervan-production.up.railway.app";
  const token = useAuthStore.getState().token;

  let response;
  try {
    response = await fetch(
      `${baseUrl}/insights/ai-review?month=${encodeURIComponent(month)}`,
      {
        method: "POST",
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }
    );
  } catch (networkErr) {
    onError(new Error("Network error — could not reach the server."));
    return;
  }

  if (!response.ok) {
    let detail = "AI review failed.";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {}
    onError(new Error(detail));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process all complete SSE lines in the buffer
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep any incomplete trailing line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const payload = JSON.parse(line.slice(6));
          if (payload.chunk) onChunk(payload.chunk);
          if (payload.done) onDone();
          if (payload.error) onError(new Error(payload.error));
        } catch (_) {}
      }
    }
    // Flush remaining buffer
    if (buffer.startsWith("data: ")) {
      try {
        const payload = JSON.parse(buffer.slice(6));
        if (payload.chunk) onChunk(payload.chunk);
        if (payload.done) onDone();
        if (payload.error) onError(new Error(payload.error));
      } catch (_) {}
    }
  } catch (readErr) {
    onError(new Error("Stream interrupted."));
  }
}

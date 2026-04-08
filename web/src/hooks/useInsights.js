import { useQuery } from "@tanstack/react-query";
import { getMonthlySummary, getSpendingTrends, getSpendingHeatmap, getSpendingPace, suggestCategory, getHealthScore, getAnomalyDetection, getStreaks, getMonthCloseSummary } from "../api/insights";

export function useMonthlySummary(month) {
  return useQuery({
    queryKey: ["insights-summary", month],
    queryFn: () => getMonthlySummary(month),
    enabled: !!month,
    staleTime: 2 * 60 * 1000,
  });
}

export function useSpendingTrends(months = 6) {
  return useQuery({
    queryKey: ["insights-trends", months],
    queryFn: () => getSpendingTrends(months),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpendingHeatmap(year) {
  return useQuery({
    queryKey: ["insights-heatmap", year],
    queryFn: () => getSpendingHeatmap(year),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpendingPace(month) {
  return useQuery({
    queryKey: ["insights-pace", month],
    queryFn: () => getSpendingPace(month),
    enabled: !!month,
    staleTime: 2 * 60 * 1000,
  });
}

export function useHealthScore(month) {
  return useQuery({
    queryKey: ["insights-health-score", month],
    queryFn: () => getHealthScore(month),
    enabled: !!month,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnomalyDetection(month, lookback = 3) {
  return useQuery({
    queryKey: ["insights-anomalies", month, lookback],
    queryFn: () => getAnomalyDetection(month, lookback),
    enabled: !!month,
    staleTime: 2 * 60 * 1000,
  });
}

export function useStreaks() {
  return useQuery({
    queryKey: ["insights-streaks"],
    queryFn: getStreaks,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMonthCloseSummary(month) {
  return useQuery({
    queryKey: ["insights-month-close", month],
    queryFn: () => getMonthCloseSummary(month),
    enabled: !!month,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCategorySuggestion(name) {
  const trimmed = (name || "").trim();
  return useQuery({
    queryKey: ["insights-suggest-category", trimmed],
    queryFn: () => suggestCategory(trimmed),
    enabled: trimmed.length >= 2,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

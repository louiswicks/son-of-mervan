import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  listInvestments,
  getPortfolioSummary,
  createInvestment,
  updateInvestment,
  deleteInvestment,
  syncPrices,
} from "../api/investments";

export function useInvestments() {
  return useQuery({
    queryKey: ["investments"],
    queryFn: listInvestments,
    staleTime: 60_000,
  });
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ["investments-summary"],
    queryFn: getPortfolioSummary,
    staleTime: 60_000,
  });
}

export function useCreateInvestment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createInvestment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investments"] });
      qc.invalidateQueries({ queryKey: ["investments-summary"] });
      toast.success("Investment added");
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail;
      toast.error(detail || "Failed to add investment");
    },
  });
}

export function useUpdateInvestment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => updateInvestment(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investments"] });
      qc.invalidateQueries({ queryKey: ["investments-summary"] });
      toast.success("Investment updated");
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail;
      toast.error(detail || "Failed to update investment");
    },
  });
}

export function useDeleteInvestment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteInvestment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investments"] });
      qc.invalidateQueries({ queryKey: ["investments-summary"] });
      toast.success("Investment removed");
    },
    onError: () => toast.error("Failed to remove investment"),
  });
}

export function useSyncPrices() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: syncPrices,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["investments"] });
      qc.invalidateQueries({ queryKey: ["investments-summary"] });
      toast.success(data?.message || "Prices synced");
    },
    onError: () => toast.error("Failed to sync prices"),
  });
}

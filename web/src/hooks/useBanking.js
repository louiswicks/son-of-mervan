import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  confirmAllDrafts,
  disconnectBank,
  getConnectUrl,
  listConnections,
  listDrafts,
  reviewDraft,
  syncTransactions,
} from "../api/banking";

export function useConnections() {
  return useQuery({
    queryKey: ["banking-connections"],
    queryFn: listConnections,
    staleTime: 30_000,
  });
}

export function useDrafts(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: ["banking-drafts", page, pageSize],
    queryFn: () => listDrafts(page, pageSize),
    staleTime: 15_000,
  });
}

export function useConnectBank() {
  return useMutation({
    mutationFn: getConnectUrl,
    onSuccess: ({ auth_url }) => {
      window.location.href = auth_url;
    },
    onError: () => toast.error("Failed to start bank connection"),
  });
}

export function useSyncTransactions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (connectionId) => syncTransactions(connectionId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["banking-drafts"] });
      qc.invalidateQueries({ queryKey: ["banking-connections"] });
      toast.success(`Synced ${data.synced} transaction${data.synced !== 1 ? "s" : ""}`);
    },
    onError: (err) => {
      const msg =
        err?.response?.status === 429
          ? "Sync is rate-limited — please wait a few minutes before trying again"
          : "Sync failed — please try again";
      toast.error(msg);
    },
  });
}

export function useDisconnectBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => disconnectBank(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["banking-connections"] });
      qc.invalidateQueries({ queryKey: ["banking-drafts"] });
      toast.success("Bank disconnected");
    },
    onError: () => toast.error("Failed to disconnect bank"),
  });
}

export function useReviewDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, category }) => reviewDraft(id, action, category),
    onSuccess: (_, { action }) => {
      qc.invalidateQueries({ queryKey: ["banking-drafts"] });
      toast.success(action === "confirm" ? "Transaction confirmed" : "Transaction rejected");
    },
    onError: () => toast.error("Failed to update transaction"),
  });
}

export function useConfirmAllDrafts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: confirmAllDrafts,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["banking-drafts"] });
      toast.success(`Confirmed ${data.confirmed} transaction${data.confirmed !== 1 ? "s" : ""}`);
    },
    onError: () => toast.error("Failed to confirm all transactions"),
  });
}

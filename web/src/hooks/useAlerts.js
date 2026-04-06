import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  listAlerts,
  createAlert,
  updateAlert,
  deleteAlert,
  listNotifications,
  markNotificationRead,
  markAllRead,
  deleteNotification,
} from "../api/alerts";

// ---------- Budget Alerts ----------

export function useBudgetAlerts() {
  return useQuery({
    queryKey: ["budget-alerts"],
    queryFn: listAlerts,
    staleTime: 60_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createAlert,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget-alerts"] });
      toast.success("Alert created");
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || "Failed to create alert");
    },
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateAlert(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget-alerts"] });
      toast.success("Alert updated");
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || "Failed to update alert");
    },
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteAlert,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget-alerts"] });
      toast.success("Alert removed");
    },
    onError: () => toast.error("Failed to remove alert"),
  });
}

// ---------- Notifications ----------

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: listNotifications,
    staleTime: 30_000,
    refetchInterval: 60_000, // poll every minute for new notifications
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("All notifications marked as read");
    },
  });
}

export function useDeleteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteNotification,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    onError: () => toast.error("Failed to delete notification"),
  });
}

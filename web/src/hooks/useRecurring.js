import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  listRecurring,
  createRecurring,
  updateRecurring,
  deleteRecurring,
  triggerGenerate,
} from "../api/recurring";

export function useRecurring() {
  return useQuery({
    queryKey: ["recurring"],
    queryFn: listRecurring,
    staleTime: 60_000,
  });
}

export function useCreateRecurring() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createRecurring,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring"] });
      toast.success("Recurring expense created");
    },
    onError: () => toast.error("Failed to create recurring expense"),
  });
}

export function useUpdateRecurring() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => updateRecurring(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring"] });
      toast.success("Recurring expense updated");
    },
    onError: () => toast.error("Failed to update recurring expense"),
  });
}

export function useDeleteRecurring() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteRecurring,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring"] });
      toast.success("Recurring expense deleted");
    },
    onError: () => toast.error("Failed to delete recurring expense"),
  });
}

export function useTriggerGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerGenerate,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["monthly-tracker"] });
      toast.success(`Generated ${data.generated} planned row(s) for ${data.month}`);
    },
    onError: () => toast.error("Generation failed"),
  });
}

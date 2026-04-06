import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  listGoals,
  createGoal,
  updateGoal,
  deleteGoal,
  listContributions,
  addContribution,
  deleteContribution,
} from "../api/savings";

export function useSavingsGoals() {
  return useQuery({
    queryKey: ["savings-goals"],
    queryFn: listGoals,
    staleTime: 60_000,
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["savings-goals"] });
      toast.success("Savings goal created");
    },
    onError: () => toast.error("Failed to create savings goal"),
  });
}

export function useUpdateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => updateGoal(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["savings-goals"] });
      toast.success("Savings goal updated");
    },
    onError: () => toast.error("Failed to update savings goal"),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["savings-goals"] });
      toast.success("Savings goal deleted");
    },
    onError: () => toast.error("Failed to delete savings goal"),
  });
}

export function useContributions(goalId) {
  return useQuery({
    queryKey: ["savings-contributions", goalId],
    queryFn: () => listContributions(goalId),
    enabled: !!goalId,
    staleTime: 30_000,
  });
}

export function useAddContribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, data }) => addContribution(goalId, data),
    onSuccess: (_, { goalId }) => {
      qc.invalidateQueries({ queryKey: ["savings-goals"] });
      qc.invalidateQueries({ queryKey: ["savings-contributions", goalId] });
      toast.success("Contribution added");
    },
    onError: () => toast.error("Failed to add contribution"),
  });
}

export function useDeleteContribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, contribId }) => deleteContribution(goalId, contribId),
    onSuccess: (_, { goalId }) => {
      qc.invalidateQueries({ queryKey: ["savings-goals"] });
      qc.invalidateQueries({ queryKey: ["savings-contributions", goalId] });
      toast.success("Contribution removed");
    },
    onError: () => toast.error("Failed to remove contribution"),
  });
}

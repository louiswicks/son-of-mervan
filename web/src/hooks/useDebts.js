import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/debts";

export const useDebts = () =>
  useQuery({ queryKey: ["debts"], queryFn: api.listDebts });

export const usePayoffPlan = (strategy) =>
  useQuery({
    queryKey: ["debts", "payoff-plan", strategy],
    queryFn: () => api.getPayoffPlan(strategy),
  });

export const useCreateDebt = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createDebt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["debts"] }),
  });
};

export const useUpdateDebt = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => api.updateDebt(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["debts"] }),
  });
};

export const useDeleteDebt = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.deleteDebt(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["debts"] }),
  });
};

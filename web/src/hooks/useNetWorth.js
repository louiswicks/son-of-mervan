import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSnapshots, createSnapshot, updateSnapshot, deleteSnapshot } from "../api/netWorth";

export const useNetWorthSnapshots = () =>
  useQuery({
    queryKey: ["netWorth"],
    queryFn: () => listSnapshots().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

export const useCreateSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSnapshot,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["netWorth"] }),
  });
};

export const useUpdateSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => updateSnapshot(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["netWorth"] }),
  });
};

export const useDeleteSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSnapshot,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["netWorth"] }),
  });
};

// src/hooks/useHousehold.js
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getMyHousehold,
  createHousehold,
  inviteMember,
  joinHousehold,
  removeMember,
  dissolveHousehold,
  getHouseholdBudget,
} from "../api/household";

export function useMyHousehold() {
  return useQuery({
    queryKey: ["household"],
    queryFn: getMyHousehold,
    retry: (failureCount, error) => {
      // 404 = not in a household — don't retry
      if (error?.response?.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useCreateHousehold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createHousehold,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["household"] }),
  });
}

export function useInviteMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: inviteMember,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["household"] }),
  });
}

export function useJoinHousehold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: joinHousehold,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["household"] }),
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: removeMember,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["household"] }),
  });
}

export function useDissolveHousehold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: dissolveHousehold,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["household"] }),
  });
}

export function useHouseholdBudget(month) {
  return useQuery({
    queryKey: ["household-budget", month],
    queryFn: () => getHouseholdBudget(month),
    enabled: !!month,
  });
}

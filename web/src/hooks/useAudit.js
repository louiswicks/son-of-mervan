import { useQuery } from "@tanstack/react-query";
import { getExpenseAudit } from "../api/audit";

/**
 * Fetch the audit trail for a single expense.
 * Only fires when expenseId is non-null and the drawer is open.
 */
export function useExpenseAudit(expenseId, enabled = true) {
  return useQuery({
    queryKey: ["audit", "expense", expenseId],
    queryFn: () => getExpenseAudit(expenseId),
    enabled: enabled && expenseId != null,
    staleTime: 30_000,
  });
}

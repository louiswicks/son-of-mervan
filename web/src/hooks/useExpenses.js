import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMonthlyTracker,
  saveMonthlyTracker,
  updateExpense,
  deleteExpense,
} from '../api/expenses';
import { calculateBudget } from '../api/budget';
import toast from 'react-hot-toast';

export function useMonthlyTracker(month, { category, page = 1, pageSize = 25 } = {}) {
  return useQuery({
    queryKey: ['monthly-tracker', month, category, page],
    queryFn: () =>
      getMonthlyTracker(month, {
        _r: Date.now(),
        page,
        page_size: pageSize,
        ...(category && category !== 'All' ? { category } : {}),
      }),
    staleTime: 30 * 1000,
  });
}

export function useSaveMonthlyTracker(month) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ salary, rows }) => {
      const plannedExpenses = rows
        .filter((r) => r.projected !== '' && !isNaN(Number(r.projected)))
        .map((r) => ({
          name: r.name?.trim() || r.category,
          amount: Number(r.projected) || 0,
          category: r.category,
        }));

      if (plannedExpenses.some((e) => e.amount > 0)) {
        await calculateBudget(
          {
            month,
            monthly_salary: salary !== '' ? Number(salary) : 0,
            expenses: plannedExpenses,
          },
          true,
        );
      }

      const actualExpenses = rows
        .filter((r) => r.actual !== '' && !isNaN(Number(r.actual)))
        .map((r) => ({
          name: r.name?.trim() || r.category,
          amount: Number(r.actual) || 0,
          category: r.category,
        }));

      return saveMonthlyTracker(month, {
        salary: salary !== '' ? Number(salary) : null,
        expenses: actualExpenses,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monthly-tracker', month] });
      toast.success(`${month} data saved.`);
    },
    onError: () => {
      toast.error("Couldn't save monthly data. Please try again.");
    },
  });
}

export function useUpdateExpense(month) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateExpense(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monthly-tracker', month] });
      toast.success('Expense updated.');
    },
    onError: () => {
      toast.error("Couldn't save changes. Please try again.");
    },
  });
}

export function useDeleteExpense(month) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteExpense(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monthly-tracker', month] });
      toast.success('Expense deleted.');
    },
    onError: () => {
      toast.error("Couldn't delete the expense. Please try again.");
    },
  });
}

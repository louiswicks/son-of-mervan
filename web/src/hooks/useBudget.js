import { useMutation } from '@tanstack/react-query';
import { calculateBudget } from '../api/budget';
import toast from 'react-hot-toast';

export function useCalculateBudget() {
  return useMutation({
    mutationFn: ({ payload, commit = false }) => calculateBudget(payload, commit),
    onError: (err) => {
      toast.error(
        err.response?.data?.detail || err.message || 'Network error. Please try again.',
      );
    },
  });
}

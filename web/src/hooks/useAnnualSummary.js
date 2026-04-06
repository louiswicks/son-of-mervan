import { useQuery } from '@tanstack/react-query';
import { getAnnualOverview } from '../api/expenses';

export function useAnnualSummary(year) {
  return useQuery({
    queryKey: ['annual-overview', year],
    queryFn: () => getAnnualOverview(year),
    staleTime: 5 * 60 * 1000, // 5 min
  });
}

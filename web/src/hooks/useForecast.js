import { useQuery } from "@tanstack/react-query";
import { getForecast } from "../api/forecast";

export function useForecast(months = 3, salaryOverride = null) {
  return useQuery({
    queryKey: ["forecast", months, salaryOverride],
    queryFn: () => getForecast(months, salaryOverride),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

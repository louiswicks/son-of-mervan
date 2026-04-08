import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as categoriesApi from '../api/categories';

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: categoriesApi.getCategories,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: categoriesApi.createCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }) => categoriesApi.updateCategory(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: categoriesApi.deleteCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

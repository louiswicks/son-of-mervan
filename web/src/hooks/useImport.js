import { useMutation } from '@tanstack/react-query';
import { previewCSVImport, confirmCSVImport } from '../api/import';

/**
 * Mutation: parse a CSV file and return a preview.
 * Does NOT save anything. Call mutateAsync({ file, month }).
 */
export function useCSVPreview() {
  return useMutation({
    mutationFn: ({ file, month }) => previewCSVImport(file, month),
  });
}

/**
 * Mutation: persist confirmed rows. Call mutateAsync(rows).
 */
export function useCSVConfirm() {
  return useMutation({
    mutationFn: (rows) => confirmCSVImport(rows),
  });
}

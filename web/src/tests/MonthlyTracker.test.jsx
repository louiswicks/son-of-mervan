import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock recharts before any imports that use it
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  PieChart: ({ children }) => <div>{children}</div>,
  Pie: () => null,
  Cell: () => null,
  Tooltip: () => null,
  Legend: () => null,
  LineChart: ({ children }) => <div>{children}</div>,
  BarChart: ({ children }) => <div>{children}</div>,
  Line: () => null,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, loading: false }),
}));

// Mock Skeleton to render nothing
jest.mock('../components/Skeleton', () => ({
  SkeletonTable: () => <div data-testid="skeleton-table" />,
}));

const mockUpdateMutateAsync = jest.fn();
const mockDeleteMutateAsync = jest.fn();
const mockSaveMutateAsync = jest.fn();
let mockIsLoading = false;
let mockTrackerData = null;

jest.mock('../hooks/useExpenses', () => ({
  useMonthlyTracker: () => ({
    data: mockTrackerData,
    isLoading: mockIsLoading,
  }),
  useSaveMonthlyTracker: () => ({
    mutateAsync: mockSaveMutateAsync,
    isPending: false,
  }),
  useUpdateExpense: () => ({
    mutateAsync: mockUpdateMutateAsync,
    isPending: false,
  }),
  useDeleteExpense: () => ({
    mutateAsync: mockDeleteMutateAsync,
    isPending: false,
  }),
}));

import MonthlyTracker from '../components/MonthlyTracker';

const mockTrackerDataWithExpense = {
  salary_planned: 3000,
  salary_actual: 3000,
  expenses: {
    items: [
      {
        id: 42,
        category: 'Housing',
        name: 'Rent',
        planned_amount: 1200,
        actual_amount: 1200,
      },
    ],
    total: 1,
    pages: 1,
    page_size: 25,
  },
  total_actual: 1200,
  remaining_actual: 1800,
};

function renderMonthlyTracker() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MonthlyTracker />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockIsLoading = false;
  mockTrackerData = null;
  mockUpdateMutateAsync.mockResolvedValue({});
  mockDeleteMutateAsync.mockResolvedValue({});
  mockSaveMutateAsync.mockResolvedValue({});
});

describe('MonthlyTracker', () => {
  test('shows skeleton when isLoading=true', () => {
    mockIsLoading = true;
    renderMonthlyTracker();
    expect(screen.getByTestId('skeleton-table')).toBeInTheDocument();
  });

  test('renders salary input and expense rows from trackerData', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      // Salary input should be populated
      const salaryInput = screen.getByPlaceholderText(/e\.g\. 2500/i);
      expect(salaryInput).toBeInTheDocument();
    });
  });

  test('edit button appears only for rows with id', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      // The Housing row has id=42, so it should show an edit button
      const editButtons = screen.getAllByRole('button', { name: /edit expense/i });
      expect(editButtons.length).toBeGreaterThan(0);
    });
  });

  test('clicking edit button shows save and cancel buttons', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /edit expense/i }).length).toBeGreaterThan(0);
    });

    // Click first edit button — component renders both mobile card and desktop table,
    // so multiple edit/save/cancel buttons may exist.
    const editBtn = screen.getAllByRole('button', { name: /edit expense/i })[0];
    fireEvent.click(editBtn);

    await waitFor(() => {
      // After clicking edit, at least one Save changes + Cancel edit button should appear
      expect(screen.getAllByRole('button', { name: /save changes/i }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: /cancel edit/i }).length).toBeGreaterThan(0);
    });
  });

  test('clicking cancel returns to view mode', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /edit expense/i }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /edit expense/i })[0]);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /cancel edit/i }).length).toBeGreaterThan(0);
    });

    // Click the first cancel button
    fireEvent.click(screen.getAllByRole('button', { name: /cancel edit/i })[0]);

    await waitFor(() => {
      expect(screen.queryAllByRole('button', { name: /cancel edit/i })).toHaveLength(0);
      expect(screen.getAllByRole('button', { name: /edit expense/i }).length).toBeGreaterThan(0);
    });
  });

  test('clicking save calls updateMutation.mutateAsync with id and payload', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /edit expense/i }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /edit expense/i })[0]);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /save changes/i }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /save changes/i })[0]);

    await waitFor(() => {
      expect(mockUpdateMutateAsync).toHaveBeenCalledTimes(1);
      expect(mockUpdateMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ id: 42 }),
      );
    });
  });

  test('delete button opens ConfirmModal for rows with id', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /delete expense/i }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /delete expense/i })[0]);

    await waitFor(() => {
      // ConfirmModal renders with "Delete expense?" title
      expect(screen.getByText(/delete expense\?/i)).toBeInTheDocument();
    });
  });

  test('confirming delete calls deleteMutation.mutateAsync with the expense id', async () => {
    mockTrackerData = mockTrackerDataWithExpense;
    renderMonthlyTracker();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /delete expense/i }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /delete expense/i })[0]);

    await waitFor(() => {
      expect(screen.getByText(/delete expense\?/i)).toBeInTheDocument();
    });

    // Click the "Delete" confirm button in the modal
    const confirmButton = screen.getByRole('button', { name: /^delete$/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockDeleteMutateAsync).toHaveBeenCalledWith(42);
    });
  });
});

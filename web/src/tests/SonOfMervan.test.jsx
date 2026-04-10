import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock recharts before any imports that use it
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }) => <div>{children}</div>,
  BarChart: ({ children }) => <div>{children}</div>,
  PieChart: ({ children }) => <div>{children}</div>,
  Pie: () => null,
  Cell: () => null,
  Line: () => null,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

const mockMutateAsync = jest.fn();
let mockIsPending = false;

jest.mock('../hooks/useBudget', () => ({
  useCalculateBudget: () => ({
    mutateAsync: mockMutateAsync,
    isPending: mockIsPending,
  }),
}));

jest.mock('../hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: jest.fn() }),
}));

jest.mock('../hooks/useCategories', () => ({
  useCategories: () => ({ data: null }),
}));

jest.mock('../hooks/useInsights', () => ({
  useStreaks: () => ({ data: null }),
  useMonthCloseSummary: () => ({ data: null }),
}));

const mockGetMonthlyTracker = jest.fn();
jest.mock('../api/expenses', () => ({
  getMonthlyTracker: (...args) => mockGetMonthlyTracker(...args),
}));

jest.mock('react-hot-toast', () => {
  const toastFn = jest.fn();
  toastFn.success = jest.fn();
  toastFn.error = jest.fn();
  return { __esModule: true, default: toastFn };
});

import SonOfMervan from '../components/SonOfMervan';

const mockResultsData = {
  monthly_salary: 3000,
  total_expenses: 1500,
  remaining_budget: 1500,
  expenses_by_category: { Housing: 1000, Food: 500 },
};

function renderSonOfMervan() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SonOfMervan />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockIsPending = false;
  mockMutateAsync.mockResolvedValue(mockResultsData);
  mockGetMonthlyTracker.mockResolvedValue({
    salary_planned: 3000,
    expenses: {
      items: [
        { name: 'Rent', category: 'Housing', planned_amount: 1000, actual_amount: 0 },
        { name: 'Groceries', category: 'Food', planned_amount: 300, actual_amount: 0 },
      ],
      total: 2,
      page: 1,
      pages: 1,
    },
  });
});

describe('SonOfMervan', () => {
  test('renders "Son Of Mervan" heading', () => {
    renderSonOfMervan();
    expect(screen.getByText('Son Of Mervan')).toBeInTheDocument();
  });

  test('renders salary input and at least one expense row', () => {
    renderSonOfMervan();
    expect(screen.getAllByPlaceholderText(/0\.00/i).length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText(/e\.g\. rent/i)).toBeInTheDocument();
  });

  test('live stat cards shown initially; charts not shown until after Calculate', () => {
    renderSonOfMervan();
    // Live stats panel is always visible (greyed out until salary entered)
    expect(screen.getByText('Monthly Salary')).toBeInTheDocument();
    expect(screen.getByText('Total Expenses')).toBeInTheDocument();
    // Charts only appear after Calculate
    expect(screen.queryByText('Savings Projection')).not.toBeInTheDocument();
    expect(screen.queryByText('Expense Breakdown')).not.toBeInTheDocument();
  });

  test('"Add row" button adds a new expense row', () => {
    renderSonOfMervan();
    const nameInputsBefore = screen.getAllByPlaceholderText(/e\.g\. rent/i);
    fireEvent.click(screen.getByRole('button', { name: /add row/i }));
    const nameInputsAfter = screen.getAllByPlaceholderText(/e\.g\. rent/i);
    expect(nameInputsAfter.length).toBe(nameInputsBefore.length + 1);
  });

  test('Calculate button calls mutateAsync with correct payload', async () => {
    renderSonOfMervan();

    // Fill in salary — first 0.00 placeholder is the salary field
    const allInputs = screen.getAllByPlaceholderText(/0\.00/i);
    fireEvent.change(allInputs[0], { target: { value: '3000' } });

    // Fill in one expense
    const nameInput = screen.getByPlaceholderText(/e\.g\. rent/i);
    fireEvent.change(nameInput, { target: { value: 'Rent' } });
    fireEvent.change(allInputs[1], { target: { value: '1000' } });

    fireEvent.click(screen.getByRole('button', { name: /calculate budget/i }));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    });

    const callArg = mockMutateAsync.mock.calls[0][0];
    expect(callArg.commit).toBe(false);
    expect(callArg.payload.monthly_salary).toBe(3000);
    expect(callArg.payload.expenses[0]).toMatchObject({
      name: 'Rent',
      amount: 1000,
      category: 'Housing',
    });
  });

  test('after mutateAsync resolves with results, shows Expense Breakdown chart', async () => {
    renderSonOfMervan();

    const allInputs = screen.getAllByPlaceholderText(/0\.00/i);
    fireEvent.change(allInputs[0], { target: { value: '3000' } });

    const nameInput = screen.getByPlaceholderText(/e\.g\. rent/i);
    fireEvent.change(nameInput, { target: { value: 'Rent' } });
    fireEvent.change(allInputs[1], { target: { value: '1000' } });

    fireEvent.click(screen.getByRole('button', { name: /calculate budget/i }));

    await waitFor(() => {
      expect(screen.getByText('Savings Projection')).toBeInTheDocument();
      expect(screen.getByText('Expense Breakdown')).toBeInTheDocument();
    });
  });

  describe('Budget Templates', () => {
    test('"Use Template" button is visible', () => {
      renderSonOfMervan();
      expect(screen.getByRole('button', { name: /use template/i })).toBeInTheDocument();
    });

    test('clicking "Use Template" opens the template modal', () => {
      renderSonOfMervan();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Choose a Budget Template')).toBeInTheDocument();
    });

    test('modal shows all four templates', () => {
      renderSonOfMervan();
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      expect(screen.getByText('50/30/20 Rule')).toBeInTheDocument();
      expect(screen.getByText('Zero-Based')).toBeInTheDocument();
      expect(screen.getByText('Minimalist')).toBeInTheDocument();
      expect(screen.getByText('Student Budget')).toBeInTheDocument();
    });

    test('close button dismisses the modal', () => {
      renderSonOfMervan();
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /close template selector/i }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    test('selecting the 50/30/20 template populates expense rows', () => {
      renderSonOfMervan();
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      const useButtons = screen.getAllByRole('button', { name: /use this template/i });
      fireEvent.click(useButtons[0]); // 50/30/20
      // Modal should close
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      // Expense rows should now contain template names
      expect(screen.getByDisplayValue('Rent / Mortgage')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Groceries')).toBeInTheDocument();
    });

    test('applying template with salary pre-filled calculates amounts', () => {
      renderSonOfMervan();
      // Enter salary first
      const allInputs = screen.getAllByPlaceholderText(/0\.00/i);
      fireEvent.change(allInputs[0], { target: { value: '2000' } });

      // Apply minimalist template (Housing 35% of 2000 = 700)
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      const useButtons = screen.getAllByRole('button', { name: /use this template/i });
      fireEvent.click(useButtons[2]); // Minimalist

      // Housing row: 35% of 2000 = 700
      expect(screen.getByDisplayValue('700')).toBeInTheDocument();
    });

    test('applying template with no salary leaves amounts blank', () => {
      renderSonOfMervan();
      fireEvent.click(screen.getByRole('button', { name: /use template/i }));
      const useButtons = screen.getAllByRole('button', { name: /use this template/i });
      fireEvent.click(useButtons[2]); // Minimalist
      // All amount fields should be empty
      const amountInputs = screen.getAllByPlaceholderText(/0\.00/i);
      // First is salary (still empty), rest are expense amounts (also empty)
      amountInputs.forEach((input) => {
        expect(input.value).toBe('');
      });
    });
  });

  describe('Budget Copy Forward', () => {
    test('"Load [prev month]" button is rendered', () => {
      renderSonOfMervan();
      const btn = screen.getByTestId('load-prev-month-btn');
      expect(btn).toBeInTheDocument();
    });

    test('clicking load button pre-fills salary and expense rows from previous month', async () => {
      renderSonOfMervan();
      const btn = screen.getByTestId('load-prev-month-btn');
      fireEvent.click(btn);

      await waitFor(() => {
        // Salary field should be populated
        const salaryInput = screen.getAllByPlaceholderText(/0\.00/i)[0];
        expect(salaryInput.value).toBe('3000');
      });

      // Expense name fields should contain previous month's expenses
      expect(screen.getByDisplayValue('Rent')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Groceries')).toBeInTheDocument();
    });

    test('shows informational toast when previous month has no data', async () => {
      const toast = require('react-hot-toast').default;
      mockGetMonthlyTracker.mockResolvedValueOnce({
        salary_planned: 0,
        expenses: { items: [], total: 0, page: 1, pages: 0 },
      });

      renderSonOfMervan();
      fireEvent.click(screen.getByTestId('load-prev-month-btn'));

      await waitFor(() => {
        expect(toast).toHaveBeenCalledWith(
          expect.stringMatching(/no budget found/i),
          expect.objectContaining({ icon: 'ℹ️' })
        );
      });
    });
  });
});

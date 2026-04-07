import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
      <SonOfMervan />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockIsPending = false;
  mockMutateAsync.mockResolvedValue(mockResultsData);
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

  test('no results shown initially (no "Monthly Salary" result card)', () => {
    renderSonOfMervan();
    expect(screen.queryByText('Monthly Salary')).not.toBeInTheDocument();
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

  test('after mutateAsync resolves with results, shows result cards', async () => {
    renderSonOfMervan();

    const allInputs = screen.getAllByPlaceholderText(/0\.00/i);
    fireEvent.change(allInputs[0], { target: { value: '3000' } });

    const nameInput = screen.getByPlaceholderText(/e\.g\. rent/i);
    fireEvent.change(nameInput, { target: { value: 'Rent' } });
    fireEvent.change(allInputs[1], { target: { value: '1000' } });

    fireEvent.click(screen.getByRole('button', { name: /calculate budget/i }));

    await waitFor(() => {
      expect(screen.getByText('Monthly Salary')).toBeInTheDocument();
      expect(screen.getByText('Total Expenses')).toBeInTheDocument();
    });
  });
});

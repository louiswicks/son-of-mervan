import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CalendarPage from "../components/CalendarPage";

// ── Mock hooks ──────────────────────────────────────────────────────────────

jest.mock("../hooks/useRecurring", () => ({
  useRecurring: jest.fn(),
}));

jest.mock("../hooks/useSavings", () => ({
  useSavingsGoals: jest.fn(),
}));

// Suppress lucide-react SVG issues in jsdom
jest.mock("lucide-react", () => {
  const React = require("react");
  const icon = (name) => () => React.createElement("span", { "data-testid": name });
  return {
    CalendarDays: icon("CalendarDays"),
    Target: icon("Target"),
    ChevronLeft: icon("ChevronLeft"),
    ChevronRight: icon("ChevronRight"),
    Repeat: icon("Repeat"),
  };
});

const { useRecurring } = require("../hooks/useRecurring");
const { useSavingsGoals } = require("../hooks/useSavings");

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CalendarPage />
    </QueryClientProvider>
  );
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe("CalendarPage", () => {
  beforeEach(() => {
    useRecurring.mockReturnValue({ data: [], isLoading: false });
    useSavingsGoals.mockReturnValue({ data: [], isLoading: false });
  });

  test("renders heading and all 12 month names", () => {
    renderPage();
    expect(screen.getByText("Financial Calendar")).toBeInTheDocument();
    const months = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    ];
    months.forEach((m) => expect(screen.getByText(m)).toBeInTheDocument());
  });

  test("shows loading skeletons when data is loading", () => {
    useRecurring.mockReturnValue({ data: [], isLoading: true });
    useSavingsGoals.mockReturnValue({ data: [], isLoading: true });
    renderPage();
    const skeletons = screen.getAllByLabelText("Loading");
    expect(skeletons).toHaveLength(12);
  });

  test("shows 'No events' for empty months", () => {
    renderPage();
    const noEvents = screen.getAllByText("No events");
    // All 12 months are empty
    expect(noEvents).toHaveLength(12);
  });

  test("shows a monthly recurring expense in every month within its range", () => {
    useRecurring.mockReturnValue({
      data: [
        {
          id: 1,
          name: "Rent",
          category: "Housing",
          frequency: "monthly",
          start_date: "2026-01-01T00:00:00",
          end_date: null,
        },
      ],
      isLoading: false,
    });
    renderPage();
    // "Rent" should appear 12 times (once per month)
    const rentChips = screen.getAllByText(/Rent/);
    expect(rentChips.length).toBe(12);
  });

  test("shows a yearly recurring expense only in its anniversary month", () => {
    useRecurring.mockReturnValue({
      data: [
        {
          id: 2,
          name: "Annual Insurance",
          category: "Insurance",
          frequency: "yearly",
          start_date: "2026-03-15T00:00:00", // March
          end_date: null,
        },
      ],
      isLoading: false,
    });
    renderPage();
    const chips = screen.getAllByText(/Annual Insurance/);
    expect(chips.length).toBe(1); // only March
  });

  test("shows a savings goal deadline in the correct month", () => {
    const currentYear = new Date().getFullYear();
    useSavingsGoals.mockReturnValue({
      data: [
        {
          id: 10,
          name: "House Deposit",
          target_date: `${currentYear}-06-30T00:00:00`, // June of current year
          current_amount: 5000,
          target_amount: 20000,
        },
      ],
      isLoading: false,
    });
    renderPage();
    expect(screen.getByText("House Deposit")).toBeInTheDocument();
  });

  test("year navigation changes displayed year", () => {
    const currentYear = new Date().getFullYear();
    renderPage();
    expect(screen.getByText(String(currentYear))).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next year" }));
    expect(screen.getByText(String(currentYear + 1))).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous year" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous year" }));
    expect(screen.getByText(String(currentYear - 1))).toBeInTheDocument();
  });

  test("shows summary footer with recurring and goal counts", () => {
    useRecurring.mockReturnValue({
      data: [
        {
          id: 1,
          name: "Rent",
          category: "Housing",
          frequency: "monthly",
          start_date: "2026-01-01T00:00:00",
          end_date: null,
        },
      ],
      isLoading: false,
    });
    useSavingsGoals.mockReturnValue({
      data: [
        {
          id: 10,
          name: "Holiday",
          target_date: "2026-08-01T00:00:00",
          current_amount: 0,
          target_amount: 2000,
        },
      ],
      isLoading: false,
    });
    renderPage();
    expect(screen.getByText(/active recurring expense/)).toBeInTheDocument();
    expect(screen.getByText(/savings goal.*with deadline/)).toBeInTheDocument();
  });

  test("goal without target_date does not appear on calendar", () => {
    useSavingsGoals.mockReturnValue({
      data: [
        {
          id: 11,
          name: "Emergency Fund",
          target_date: null,
          current_amount: 500,
          target_amount: 5000,
        },
      ],
      isLoading: false,
    });
    renderPage();
    expect(screen.queryByText("Emergency Fund")).not.toBeInTheDocument();
  });
});

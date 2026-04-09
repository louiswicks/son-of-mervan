import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle, Circle, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

async function fetchOnboardingStatus() {
  const r = await api.get("/onboarding/status");
  return r.data;
}

async function dismissOnboarding() {
  const r = await api.post("/onboarding/dismiss");
  return r.data;
}

const STEP_ROUTES = {
  set_salary: "/budget",
  add_expense: "/budget",
  add_savings_goal: "/savings",
  add_recurring: "/recurring",
};

export default function OnboardingStatusWizard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [localDismissed, setLocalDismissed] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
    staleTime: 30_000,
  });

  const dismiss = useMutation({
    mutationFn: dismissOnboarding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["onboarding-status"] });
      setLocalDismissed(true);
    },
  });

  if (isLoading || !data) return null;
  if (data.completed || data.dismissed || localDismissed) return null;

  const steps = data.steps || [];
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-800">
        <button
          onClick={() => dismiss.mutate()}
          className="absolute right-4 top-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          aria-label="Dismiss onboarding"
        >
          <X className="h-5 w-5" />
        </button>

        <h2 className="mb-1 text-xl font-bold text-gray-900 dark:text-white">
          Welcome to Son of Mervan 👋
        </h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          Complete these steps to get the most out of your budget tracker.
          {doneCount > 0 && ` You've done ${doneCount} of ${steps.length}.`}
        </p>

        <ul className="mb-6 space-y-3">
          {steps.map((step) => (
            <li
              key={step.id}
              className="flex items-center gap-3 cursor-pointer group"
              onClick={() => {
                const route = STEP_ROUTES[step.id];
                if (route && !step.done) {
                  dismiss.mutate();
                  navigate(route);
                }
              }}
            >
              {step.done ? (
                <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-500" />
              ) : (
                <Circle className="h-5 w-5 flex-shrink-0 text-gray-300 group-hover:text-blue-400" />
              )}
              <span
                className={`text-sm ${
                  step.done
                    ? "text-gray-400 line-through dark:text-gray-500"
                    : "text-gray-700 group-hover:text-blue-600 dark:text-gray-200"
                }`}
              >
                {step.label}
              </span>
            </li>
          ))}
        </ul>

        <button
          onClick={() => dismiss.mutate()}
          className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          disabled={dismiss.isPending}
        >
          {doneCount === steps.length ? "Finish" : "Skip for now"}
        </button>
      </div>
    </div>
  );
}

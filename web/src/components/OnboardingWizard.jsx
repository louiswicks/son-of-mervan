// src/components/OnboardingWizard.jsx
import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  BarChart2, Bell, TrendingUp, Repeat, PiggyBank,
  ChevronRight, ChevronLeft, Check,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { useProfile } from "../hooks/useProfile";
import { useCurrencies } from "../hooks/useCurrency";
import { updateProfile } from "../api/users";
import { calculateBudget } from "../api/budget";

// ---------- Constants ----------

const PRESET_CATEGORIES = [
  { name: "Housing",        emoji: "🏠", description: "Rent, mortgage, maintenance" },
  { name: "Transportation", emoji: "🚗", description: "Fuel, travel, parking" },
  { name: "Food",           emoji: "🛒", description: "Groceries and dining" },
  { name: "Utilities",      emoji: "💡", description: "Energy, broadband, phone" },
  { name: "Insurance",      emoji: "🛡️", description: "Health, home, car" },
  { name: "Healthcare",     emoji: "💊", description: "Prescriptions, appointments" },
  { name: "Entertainment",  emoji: "🎬", description: "Subscriptions, hobbies, nights out" },
  { name: "Other",          emoji: "📦", description: "Everything else" },
];

const APP_FEATURES = [
  { icon: BarChart2,  text: "Plan monthly budgets and track actual spending" },
  { icon: TrendingUp, text: "Insights, trends, and AI-powered financial advice" },
  { icon: PiggyBank,  text: "Savings goals and investment portfolio tracking" },
  { icon: Bell,       text: "Budget alerts, recurring expenses, and scenarios" },
];

const TOTAL_STEPS = 3;

// ---------- Step indicator ----------

function StepDots({ current }) {
  return (
    <div className="flex items-center justify-center gap-2" aria-label={`Step ${current} of ${TOTAL_STEPS}`}>
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <div
          key={i}
          className={`rounded-full transition-all duration-300 ${
            i + 1 === current
              ? "w-6 h-2 bg-blue-400"
              : i + 1 < current
              ? "w-2 h-2 bg-blue-400/60"
              : "w-2 h-2 bg-white/20"
          }`}
        />
      ))}
    </div>
  );
}

// ---------- Step 1: Welcome ----------

function WelcomeStep({ onNext }) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="w-16 h-16 rounded-2xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center mb-6">
        <BarChart2 size={32} className="text-blue-400" />
      </div>
      <h1 className="text-3xl sm:text-4xl font-bold text-white mb-3">
        Welcome to SYITB
      </h1>
      <p className="text-blue-200 text-lg mb-8 max-w-sm">
        Start Your Income Tracking Budget — your personal finance companion.
      </p>

      <ul className="w-full max-w-sm space-y-3 mb-10 text-left">
        {APP_FEATURES.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-center gap-3 text-white/80">
            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
              <Icon size={16} className="text-blue-300" />
            </div>
            <span className="text-sm">{text}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onNext}
        className="w-full max-w-sm flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-6 rounded-xl transition-colors text-lg"
      >
        Get started <ChevronRight size={20} />
      </button>
    </div>
  );
}

// ---------- Step 2: Budget setup ----------

function BudgetSetupStep({ currencies, formData, onChange, onNext, onBack }) {
  const [salaryError, setSalaryError] = useState("");

  const handleNext = () => {
    if (!formData.salary || Number(formData.salary) <= 0) {
      setSalaryError("Please enter a valid monthly income.");
      return;
    }
    if (formData.categories.length < 1) {
      toast.error("Please select at least one expense category.");
      return;
    }
    setSalaryError("");
    onNext();
  };

  const toggleCategory = (name) => {
    const next = formData.categories.includes(name)
      ? formData.categories.filter((c) => c !== name)
      : [...formData.categories, name];
    onChange({ categories: next });
  };

  return (
    <div className="flex flex-col w-full">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-blue-300 hover:text-white text-sm mb-6 self-start"
      >
        <ChevronLeft size={16} /> Back
      </button>

      <h2 className="text-2xl font-bold text-white mb-1">Set up your budget</h2>
      <p className="text-blue-200 text-sm mb-6">Enter your income and pick your expense categories.</p>

      {/* Currency */}
      <label className="block text-sm font-medium text-blue-200 mb-1">
        Currency
      </label>
      <select
        value={formData.currency}
        onChange={(e) => onChange({ currency: e.target.value })}
        className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2.5 text-white text-[16px] mb-4 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        {(currencies ?? []).map((c) => (
          <option key={c.code} value={c.code} className="bg-gray-800 text-white">
            {c.code} — {c.name}
          </option>
        ))}
      </select>

      {/* Monthly salary */}
      <label className="block text-sm font-medium text-blue-200 mb-1">
        Monthly income (gross)
      </label>
      <input
        type="number"
        min="0"
        step="100"
        placeholder="e.g. 3000"
        value={formData.salary}
        onChange={(e) => { onChange({ salary: e.target.value }); setSalaryError(""); }}
        className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2.5 text-white text-[16px] placeholder-white/40 mb-1 focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      {salaryError && <p className="text-red-400 text-xs mb-2">{salaryError}</p>}
      {!salaryError && <p className="text-white/40 text-xs mb-4">You can update this anytime on the Budget page.</p>}

      {/* Category picker */}
      <p className="text-sm font-medium text-blue-200 mb-2">
        Expense categories <span className="text-white/40 font-normal">(pick at least one)</span>
      </p>
      <div className="grid grid-cols-2 gap-2 mb-6">
        {PRESET_CATEGORIES.map(({ name, emoji, description }) => {
          const selected = formData.categories.includes(name);
          return (
            <button
              key={name}
              type="button"
              onClick={() => toggleCategory(name)}
              aria-pressed={selected}
              className={`relative flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                selected
                  ? "bg-blue-600/30 border-blue-400 text-white"
                  : "bg-white/5 border-white/15 text-white/70 hover:bg-white/10 hover:border-white/30"
              }`}
            >
              {selected && (
                <span className="absolute top-2 right-2 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center">
                  <Check size={10} className="text-white" />
                </span>
              )}
              <span className="text-xl mb-1">{emoji}</span>
              <span className="text-sm font-medium leading-tight">{name}</span>
              <span className="text-xs text-white/50 leading-tight mt-0.5">{description}</span>
            </button>
          );
        })}
      </div>

      <button
        onClick={handleNext}
        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
      >
        Continue <ChevronRight size={18} />
      </button>
    </div>
  );
}

// ---------- Step 3: Confirm & Launch ----------

function ConfirmStep({ formData, onBack, onComplete, isLoading }) {
  const salary = Number(formData.salary) || 0;

  return (
    <div className="flex flex-col w-full">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-blue-300 hover:text-white text-sm mb-6 self-start"
        disabled={isLoading}
      >
        <ChevronLeft size={16} /> Back
      </button>

      <h2 className="text-2xl font-bold text-white mb-1">Ready to go!</h2>
      <p className="text-blue-200 text-sm mb-6">Here's your starting budget. You can adjust amounts on the Budget page.</p>

      {/* Summary card */}
      <div className="bg-white/10 rounded-2xl border border-white/20 p-5 mb-6 space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-white/60 text-sm">Currency</span>
          <span className="text-white font-semibold">{formData.currency}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-white/60 text-sm">Monthly income</span>
          <span className="text-white font-semibold">
            {formData.currency} {salary.toLocaleString()}
          </span>
        </div>
        <div>
          <span className="text-white/60 text-sm block mb-2">Categories</span>
          <div className="flex flex-wrap gap-2">
            {formData.categories.map((cat) => {
              const preset = PRESET_CATEGORIES.find((p) => p.name === cat);
              return (
                <span
                  key={cat}
                  className="bg-blue-600/30 border border-blue-400/40 text-blue-200 text-xs font-medium px-2.5 py-1 rounded-full"
                >
                  {preset?.emoji} {cat}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      <p className="text-white/40 text-xs text-center mb-4">
        Expense amounts default to £0 — set them on the Budget page.
      </p>

      <button
        onClick={onComplete}
        disabled={isLoading}
        className="w-full flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl transition-colors"
      >
        {isLoading ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Setting up…
          </>
        ) : (
          <>
            <Repeat size={18} /> Start Budgeting
          </>
        )}
      </button>
    </div>
  );
}

// ---------- Main wizard ----------

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const { data: profile, isLoading: profileLoading } = useProfile({ enabled: !authLoading && isAuthenticated });
  const { data: currencies } = useCurrencies();

  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    currency: "GBP",
    salary: "",
    categories: ["Housing", "Food", "Transportation"],
  });

  const completeMutation = useMutation({
    mutationFn: async ({ budgetPayload, profilePayload }) => {
      await calculateBudget(budgetPayload, true);
      return updateProfile(profilePayload);
    },
    onSuccess: (profileData) => {
      queryClient.setQueryData(["profile"], profileData);
      toast.success("Your budget is set up. Let's go!");
      navigate("/budget", { replace: true });
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || err.message || "Setup failed. Please try again.";
      toast.error(msg);
    },
  });

  const updateForm = (patch) => setFormData((prev) => ({ ...prev, ...patch }));

  const handleComplete = () => {
    const salary = Number(formData.salary) || 0;
    const now = new Date();
    const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

    const expenses = formData.categories.map((cat) => ({
      name: cat,
      category: cat,
      amount: 0,
    }));

    completeMutation.mutate({
      budgetPayload: { month, monthly_salary: salary, expenses },
      profilePayload: {
        base_currency: formData.currency,
        has_completed_onboarding: true,
      },
    });
  };

  // Auth loading — show spinner
  if (authLoading || profileLoading) {
    return (
      <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white" />
      </div>
    );
  }

  // Not authenticated → login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Already completed onboarding → skip to app
  if (profile?.has_completed_onboarding) {
    return <Navigate to="/budget" replace />;
  }

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Progress dots */}
        <div className="mb-8">
          <StepDots current={step} />
        </div>

        {/* Card */}
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6 sm:p-8 backdrop-blur-sm">
          {step === 1 && (
            <WelcomeStep onNext={() => setStep(2)} />
          )}
          {step === 2 && (
            <BudgetSetupStep
              currencies={currencies}
              formData={formData}
              onChange={updateForm}
              onNext={() => setStep(3)}
              onBack={() => setStep(1)}
            />
          )}
          {step === 3 && (
            <ConfirmStep
              formData={formData}
              onBack={() => setStep(2)}
              onComplete={handleComplete}
              isLoading={completeMutation.isPending}
            />
          )}
        </div>

        {/* Skip link */}
        {step === 1 && (
          <button
            onClick={() => {
              updateProfile({ has_completed_onboarding: true })
                .then((data) => {
                  queryClient.setQueryData(["profile"], data);
                  navigate("/budget", { replace: true });
                })
                .catch(() => navigate("/budget", { replace: true }));
            }}
            className="mt-4 w-full text-center text-white/40 hover:text-white/70 text-sm py-2 transition-colors"
          >
            Skip setup — I'll configure it manually
          </button>
        )}
      </div>
    </div>
  );
}

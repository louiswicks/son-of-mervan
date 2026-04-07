// src/App.jsx
// src/App.jsx
import React from "react";
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "./context/AuthContext";
import { router } from "./router";
import ErrorBoundary from "./components/ErrorBoundary";
import InstallBanner from "./components/InstallBanner";
import "./App.css";
import "./styles/tokens.css";
import "./styles/breakpoints.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
          <Toaster position="top-right" toastOptions={{ duration: 3000 }} />
          <InstallBanner />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

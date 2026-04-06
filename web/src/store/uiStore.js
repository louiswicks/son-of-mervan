// src/store/uiStore.js
// Zustand store for UI state (active modal, theme).
import { create } from 'zustand';

function getInitialTheme() {
  const stored = localStorage.getItem('theme');
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const useUiStore = create((set) => ({
  activeModal: null,
  theme: getInitialTheme(),

  openModal: (name) => set({ activeModal: name }),
  closeModal: () => set({ activeModal: null }),
  setTheme: (theme) => set({ theme }),
}));

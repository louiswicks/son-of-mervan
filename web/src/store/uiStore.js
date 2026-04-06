// src/store/uiStore.js
// Zustand store for UI state (active modal).
// Theme lives in useTheme hook (Phase 3.6).
import { create } from 'zustand';

export const useUiStore = create((set) => ({
  // Name of the currently open modal, or null if none.
  activeModal: null,

  openModal: (name) => set({ activeModal: name }),
  closeModal: () => set({ activeModal: null }),
}));

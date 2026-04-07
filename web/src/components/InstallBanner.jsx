import React, { useState, useEffect } from 'react';
import { Download, X } from 'lucide-react';

const DISMISSED_KEY = 'pwa-install-dismissed';

/**
 * Shows a bottom-anchored install banner when the browser fires
 * the `beforeinstallprompt` event and the user hasn't dismissed it before.
 */
export default function InstallBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      if (!localStorage.getItem(DISMISSED_KEY)) {
        setVisible(true);
      }
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setDeferredPrompt(null);
    }
    setVisible(false);
  };

  const handleDismiss = () => {
    setVisible(false);
    localStorage.setItem(DISMISSED_KEY, '1');
  };

  if (!visible) return null;

  return (
    <div
      role="banner"
      aria-label="Install app banner"
      className="fixed bottom-20 left-4 right-4 sm:left-auto sm:right-4 sm:w-80 z-50
                 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
                 rounded-xl shadow-lg p-4 flex items-start gap-3"
    >
      <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
        <Download size={18} className="text-blue-600 dark:text-blue-400" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-white">
          Install Son of Mervan
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Add to your home screen for quick access
        </p>
        <div className="flex gap-2 mt-3">
          <button
            onClick={handleInstall}
            className="flex-1 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white
                       hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2
                       focus:ring-blue-500 focus:ring-offset-1"
          >
            Install
          </button>
          <button
            onClick={handleDismiss}
            className="flex-1 py-1.5 text-xs font-medium rounded-lg border
                       border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300
                       hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1"
          >
            Not now
          </button>
        </div>
      </div>

      <button
        onClick={handleDismiss}
        aria-label="Close install banner"
        className="flex-shrink-0 p-1 rounded-lg text-gray-400 hover:text-gray-600
                   dark:hover:text-gray-200 transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}

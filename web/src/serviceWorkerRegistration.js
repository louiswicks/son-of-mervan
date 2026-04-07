/**
 * Service worker registration helper.
 * Only registers in production builds (avoids dev-mode cache staling).
 */
export function register() {
  if (process.env.NODE_ENV === 'production' && 'serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register(`${process.env.PUBLIC_URL}/service-worker.js`)
        .catch((err) => console.error('[SW] Registration failed:', err));
    });
  }
}

export function unregister() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => registration.unregister())
      .catch((err) => console.error('[SW] Unregister failed:', err));
  }
}

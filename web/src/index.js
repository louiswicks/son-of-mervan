import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from '@sentry/react';
import './index.css';
import App from './App.jsx';
import reportWebVitals from './reportWebVitals';
import { register as registerSW } from './serviceWorkerRegistration';

// Sentry is only active when REACT_APP_SENTRY_DSN is set at build time.
// Leave the variable unset in local development to keep the console clean.
if (process.env.REACT_APP_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.REACT_APP_SENTRY_DSN,
    environment: process.env.REACT_APP_ENVIRONMENT || 'development',
    release: `son-of-mervan@${process.env.REACT_APP_VERSION || '1.0.0'}`,
    // Capture 100% of performance transactions — tune down once baseline is known
    tracesSampleRate: 1.0,
    // Report React component names in breadcrumbs
    integrations: [Sentry.browserTracingIntegration()],
  });
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
registerSW();

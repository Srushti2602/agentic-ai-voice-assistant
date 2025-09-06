import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

// Suppress ResizeObserver errors globally
const resizeObserverErrorHandler = (e: ErrorEvent) => {
  if (e.message === 'ResizeObserver loop completed with undelivered notifications.') {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
};

// Also catch unhandled promise rejections
const resizeObserverPromiseHandler = (e: PromiseRejectionEvent) => {
  if (e.reason?.message?.includes('ResizeObserver loop completed')) {
    e.preventDefault();
    return false;
  }
};

window.addEventListener('error', resizeObserverErrorHandler);
window.addEventListener('unhandledrejection', resizeObserverPromiseHandler);

// Override console.error temporarily to filter ResizeObserver warnings
const originalConsoleError = console.error;
console.error = (...args) => {
  if (args[0]?.includes?.('ResizeObserver loop completed')) {
    return; // Suppress ResizeObserver errors
  }
  originalConsoleError.apply(console, args);
};

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

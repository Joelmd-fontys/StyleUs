import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth/AuthProvider';
import './index.css';
import { USE_LIVE_API_ITEMS, USE_LIVE_API_UPLOAD } from './lib/config';

const container = document.getElementById('root');

if (!container) {
  throw new Error('Root container not found');
}

const root = ReactDOM.createRoot(container);

const enableMocking = async () => {
  if (!import.meta.env.DEV) {
    return;
  }
  if (USE_LIVE_API_ITEMS && USE_LIVE_API_UPLOAD) {
    return;
  }
  const { startWorker } = await import('./mocks/browser');
  await startWorker();
};

enableMocking().finally(() => {
  root.render(
    <React.StrictMode>
      <AuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </React.StrictMode>
  );
});

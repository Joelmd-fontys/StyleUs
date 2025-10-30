import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error('Root container not found');
}

const root = ReactDOM.createRoot(container);

const enableMocking = async () => {
  if (import.meta.env.DEV) {
    const { startWorker } = await import('./mocks/browser');
    await startWorker();
  }
};

enableMocking().finally(() => {
  root.render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
});

import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

const GameApp = lazy(() => import('./App'));
const DashboardApp = lazy(() =>
  import('./dashboard/Dashboard').then((module) => ({
    default: module.Dashboard,
  })),
);
const isDashboard = window.location.pathname.startsWith('/dashboard');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Suspense fallback={<main className="route-loading">불러오는 중…</main>}>
      {isDashboard ? <DashboardApp /> : <GameApp />}
    </Suspense>
  </React.StrictMode>
);

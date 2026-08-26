import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const dashboardProxyTarget =
  process.env.VITE_DASHBOARD_PROXY_TARGET ??
  (process.env.CHOKIDAR_USEPOLLING === 'true'
    ? 'http://backend:8001'
    : 'http://127.0.0.1:8001');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/dashboard/state': dashboardProxyTarget,
      '/dashboard/events': dashboardProxyTarget,
      '/dashboard/agents': dashboardProxyTarget,
      '/agents': dashboardProxyTarget,
      '/sessions': dashboardProxyTarget,
    },
  },
});

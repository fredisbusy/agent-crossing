# Deployment change

1. Run `@agent-crossing/backend` on `127.0.0.1:8001` with a user LaunchAgent.
2. Route exact path `/ws/world` through Caddy to `127.0.0.1:8001`.
3. Keep the frontend reverse proxy on `127.0.0.1:3010`.
4. On HTTPS, derive `wss://<public-host>/ws/world` before applying the Vite dev fallback.
5. Verify port ownership, HTTP backend health, WebSocket upgrade, and the public page.

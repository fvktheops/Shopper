# LUVORA — ML & Real-time additions

This README documents the additional components added to provide a free, self-hosted ML and realtime support for LUVORA.

New components
- ml-service/: FastAPI-based ML service (embeddings + retrieval). Run with docker compose in docker-compose.ml.yml.
- worker/: Redis-backed worker to compute embeddings and update the on-disk index.
- socket-proxy/: Node.js socket.io + Redis subscriber that forwards ml:events to connected browser clients.
- infra/nginx/: Example nginx reverse-proxy configuration to route /ml/, /api/, and /socket.io/.
- hooks/post-receive: template hook to enqueue embedding jobs on repo push.
- ml-service/seed_repo.py: script to scan a repository directory and submit embedding jobs.
- frontend/static/js/ml-panel.js: small client-side module to call /ml/suggest and show results.
- scripts/seed_demo.sh: convenience script to seed a demo repo.

Quickstart (local dev)
1. Start ML services (redis, ml-service, worker):
   docker compose -f docker-compose.ml.yml up --build
   - ml-service is available at: http://localhost:8001
   - worker consumes jobs and updates ml-data/index.npz
2. Start socket-proxy (optional):
   - Build and run via docker (create a compose entry) or run locally with Node.js:
     cd socket-proxy
     npm install
     node index.js
   - socket-proxy listens on port 4002 by default and will emit events from Redis channel 'ml:events'.
3. Seed a repository (optional):
   ./scripts/seed_demo.sh /path/to/your/repo

Notes & next steps
- The provided nginx config is a template. Update upstream hostnames and ports to match your deployment and consider using Cloudflare Tunnel for secure exposure.
- The NPZ index is fine for small projects; switch to FAISS or other vector DB for larger datasets.
- The socket-proxy relays job events to the browser. Integrate it into the SPA via a socket.io client to show real-time progress.
- The post-receive hook uses git archive to extract files and posts them to the ml-service. Place it into your bare repo hooks directory and set ML_ENDPOINT if needed.

Security
- No paid APIs or external services are required.
- Do not commit secrets — use .env and Docker secrets for production.

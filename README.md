### Important notes & ethics

This change converts the project to a focused machine-learning telemetry and pattern-learning system.
Before deploying publicly:
- Obtain user consent before tracking. Do not collect personal data (PII) without explicit, lawful basis.
- Configure retention and deletion policies for user data.
- Follow GDPR/CCPA and other applicable regulations.

How the new ML pipeline works (summary)
- Frontend tracker (static/js/tracker.js) sends small, non-PII telemetry events to the server via POST /track.
- ml-service enqueues events into Redis list 'tracking:events' and appends them to a JSONL file for persistence.
- ml-learner worker consumes events, computes sentence-transformers embeddings, and performs online centroid-based clustering.
- Centroids and counts are persisted (ml-data/centroids.npy, centroid_counts.json) and insights are published to Redis channel 'ml:insights' and broadcast over WebSocket (/ws).
- The dashboard (index.html) subscribes to /ws and presents live insights and semantic retrieval via /ml/suggest.

Run locally
1. cp .env.ml.template .env
2. docker compose -f docker-compose.ml.yml up --build
3. Seed a repo (optional): ./scripts/seed_demo.sh /path/to/repo
4. Visit dashboard (serve index.html via static server or proxy through nginx to the same origin as ml-service)

Deploying safely
- Use Cloudflare Tunnel for secure exposure; see infra/cloudflared/config.yml for example.
- Protect /track, /ml/seed and seeding endpoints behind Auth for server-side operations.

If you want, I can further:
- Add a small admin UI to view clusters and download processed events.
- Add retention & purging features.
- Implement supervised reranker using logged clicks/feedback.

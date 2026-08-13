### ML & realtime: added socket-proxy service and FAISS migration

I added the socket-proxy service to docker-compose.ml.yml so you can bring up Redis, ml-service, worker, and socket-proxy in one command.

I also mounted the ML panel into a simple demo index.html at the repo root and added a copy of ml-panel.js to static/js so it can be served from /static/js/ml-panel.js.

Finally, I added a prototype FAISS migration script (scripts/migrate_to_faiss.py) that converts the existing NPZ index to a FAISS IndexFlatIP and writes metadata to faiss_meta.json.

Run instructions (one command to bring services up):
1. Copy env template:
   cp .env.ml.template .env
2. Start the ML stack (now includes socket-proxy):
   docker compose -f docker-compose.ml.yml up --build

Services and ports:
- ml-service: http://localhost:8001
- socket-proxy (socket.io relay): http://localhost:4002

Seed a repo if you haven't yet:
  ./scripts/seed_demo.sh /path/to/your/repo

Test suggest endpoint:
  curl -X POST http://localhost:8001/ml/suggest -H "Content-Type: application/json" -d '{"query":"read file","top_k":5}'

Migrate to FAISS (prototype):
  - Ensure faiss-cpu is installed in your Python env (pip install faiss-cpu) then run:
    python3 scripts/migrate_to_faiss.py

Notes & next steps:
- For production, secure /ml endpoints and proxy under your API origin if desired.
- The FAISS migration script is a prototype; for very large indexes consider partitioning or using FaissIVFFlat with training.

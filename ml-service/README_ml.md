# ML Service & Worker

This folder contains a small self-hosted ML service (ml-service) and a worker designed to compute embeddings
and perform retrieval operations using free, open-source models only.

Key components
- ml-service: FastAPI app exposing endpoints to enqueue embedding jobs and perform retrieval (suggestions).
- worker: simple Redis-backed worker that consumes jobs and updates a local on-disk embedding index.
- docker-compose.ml.yml: Compose file to run redis, ml-service, and ml-worker locally.

How to run locally (development)
1. Copy env template and adjust if needed:
   cp .env.ml.template .env
2. Start services with Docker Compose (requires Docker):
   docker compose -f docker-compose.ml.yml up --build
3. ML service will be available at http://localhost:8001

Endpoints
- POST /ml/embeddings/job  -> enqueue embeddings job (body: { items: [{path, text}, ...] })
- POST /ml/embeddings/compute -> compute embeddings synchronously (for small jobs)
- POST /ml/suggest -> { query: 'some text', top_k: 5 } returns top-k similar items
- GET /ml/index/status -> index status
- GET /health -> health check

Notes
- This implementation uses sentence-transformers (all-MiniLM-L6-v2) for embeddings (free).
- Vector storage is a simple on-disk numpy NPZ file (ml-data/index.npz). For larger repos use FAISS or other vector DB.
- No paid providers are used. If you later add a GPU and model files, the worker can be extended to run local model inference.

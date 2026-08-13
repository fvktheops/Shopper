Updated: Integrated ML panel with WebSocket events, FAISS-backed indexing in ml-service and worker, removed separate socket-proxy from compose and now ml-service broadcasts events via /ws.

Run instructions (updated):
1. Prepare env: cp .env.ml.template .env
2. Start services: docker compose -f docker-compose.ml.yml up --build
   - ml-service: http://localhost:8001 (also exposes WebSocket at ws://localhost:8001/ws)
3. Seed a repo: ./scripts/seed_demo.sh /path/to/repo
4. Test suggest: curl -X POST http://localhost:8001/ml/suggest -H "Content-Type: application/json" -d '{"query":"read file","top_k":5}'
5. FAISS migrate: pip install faiss-cpu && python3 scripts/migrate_to_faiss.py

Note: faiss-cpu may not have wheels for all platforms; if installation fails, the system will continue using NPZ fallback. The ml-service will attempt to load FAISS and will work with NPZ if FAISS unavailable.

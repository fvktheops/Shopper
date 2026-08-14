# README metrics section

Prometheus metrics
- The ml-service exposes Prometheus metrics at /metrics (default port 8001 when using docker compose mapping).
- A local Prometheus server is included in docker-compose (localhost:9090) and will scrape ml-service as configured in infra/prometheus/prometheus.yml.

How to run and verify
1. Start services:
   docker compose -f docker-compose.ml.yml up --build
2. Visit Prometheus UI at http://localhost:9090 and run queries like:
   - http_requests_total{endpoint="/ml/suggest"}
   - rate_limit_blocked_total
   - ml_jobs_queue_depth
3. Quick check via script:
   ./scripts/check_metrics.sh

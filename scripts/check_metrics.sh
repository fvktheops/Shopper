#!/bin/bash
# Check metrics locally by curling the /metrics endpoint and grepping key metrics
set -e
echo "ml-service metrics summary:\n"
curl -s http://localhost:8001/metrics | egrep 'http_requests_total|ml_jobs_queue_depth|tracking_events_queue_depth|faiss_index_size|rate_limit_blocked_total|redis_errors_total' || true

echo "\nPrometheus UI: http://localhost:9090 (if running via docker compose)"

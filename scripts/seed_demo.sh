#!/bin/bash
# Seed demo repo by calling the ml-service seed script
REPO_DIR=${1:-./sample-repo}
ML_URL=${ML_URL:-http://localhost:8001}
PY=${PYTHON:-python3}

if [ ! -d "$REPO_DIR" ]; then
  echo "Repo not found: $REPO_DIR"; exit 1
fi

echo "Seeding repo $REPO_DIR -> ML service at $ML_URL"
$PY ml-service/seed_repo.py "$REPO_DIR"

# LUVORA (Shopper)

This repository is a scaffold for LUVORA — a GitHub-like platform prototype. It includes a Node.js + Express backend, a React + Vite frontend, and Docker Compose to run PostgreSQL and Redis for realtime features.

Features in this initial scaffold
- Backend API (Express) with endpoints to create and list repositories (real git integration using simple-git)
- Frontend (React + Vite) with a minimal UI to create repositories and view the list
- Docker Compose configuration for local development (postgres, redis, backend, frontend)
- Socket.io present in the backend for future realtime features

Next steps
- Implement authentication (JWT)
- Add database models and migrations (Postgres)
- Add issues, PRs, code viewer, and realtime notifications using Socket.io + Redis adapter
- Add CI, tests, and deployment workflows

Getting started (local development)

Prerequisites: Git, Docker, Docker Compose

1. Clone the repo
   git clone https://github.com/fvktheops/Shopper.git
   cd Shopper

2. Start services
   docker compose up --build

3. Backend API available at: http://localhost:4000
   Frontend available at: http://localhost:5173

Notes
- Repositories created by the API will be stored under ./data/repos on the host (persisted)
- This scaffold uses simple-git and therefore requires the Git binary to be available inside the backend container (the Dockerfile installs git)


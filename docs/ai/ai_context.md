# Silver Safe Platform AI Context

## Current Project

银龄安全系统（Silver Safe Platform）

Architecture: WeChat Mini Program + FastAPI Backend + SQLite testing
database.
Architecture: WeChat Mini Program + HTTPS + Caddy Reverse Proxy + FastAPI Backend + SQLite testing database (WAL mode).

## Current Phase

Volunteer Testing Deployment.
Phase 5: Public Cloud Deployment & Volunteer Real Device Acceptance.

Completed: - Backend API - Mini Program - Backend tests 94/94 - Mini
Program tests 27/27 - testing environment isolation
Completed:
- Backend API & DB models
- Mini Program elder & family pages with anti-jitter polyline rendering
- Backend tests 94/94 passed
- Mini Program tests 27/27 passed
- 10 isolated testing accounts & 1:1 bindings (elder_test_01~10 & family_test_01~10)
- Pre-seeded enabled WGS84 Geofences & active Trips
- Safe testing reset & automated readiness verification ([GO])
- Live E2E smoke test suite (13/13 passed)
- Full deployment package under deploy/ (Caddyfile, systemd service, setup_server.sh)

Pending: - HTTPS deployment - Real domain - WeChat legal domain -
Volunteer account isolation - Real device E2E test
Pending:
- Cloud VM setup & DNS A-record binding
- HTTPS activation via Caddy Let's Encrypt
- WeChat request合法域名 configuration
- Mini Program testing URL switch
- Real device dual-phone E2E acceptance test

## Architecture Rules

Backend Authority: All safety decisions belong to Backend.

Backend: - authentication - authorization - trip lifecycle - location
storage - freshness - risk status - safety calculation
Backend:
- authentication
- authorization
- trip lifecycle
- location storage
- freshness calculation
- risk status calculation
- safety view generation

Frontend: - collect GPS - upload data - display results
Frontend:
- collect GPS
- upload data
- display results

Do not: - calculate risk in client - calculate freshness in client -
move safety logic to frontend
Do not:
- calculate risk in client
- calculate freshness in client
- move safety logic to frontend

## Important Files

Backend: backend/app/main.py backend/app/services/safety.py
backend/app/services/seed.py
Backend:
- backend/app/main.py
- backend/app/services/safety.py
- backend/app/services/seed.py

Mini Program: miniprogram/config.js miniprogram/services/location.js
miniprogram/services/map.js
Mini Program:
- miniprogram/config.js
- miniprogram/services/location.js
- miniprogram/services/map.js

Deployment & Scripts:
- deploy/Caddyfile
- deploy/silver-safe-testing.service
- deploy/setup_server.sh
- scripts/reset_testing.py
- scripts/verify_testing_readiness.py

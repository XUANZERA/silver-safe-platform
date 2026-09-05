# Silver Safe Platform AI Context

## Current Project

银龄安全系统（Silver Safe Platform）

Architecture: WeChat Mini Program + FastAPI Backend + SQLite testing
database.

## Current Phase

Volunteer Testing Deployment.

Completed: - Backend API - Mini Program - Backend tests 94/94 - Mini
Program tests 27/27 - testing environment isolation

Pending: - HTTPS deployment - Real domain - WeChat legal domain -
Volunteer account isolation - Real device E2E test

## Architecture Rules

Backend Authority: All safety decisions belong to Backend.

Backend: - authentication - authorization - trip lifecycle - location
storage - freshness - risk status - safety calculation

Frontend: - collect GPS - upload data - display results

Do not: - calculate risk in client - calculate freshness in client -
move safety logic to frontend

## Important Files

Backend: backend/app/main.py backend/app/services/safety.py
backend/app/services/seed.py

Mini Program: miniprogram/config.js miniprogram/services/location.js
miniprogram/services/map.js

# DealPilot AI — Starter MVP

Industry-independent sales intelligence platform. This starter establishes the API and React dashboard foundation. It uses SQLite locally so it runs without a database server; the data model is intentionally generic and can later be moved to PostgreSQL.

## Requirements
- Python 3.11+
- Node.js 20+ and npm
- VS Code (recommended)

## 1. Start the backend (Windows PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

If PowerShell blocks activation, run this once in the current terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend:
- API: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## 2. Start the frontend (a second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

## What is included
- Generic records for products/services, customers, and deals
- API endpoints to create/list products, customers and deals
- Dashboard analytics derived from the database (not hardcoded graph values)
- Demo seed endpoint for clearly labelled synthetic test data
- React dashboard that fetches data from the API

## Important
The seed endpoint creates fictional sample records only. Never treat demo data as real business performance.
This is Phase 1. Meeting transcription, business memory, forecasting and prescriptive recommendations will be added in later phases.
License

DealPilot AI is licensed under the MIT License. See the LICENSE file for details.

Copyright (c) 2026 Deekshith Kumar K.

If you use or adapt this project, please retain the original copyright and license notices and consider crediting the original project:

DealPilot AI — originally developed by Deekshith Kumar K.

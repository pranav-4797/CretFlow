# CertFlow Architecture — Firestore-Backed Free-Tier Batch Engine

## System Architecture

```
                    ┌─────────────────────────────────────┐
                    │            User Browser              │
                    │   React + Vite + TypeScript          │
                    │   Tailwind CSS + shadcn/ui           │
                    │   Framer Motion animations           │
                    └──────────────┬──────────────────────┘
                                   │ HTTPS
                    ┌──────────────▼──────────────────────┐
                    │       Firebase Hosting               │
                    │   (Frontend static hosting)          │
                    │   https://certflow-ab935.web.app     │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐  ┌────────▼────────────────┐  ┌▼──────────────────┐
    │ Firebase Auth    │  │ FastAPI Backend         │  │ Google Shared Drive│
    │ (Authentication) │  │ (Render Free Web Svc)   │  │ (Certificate PDFs) │
    └──────────────────┘  │ https://certflow.onrender│ └───────────────────┘
                          └────────┬────────────────┘
                                   │
                          ┌────────▼────────────────┐
                          │   Firebase Firestore    │
                          │   (Sole Database &      │
                          │    Batch Job State Store│
                          │    - campaigns          │
                          │    - participants       │
                          │    - email_jobs         │
                          │    - gmail_connections) │
                          └────────┬────────────────┘
                                   │
                          ┌────────▼────────────────┐
                          │   Official Gmail API    │
                          │   (users.messages.send) │
                          └─────────────────────────┘
```

## Backend Services Structure

```
backend/
├── main.py                          # FastAPI application factory & lifespan
├── app/
│   ├── core/
│   │   ├── config.py                # Pydantic settings (env vars)
│   │   ├── firebase.py              # Firebase Admin SDK initialization
│   │   ├── logging.py               # structlog structured JSON logging
│   │   ├── security.py              # Firebase Auth ID token verification
│   │   └── encryption.py            # Fernet AES token encryption
│   ├── services/
│   │   ├── firestore_service.py     # Firestore repository (Campaigns, Jobs, Leases, Tokens)
│   │   ├── batch_engine.py          # In-process batch engine (10–25 batch, 1–3 concurrency)
│   │   ├── reconciler.py            # Startup recovery & lease reconciliation
│   │   ├── drive_service.py         # Google Shared Drive API v3 operations
│   │   ├── certificate_service.py   # PDF certificate rendering & Drive upload
│   │   └── gmail_service.py         # Gmail OAuth 2.0 & users.messages.send
│   ├── schemas/                     # Pydantic validation schemas
│   └── api/                         # REST endpoints (auth, campaigns, emails, gmail, storage)
```

## Core Design Principles

1. **Free-Tier Compatibility:** Operates completely inside a single free-tier Render Web Service and Firebase Free Spark plan without paid add-ons.
2. **Resumable Batching:** Bulk certificate sending is broken into small batches (default 15 recipients). Each recipient's state is stored in Firestore (`queued`, `processing`, `sent`, `retrying`, `failed`, `unknown`, `cancelled`).
3. **Atomic Leases & Dual-Process Protection:** Background workers acquire time-limited Firestore job leases (`lease_expires_at`). Competing workers cannot process the same job or participants.
4. **Render Sleep Recovery:** If the free Render service spins down during inactivity, `RestartReconciler` detects expired leases upon wake-up/activity and resets stuck recipients for seamless resumption.
5. **Zero Redis & Neon:** Upstash Redis, Celery background workers, Neon PostgreSQL, and SQLAlchemy ORM have been completely excised.

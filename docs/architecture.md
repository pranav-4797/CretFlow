# CertFlow Architecture — Phase 1 Foundation

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
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐  ┌────────▼───────┐  ┌────────▼────────┐
    │ Firebase Auth    │  │ FastAPI Backend │  │ Cloudflare R2   │
    │ (Authentication) │  │ (Render)        │  │ (File Storage)  │
    └─────────┬────────┘  └────────┬───────┘  └────────┬────────┘
              │                    │                    │
              │           ┌────────▼───────┐           │
              │           │ Neon PostgreSQL │           │
              │           │ (Database)      │           │
              │           └────────────────┘           │
              │                    │                    │
              │           ┌────────▼───────┐           │
              │           │ Celery Worker   │◄──────────┘
              │           │ (Render)        │
              │           └────────┬───────┘
              │                    │
              │           ┌────────▼───────┐
              │           │ Upstash Redis   │
              │           │ (Task Queue)    │
              │           └────────────────┘
              │
    ┌─────────▼────────┐
    │   Gmail API      │
    │ (Email Delivery) │
    └──────────────────┘
```

## Frontend Structure

```
frontend/src/
├── components/
│   ├── ui/               # shadcn/ui base components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── label.tsx
│   │   ├── progress.tsx
│   │   ├── separator.tsx
│   │   ├── toast.tsx
│   │   └── toaster.tsx
│   ├── layout/
│   │   └── AppLayout.tsx  # Sidebar layout for authenticated pages
│   └── routing/
│       └── ProtectedRoute.tsx  # Auth guards
├── contexts/
│   └── AuthContext.tsx    # Firebase auth context
├── hooks/
│   └── use-toast.ts       # Toast notification hook
├── lib/
│   └── utils.ts           # Shared utilities (cn, formatDate, etc.)
├── pages/
│   ├── LandingPage.tsx    # Marketing page
│   ├── LoginPage.tsx      # Sign in
│   ├── SignupPage.tsx     # Sign up
│   ├── DashboardPage.tsx  # Main dashboard
│   ├── CampaignsPage.tsx  # Campaign list
│   ├── SettingsPage.tsx   # User settings
│   ├── VerifyPage.tsx     # Certificate verification (public)
│   └── NotFoundPage.tsx   # 404
├── services/
│   └── api.ts             # API client with auth token injection
├── types/
│   └── index.ts           # TypeScript domain types
└── test/
    ├── setup.ts           # Vitest setup + mocks
    └── phase1.test.tsx    # Phase 1 tests
```

## Backend Structure

```
backend/
├── main.py                # FastAPI application factory
├── app/
│   ├── core/
│   │   ├── config.py      # Pydantic settings (env vars)
│   │   ├── database.py    # SQLAlchemy engine & session
│   │   ├── firebase.py    # Firebase Admin initialization
│   │   ├── logging.py     # structlog configuration
│   │   └── security.py   # get_current_user dependency
│   └── api/
│       ├── router.py      # Central API router
│       └── endpoints/
│           ├── auth.py     # /api/auth
│           ├── campaigns.py # /api/campaigns
│           ├── participants.py # /api/participants
│           ├── templates.py # /api/templates
│           ├── certificates.py # /api/certificates
│           ├── gmail.py    # /api/gmail
│           ├── emails.py   # /api/emails
│           └── reports.py  # /api/reports
├── worker/
│   ├── celery_app.py      # Celery configuration
│   └── tasks/
│       ├── certificates.py # Certificate generation tasks
│       └── emails.py       # Email sending tasks
└── tests/
    └── test_phase1.py     # Phase 1 backend tests
```

## API Endpoints (Phase 1 Status)

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/health` | GET | ✅ | Public health check |
| `/api/docs` | GET | ✅ | Swagger UI |
| `/api/auth/status` | GET | ✅ | Firebase config status |
| `/api/auth/me` | GET | 🔒 | Requires Firebase auth (Phase 2) |
| `/api/campaigns/*` | * | 🚧 | Phase 3 |
| `/api/participants/*` | * | 🚧 | Phase 4 |
| `/api/templates/*` | * | 🚧 | Phase 5 |
| `/api/certificates/*` | * | 🚧 | Phase 6 |
| `/api/gmail/*` | * | 🚧 | Phase 8 |
| `/api/emails/*` | * | 🚧 | Phase 10 |
| `/api/reports/*` | * | 🚧 | Phase 11 |

## Security Model

- Firebase ID tokens are verified server-side for every protected request
- Users can only access their own data (owner checks added in Phase 3)
- Gmail OAuth 2.0 — refresh tokens stored encrypted in database
- Files stored in R2 with secure keys — never on Render filesystem
- CORS restricted to known frontend origins

## Development vs Production

| Config | Development | Production |
|--------|------------|-----------|
| Database | Local PostgreSQL | Neon PostgreSQL |
| Redis | Local Redis | Upstash Redis |
| Storage | R2 dev bucket | R2 prod bucket |
| Logging | Colored console | JSON (log aggregation) |
| CORS | All localhost | Specific domain |
| Trusted Hosts | Disabled | Backend hostname |

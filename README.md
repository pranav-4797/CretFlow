# CertFlow 🎓

> **Automated Certificate Generation & Verified Distribution Platform**

CertFlow allows event organizers, educators, and hackathons to upload spreadsheets, map participant details, render personalized PDF certificates, store them in Google Shared Drive, and distribute them in reliable batches via the organizer's connected Gmail account.

Hosted on **Firebase Hosting** (Frontend) and **Render Free-Tier Web Service** (Backend) with **Firebase Firestore** as the sole primary database and job state store.

---

## 🚀 Key Architecture Highlights

* **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion
* **Frontend Hosting:** Firebase Hosting (`https://certflow-ab935.web.app`)
* **Backend:** Python 3.12, FastAPI
* **Backend Hosting:** Render Web Service (`https://certflow.onrender.com`)
* **Primary Database:** Firebase Cloud Firestore (No Neon PostgreSQL, no SQLAlchemy, no migrations)
* **Job State & Queue:** Firestore-backed bounded batch processing with atomic leases (No Celery, no Redis, no Upstash)
* **File Storage:** Google Shared Drive (`CertFlow`) via Google Drive API v3 and Google Cloud Service Account
* **Email Distribution:** Official Gmail API (`users.messages.send`) via Google OAuth 2.0 user authorization

---

## ⚡ Background Batch Processing & Render Free-Tier Resilience

1. **Bounded Batches:** Campaigns process in configurable batches (default 15 recipients) with bounded concurrency (1–3 workers) to protect memory and respect Gmail API quotas.
2. **Authoritative Firestore State:** Every recipient transition (`queued` → `processing` → `sent` / `retrying` / `failed` / `unknown` / `cancelled`) is persisted in Firestore.
3. **Dual-Process Protection:** Uses atomic Firestore job leases with timeout (`lease_expires_at`). Multiple requests or threads cannot process the same recipients.
4. **Render Free-Tier Sleep Recovery:** Free Render instances spin down after 15 minutes of inactivity. When the service awakens (on startup or dashboard activity), `RestartReconciler` automatically reclaims expired leases and resets interrupted recipients for smooth resumption.
5. **Truthful Progress:** Dashboard displays honest counts computed directly from Firestore participant documents.
6. **Campaign Controls:** Full support for pausing, resuming, cancelling, and retrying failed deliveries.

---

## 🛠️ Getting Started Locally

### 1. Backend Setup

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Fill in your Firebase and Google Cloud credentials in .env

# Run FastAPI backend
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Run Tests

```bash
# Run backend test suite (34 unit & integration tests)
python -m pytest backend/tests/ -v

# Run frontend production build
cd frontend && npm run build
```

---

## 📄 Documentation

* [Architecture Overview](docs/architecture.md)
* [Render Free-Tier Batch Deployment Guide](docs/render_firestore_batch_deployment.md)
* [Gmail OAuth 2.0 Integration Guide](docs/gmail_oauth_integration.md)
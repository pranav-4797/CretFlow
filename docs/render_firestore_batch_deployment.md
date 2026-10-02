# Render Free-Tier Deployment Guide: Firestore-Backed Batch Processing

This guide provides end-to-end instructions for deploying the **FastAPI Web Service** on **Render Free Tier**, utilizing **Firebase Firestore** as the sole database and job-state store, downloading certificate PDFs from **Google Shared Drive**, and distributing emails via the official **Gmail API** with zero Redis, Celery, or Neon PostgreSQL dependencies.

---

## 1. System Architecture

```
                                  +-----------------------+
                                  |    CertFlow Frontend  |
                                  | (Firebase Hosting /   |
                                  |  certflow-ab935.web)  |
                                  +-----------------------+
                                              |
                                              | HTTPS API (Bearer Firebase Token)
                                              v
+--------------------------------------------------------------------------------------------------+
|                               RENDER WEB SERVICE (Free Tier)                                     |
|                                                                                                  |
|   FastAPI Application (Single Web Service)                                                      |
|   - Root: backend                                                                                |
|   - Command: uvicorn main:app --host 0.0.0.0 --port $PORT                                        |
|   - Features:                                                                                    |
|       * In-Process Batch Processing Engine (Bounded batches: 10–25 recipients)                   |
|       * Bounded Concurrency: 1–3 workers                                                         |
|       * Atomic Firestore Job Leases & Lease Expiry Timeout                                       |
|       * Startup Reconciler: Auto-reclaims expired leases and stuck recipients                     |
|       * Safe Handling of Ambiguous Delivery Outcomes ('unknown' state)                           |
|       * Authenticated Campaign Controls: Pause, Resume, Cancel, Retry                             |
|                                                                                                  |
|          |                                                           |                           |
|          | Download certificate PDFs (service account)               | Authoritative state &     |
|          v                                                           | token persistence         |
|   +--------------------------+                                       v                           |
|   |   Google Shared Drive    |                         +---------------------------+             |
|   |   - Certificates folder  |                         |      Cloud Firestore      |             |
|   |   - Templates folder     |                         |   - campaigns             |             |
|   +--------------------------+                         |   - campaigns/participants|             |
|          |                                             |   - email_jobs            |             |
|          | Send personalized MIME                      |   - gmail_connections     |             |
|          v                                             +---------------------------+             |
|   +--------------------------+                                                                   |
|   |        Gmail API         |                                                                   |
|   |   (users.messages.send)  |                                                                   |
|   +--------------------------+                                                                   |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Free-Tier Reliability & Render Sleep Considerations

Render free web services spin down after 15 minutes of inactivity:
1. **Sleep Behavior:** Background tasks in memory pause or terminate when the instance sleeps.
2. **Lease Expiry & Auto-Recovery:** Every batch uses a Firestore lease (`lease_expires_at`). If Render terminates an instance during a campaign, the lease expires.
3. **Automatic Resumption:**
   - On **application boot/restart**, `RestartReconciler.reconcile_all_on_startup()` automatically resets expired leases and stuck participants to `retrying` or `queued`.
   - On **dashboard activity**, accessing `/api/emails/{campaign_id}/status` triggers reconciliation to ensure the campaign can resume cleanly.
4. **Truthful Progress:** Dashboard numbers reflect persisted Firestore document counts, never transient memory states.

---

## 3. Required Environment Variables

Configure these in your Render Web Service dashboard (**Environment** tab):

| Variable | Description | Example / Default |
|---|---|---|
| `PYTHON_VERSION` | Python runtime version | `3.12.8` |
| `ENVIRONMENT` | Application mode | `production` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `FRONTEND_URL` | Production frontend domain | `https://certflow-ab935.web.app` |
| `ALLOWED_ORIGINS` | CORS origins (comma-delimited) | `https://certflow-ab935.web.app,https://certflow-ab935.firebaseapp.com` |
| `SECRET_KEY` | HMAC signing key (OAuth CSRF anti-replay) | *(Generate 32+ random characters)* |
| `FIREBASE_PROJECT_ID` | Firebase Project ID | `certflow-ab935` |
| `FIREBASE_CLIENT_EMAIL` | Firebase Admin service account email | `firebase-adminsdk-xxx@certflow-ab935.iam.gserviceaccount.com` |
| `FIREBASE_PRIVATE_KEY` | Firebase Admin private key | `"-----BEGIN RSA PRIVATE KEY-----\n..."` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-xxx` |
| `GOOGLE_REDIRECT_URI` | Google OAuth redirect callback | `https://certflow.onrender.com/api/gmail/callback` |
| `TOKEN_ENCRYPTION_KEY` | 32-byte Fernet key for token encryption | *(Generate with cryptography.fernet.Fernet.generate_key())* |
| `STORAGE_PROVIDER` | Primary storage engine | `shared_drive` |
| `GOOGLE_DRIVE_SHARED_DRIVE_NAME` | Shared Drive Name | `CertFlow` |
| `GOOGLE_DRIVE_SHARED_DRIVE_ID` | Shared Drive Root ID | `0ADWQx7sZb558Uk9PVA` |
| `GOOGLE_DRIVE_CAMPAIGNS_FOLDER_ID`| Campaigns folder ID | `1GvgzDjRxRsK92PiD7qNqCUlEttxv_TVq` |
| `GOOGLE_DRIVE_REPORTS_FOLDER_ID` | Reports folder ID | `1kBGhirabX-vZI6Wf20v3p4Hy5K7H97Tp` |
| `GOOGLE_DRIVE_TEMPLATES_FOLDER_ID`| Templates folder ID | `1fCKQJ01B2Vtu1oAfhFsTAPGgaGeOL0fY` |

*(Note: `DATABASE_URL` and `REDIS_URL` have been completely removed and are no longer required.)*

---

## 4. Deploying to Render

1. Push your updated code to your GitHub repository.
2. Render will automatically detect changes via `render.yaml` or you can manually trigger a deploy:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Verify Render deployment logs:
   - Look for `"CertFlow backend starting"`
   - Look for `"Startup reconciliation completed successfully"`

---

## 5. Campaign Control Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/emails/{campaign_id}/send` | `POST` | Enqueue batch email processing |
| `/api/emails/{campaign_id}/status` | `GET` | Retrieve progress counts & delivery status |
| `/api/emails/{campaign_id}/pause` | `POST` | Pause an ongoing campaign |
| `/api/emails/{campaign_id}/resume` | `POST` | Resume a paused campaign |
| `/api/emails/{campaign_id}/cancel` | `POST` | Cancel remaining email distributions |
| `/api/emails/{campaign_id}/retry` | `POST` | Retry eligible failed or unknown sends |
| `/api/emails/{campaign_id}/reconcile` | `POST` | Force immediate lease & counter reconciliation |

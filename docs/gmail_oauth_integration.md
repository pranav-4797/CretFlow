# Gmail OAuth 2.0 Integration Guide

## 1. Architectural Overview

CertFlow integrates with Google OAuth 2.0 and the official Gmail API (`users.messages.send`) using least-privilege permissions to send personalized certificate emails on behalf of organizers.

```
+---------------------------------------------------------------------------------------+
|                                    CERTFLOW SAAS                                      |
|                                                                                       |
|   Frontend (Vite / React)                               Backend (FastAPI)             |
|   +-----------------------+                            +--------------------------+   |
|   | Settings > Gmail Card | ---> GET /connect -------> | GmailService             |   |
|   |  - Connect button     | <--- Auth URL (state) <--- |  - Generates HMAC state  |   |
|   +-----------------------+                            +--------------------------+   |
|               |                                                     ^                 |
|               v Redirect to Google Auth                             |                 |
|       +-------------------------------+                             |                 |
|       | Google OAuth 2.0 Auth Server  |                             |                 |
|       |  - User consents              |                             |                 |
|       +-------------------------------+                             |                 |
|               |                                                     |                 |
|               v Redirect to Callback                                |                 |
|   GET /api/google/oauth/callback -----------------------------------+                 |
|     1. Validates single-use HMAC state                                                |
|     2. Exchanges authorization code for tokens                                        |
|     3. Verifies email via Google userinfo API                                         |
|     4. Encrypts refresh token using Fernet (AES-128-CBC + HMAC)                       |
|     5. Saves GmailConnection to Cloud Firestore (gmail_connections/{user_id})         |
|     6. Redirects browser to Frontend Settings                                         |
+---------------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------------+
|                                BULK DISTRIBUTION                                      |
|                                                                                       |
|   1. Organizer clicks "Send Campaign Emails" (requires explicit confirmation)         |
|   2. POST /api/emails/{campaign_id}/send initializes batch email job in Firestore     |
|   3. In-process BatchProcessingEngine processes recipients in bounded batches:         |
|      a. Verifies sender's active GmailConnection in Firestore                        |
|      b. Downloads personalized certificate PDF from Google Shared Drive               |
|      c. Dispatches MIME email via Gmail API (users.messages.send)                     |
|      d. Updates recipient state and truthful counters in Firestore                    |
|      e. Handles Pause, Resume, Cancel, and Restart Reconciliation                     |
+---------------------------------------------------------------------------------------+
```

---

## 2. Google Cloud Platform Configuration

### Step 1: Enable Gmail API
1. Navigate to **Google Cloud Console** > **APIs & Services** > **Library**.
2. Search for **Gmail API** and click **Enable**.

### Step 2: Configure OAuth Consent Screen
1. Go to **APIs & Services** > **OAuth consent screen**.
2. User Type: **External**.
3. App name: **CertFlow**.
4. Support email: select your organizer email.
5. Scopes:
   - `https://www.googleapis.com/auth/gmail.send` (Send emails on your behalf)
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
6. **Test Users**: While in *Testing* publishing status, add any Gmail or Google Workspace accounts that will connect during staging/development.
   > **Important Note:** In Google Cloud's *Testing* mode, OAuth refresh tokens expire after **7 days**. When ready for broad public availability, submitting the OAuth consent screen for Google Verification is required for permanent refresh tokens.

### Step 3: OAuth 2.0 Web Application Credentials
1. Go to **APIs & Services** > **Credentials** > **Create Credentials** > **OAuth client ID**.
2. Application type: **Web application**.
3. Name: `CertFlow Web Client`.
4. **Authorized JavaScript origins**:
   - Production: `https://certflow-ab935.web.app`
   - Local Development: `http://localhost:5173`
5. **Authorized redirect URIs**:
   - Production: `https://certflow.onrender.com/api/google/oauth/callback`
   - Local Development: `http://localhost:8000/api/google/oauth/callback`

---

## 3. Environment Variables for Render & Production

Configure the following environment variables in your Render backend service dashboard:

| Variable | Recommended Production Value | Description |
|---|---|---|
| `GOOGLE_CLIENT_ID` | `955806020643-933047nr1j3oabrgtrrk7manpd3pl6sn.apps.googleusercontent.com` | Google Cloud OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | *(From your Google Cloud Console)* | Google Cloud OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | `https://certflow.onrender.com/api/google/oauth/callback` | OAuth redirect endpoint |
| `FRONTEND_URL` | `https://certflow-ab935.web.app` | CertFlow frontend web application |
| `GMAIL_SCOPES` | `https://www.googleapis.com/auth/gmail.send` | Least-privilege email sending scope |
| `TOKEN_ENCRYPTION_KEY` | *(32-byte Fernet key)* | Secret key for encrypting refresh tokens at rest |

### Generating a Secure TOKEN_ENCRYPTION_KEY
Run this command in any terminal with Python installed to generate a cryptographic key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the printed 44-character string and set it as `TOKEN_ENCRYPTION_KEY` on Render. **Never commit this key to Git.**

---

## 4. Applying Database Migrations

Apply Alembic migrations against your Neon PostgreSQL database:

```bash
# In the backend directory:
alembic upgrade head
```

This creates:
- `gmail_connections`: Stores user ID, connected Google email, encrypted refresh token, and connection state.
- `email_logs`: Tracks individual delivery attempts, statuses (`queued`, `processing`, `sent`, `failed`, `retrying`, `cancelled`), and Gmail message IDs.

---

## 5. User Journey & Step-by-Step Testing

### 1. Connecting Gmail
1. Log in to CertFlow at `https://certflow-ab935.web.app` (or `http://localhost:5173` locally).
2. Go to **Settings**.
3. Under the **Gmail Integration** card, click **Connect with Google Gmail**.
4. Sign in to your authorized Google account and grant permission to send emails.
5. Google will redirect back to CertFlow, where you will see the **Connected** badge along with your verified Gmail address.

### 2. Sending a Controlled Test Email
1. On the **Gmail Integration** card, click **Send Test Email**.
2. Enter your email address and an optional note.
3. Click **Send Test**.
4. Check your inbox: you will receive a verified test email from your connected Gmail address with a message ID logged in CertFlow.

### 3. Campaign Distribution & Retries
1. Navigate to **Campaigns** > **Email Distribution**.
2. Customize the subject and body using template variables (`{{name}}`, `{{event_name}}`, `{{certificate_id}}`).
3. Click **Preview Email** to verify HTML rendering.
4. Check the explicit confirmation box and click **Send Campaign Emails**.
5. Monitor real-time progress. If any recipient encounters a temporary network issue, click **Retry Failed Sends**.

### 4. Disconnecting & Revoking
1. In **Settings** > **Gmail Integration**, click **Disconnect**.
2. CertFlow revokes the OAuth token with Google, updates the database, and cancels any pending queued jobs.

---

## 6. Security & Privacy Safeguards

- **Strict Identity Verification:** Protected routes verify Firebase ID tokens via `get_current_user`. The connected Google email is extracted from Google's `userinfo` API, never from client requests.
- **CSRF & Account-Linking Prevention:** OAuth state tokens are signed with HMAC-SHA256, bound to the user's Firebase UID, valid for 10 minutes, and strictly single-use.
- **Authenticated Encryption at Rest:** Refresh tokens are encrypted with Fernet (AES-128-CBC + HMAC-SHA256). Plaintext tokens are never stored or returned to the browser.
- **No Token Leaks:** Tokens, authorization codes, and client secrets are stripped from all API responses, query strings, and logs.
- **XSS & Injection Protection:** Template variables are HTML-escaped during preview and rendering.
- **Strict Role Separation:** The Google Drive service account is used exclusively for storage file operations. It is never used to send emails or impersonate user accounts.

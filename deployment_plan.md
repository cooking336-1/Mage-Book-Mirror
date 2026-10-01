# Mage Books SAAS — Production Heroku Deployment Plan

This guide provides an end-to-end blueprint for deploying the **Mage Books SAAS Django backend** to **Heroku**, configuring **Heroku Postgres**, solving **CORS/CSRF & cross-origin cookie authentication**, and replacing all **mock services** with live Ghanaian fintech and statutory integrations.

---

## 1. Architectural Topology Overview

```mermaid
graph LR
    subgraph Frontend [Next.js Client]
        FE[Vercel / Next.js PWA<br/>app.magebooks.com]
    end

    subgraph Heroku [Heroku Backend Platform]
        Router[Heroku Router<br/>SSL Termination]
        Web[Web Dyno<br/>Gunicorn WSGI / WhiteNoise]
        Release[Release Phase Dyno<br/>python manage.py migrate]
        Worker[Optional Worker Dyno<br/>Celery Payouts & Sync]
    end

    subgraph Managed Services [Cloud Infrastructure]
        PG[(Heroku Postgres<br/>Multi-Tenant Accounting)]
        Redis[(Heroku Redis / Upstash<br/>Idempotency & Celery)]
        R2[(Cloudflare R2<br/>Invoices, Receipts, PBC Files)]
    end

    subgraph External APIs [External Live Services]
        GRA[GRA E-VAT Gateway<br/>Act 1151 Fiscalization]
        Paystack[Paystack Ghana<br/>Card & MoMo Webhooks]
        Hubtel[Hubtel SMS & MoMo<br/>Disbursements]
    end

    FE -->|HTTPS + WithCredentials<br/>JWT Cookies & X-Org-ID| Router
    Router --> Web
    Web --> PG
    Web --> Redis
    Web --> R2
    Web --> GRA
    Web --> Paystack
    Web --> Hubtel
    Release --> PG
```

---

## 2. Prerequisites & Pre-Flight Checklist

Before launching, ensure you have:
1. **Heroku Account** with an active billing method (required for add-ons: Postgres & Redis).
2. **Heroku CLI** installed locally (`npm install -g heroku` or `brew install heroku/brew/heroku` or Windows installer).
3. **Target Frontend Domain(s)** ready (e.g., `http://localhost:3000` for staging, `https://magebooks.vercel.app` or `https://app.magebooks.com` for production).
4. **Third-Party Accounts & Credentials**:
   * Ghana Revenue Authority (GRA) E-VAT Developer credentials (or Sandbox key).
   * Paystack Merchant Account (Secret Key & Public Key).
   * Hubtel Developer Account (Client ID, Client Secret, Registered Sender ID).
   * Cloudflare R2 bucket credentials (Access Key ID, Secret Key, Bucket Name, Endpoint URL).

---

## 3. Necessary Backend Code Additions

Because the repository is structured as a monorepo (`backend/` + frontend in root), a few production packages and configuration tweaks are required for Heroku.

### A. Add Production Dependencies
Add `gunicorn` (WSGI server) and `whitenoise` (static file serving) to `backend/pyproject.toml` or `backend/requirements.txt`:

```toml
# Inside backend/pyproject.toml dependencies:
dependencies = [
    "django>=5.1",
    "djangorestframework>=3.15",
    "django-environ>=0.11",
    "uuid6>=2024.7",
    "psycopg[binary]>=3.2",
    "django-cors-headers>=4.4",
    "django-storages[s3]>=1.14",
    "boto3>=1.35",
    "djangorestframework-simplejwt>=5.5.1",
    "reportlab>=5.0.1",
    "redis>=8.1.0",
    "celery>=5.6.3",
    "httpx>=0.28.1",
    "cryptography>=50.0.1",
    "pyjwt>=2.15.0",
    "gunicorn>=23.0.0",
    "whitenoise[brotli]>=6.7.0",
]
```

Generate the locked `requirements.txt` for Heroku buildpack:
```bash
cd backend
uv pip compile pyproject.toml -o requirements.txt
```

### B. Create `Procfile` & `runtime.txt`
In `backend/Procfile`:
```procfile
release: python manage.py migrate --noinput
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120
worker: celery -A config worker --loglevel=INFO --concurrency=2
```

In `backend/runtime.txt`:
```text
python-3.12.8
```

### C. Updates Needed in `backend/config/settings.py`

#### 1. CORS, CSRF, & Cross-Origin Cookies
Because frontend and backend will run on different domains, cross-origin cookies require `CORS_ALLOW_CREDENTIALS`, `SameSite=None`, and `Secure=True`:

```python
# --- CORS & CSRF CONFIGURATION ---
CORS_ALLOW_CREDENTIALS = True

# Allows credentials across origins
CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "https://magebooks.vercel.app"]
)

# Required by Django 4.0+ for cross-origin POST/PUT requests
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:3000", "https://magebooks.vercel.app"]
)

# Tell Django to trust Heroku's reverse-proxy SSL termination
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cross-origin cookie transport settings for JWT & CSRF
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "None"
```

#### 2. WhiteNoise Static Files Serving
Add `whitenoise.middleware.WhiteNoiseMiddleware` directly after `SecurityMiddleware`:
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # <-- Add here
    "corsheaders.middleware.CorsMiddleware",
    # ... rest of middlewares
]

STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "static/"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

#### 3. Database SSL Configuration for Heroku Postgres
Heroku Postgres requires SSL mode:
```python
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/magebooks_db",
    )
}
if not DEBUG and not IS_TESTING:
    DATABASES["default"]["OPTIONS"] = {
        "sslmode": "require",
    }
```

---

## 4. Comprehensive Mock vs. Live API Audit

The backend currently contains **6 services** using mock implementations. Below is what needs to be configured to switch each from mock to live.

```
+---------------------------------------------------------------------------------------------------------+
|                                    BACKEND MOCK SERVICE INVENTORY                                       |
+--------------------------+-----------------------+-----------------------+------------------------------+
| Service Name             | Current Mock Class    | Live Class / Adapter  | Trigger Settings / Variables |
+--------------------------+-----------------------+-----------------------+------------------------------+
| 1. GRA E-VAT             | MockGraEvatClient     | LiveGraEvatClient     | USE_MOCK_GRA=False           |
| 2. Paystack Payments     | MockPaystackGateway   | PaystackGateway       | ACTIVE_PAYMENT_GATEWAY="paystack"|
| 3. Hubtel SMS Gateway    | MockHubtelSMSClient   | HubtelSMSClient       | USE_MOCK_SMS=False           |
| 4. MoMo Salary Transfers | MockPaystackTransfer  | PaystackTransfer*     | B2C Transfer Service         |
| 5. Redis Idempotency     | MockRedisClient       | Live redis.Redis      | USE_MOCK_REDIS=False         |
| 6. Storage (Invoices/PBC)| Local Media Storage   | Cloudflare R2 (S3)    | CLOUDFLARE_R2_* env vars     |
+--------------------------+-----------------------+-----------------------+------------------------------+
```

---

### Integration 1: Ghana Revenue Authority (GRA) E-VAT Clearance Service
* **Purpose:** Compliance with Ghana Act 1151 — Real-time invoice registration and cryptographic clearance code signing before invoices can be issued.
* **Current Mock:** `apps.tax.gateways.mock.MockGraEvatClient` (returns fake clearance codes like `GRA-ACCRA-2026-C89912` and dummy QR codes).
* **Live Implementation:** `apps.tax.gateways.live.LiveGraEvatClient` (performs live HTTPS calls to GRA Clearance API with Bearer token authentication).
* **Where to obtain credentials:**
  1. Register on the **GRA Taxpayers Portal** (`https://taxpayersportal.gra.gov.gh`).
  2. Apply for E-VAT System Integration certification as an Accounting Software Provider.
  3. Obtain your Sandbox `Client ID` / `API Key` and the production URL from GRA IT.
* **How to Wire Live:**
  Set these environment variables on Heroku:
  ```bash
  heroku config:set USE_MOCK_GRA="False"
  heroku config:set GRA_EVAT_API_URL="https://egov.gra.gov.gh/api/v1" # Provided by GRA
  heroku config:set GRA_EVAT_API_KEY="live_gra_api_key_xxxxxxxxxxxxx"
  ```

---

### Integration 2: Paystack Ghana (Mobile Money & Card Payments)
* **Purpose:** Accepting customer invoice payments via MTN MoMo, Telecel Cash, AT Money, and Cards, and verifying webhooks in constant time via HMAC-SHA512.
* **Current Mock:** `apps.payments.gateways.mock.MockPaystackGateway`.
* **Live Implementation:** `apps.payments.gateways.paystack.PaystackGateway` (already fully implemented with cryptographic signature verification).
* **Where to obtain credentials:**
  1. Create a business account at `https://dashboard.paystack.com/#/signup` (select Ghana).
  2. Navigate to **Settings > API Keys & Webhooks**.
  3. Copy your `Live Secret Key` (`sk_live_...`) and `Live Public Key` (`pk_live_...`).
  4. In the Paystack Dashboard Webhook settings, set:
     * **Webhook URL:** `https://your-api-domain.herokuapp.com/api/v1/payments/webhooks/paystack/`
* **How to Wire Live:**
  Set these environment variables on Heroku:
  ```bash
  heroku config:set ACTIVE_PAYMENT_GATEWAY="paystack"
  heroku config:set PAYSTACK_SECRET_KEY="sk_live_xxxxxxxxxxxxxxxxxxxxxxxx"
  heroku config:set PAYSTACK_PUBLIC_KEY="pk_live_xxxxxxxxxxxxxxxxxxxxxxxx"
  ```

---

### Integration 3: Hubtel Outbound SMS Gateway
* **Purpose:** Sending automated SMS invoice links, payment confirmations, and login alerts to Ghanaian phone numbers (`+233...`).
* **Current Mock:** `apps.core.services.sms.MockHubtelSMSClient` (in-memory thread-safe delivery store).
* **Live Implementation:** `apps.core.services.sms.HubtelSMSClient` (uses persistent `httpx.Client` connection pooling with basic auth to `https://smsc.hubtel.com/v1/messages/send`).
* **Where to obtain credentials:**
  1. Sign up on **Hubtel Developer Portal** (`https://developers.hubtel.com`).
  2. Create an SMS API application and note the `Client ID` and `Client Secret`.
  3. Register your alphanumeric **Sender ID** (e.g., `MageBooks`) in the Hubtel console and wait for NCA approval.
* **How to Wire Live:**
  Set these environment variables on Heroku:
  ```bash
  heroku config:set USE_MOCK_SMS="False"
  heroku config:set HUBTEL_SMS_CLIENT_ID="your_hubtel_client_id"
  heroku config:set HUBTEL_SMS_CLIENT_SECRET="your_hubtel_client_secret"
  heroku config:set HUBTEL_SMS_SENDER_ID="MageBooks"
  ```

---

### Integration 4: Payroll B2C Mobile Money Payouts (Staff Disbursements)
* **Purpose:** Disbursing staff salaries directly to MTN, Telecel, and AT Mobile Money wallets upon two-factor approval.
* **Current Mock:** `apps.payroll.services.disbursement.MockPaystackTransferGateway`.
* **Live Implementation Requirement:**
  To wire live B2C transfers, connect to the **Paystack Transfers API**:
  1. Enable "Transfers" in your Paystack Ghana dashboard.
  2. Fund your Paystack GHS balance.
  3. Implement the `BaseTransferGateway` adapter in `apps/payroll/services/disbursement.py` using Paystack's two-step transfer:
     * `POST https://api.paystack.co/transferrecipient`
     * `POST https://api.paystack.co/transfer`
  4. Set webhook for transfer status: `https://your-api-domain.herokuapp.com/api/v1/payments/webhooks/paystack/`

---

### Integration 5: Redis Distributed Idempotency & Celery Broker
* **Purpose:** Preventing duplicate payment processing on network retries and scheduling background jobs.
* **Current Mock:** `MockRedisClient` in `apps.payments.services.idempotency`.
* **Live Implementation:** `get_redis_client()` connects to live Redis via `redis.from_url()`.
* **How to Wire Live:**
  Provision the Heroku Redis add-on:
  ```bash
  heroku addons:create heroku-redis:mini -a magebooks-backend
  heroku config:set USE_MOCK_REDIS="False"
  ```
  *(Heroku automatically sets `REDIS_URL` in your application config).*

---

### Integration 6: Cloudflare R2 Object Storage (S3-Compatible)
* **Purpose:** Securely storing generated invoice PDFs, receipts, and audit PBC export ZIPs.
* **Where to obtain credentials:**
  1. Log in to **Cloudflare Dashboard > R2 > Manage R2 API Tokens**.
  2. Create an API token with read/write permissions to your bucket (e.g., `magebooks-prod`).
  3. Note: Access Key ID, Secret Access Key, and S3 Endpoint URL (`https://<account-id>.r2.cloudflarestorage.com`).
* **How to Wire Live:**
  ```bash
  heroku config:set R2_ACCESS_KEY_ID="your_cloudflare_r2_access_key_id"
  heroku config:set R2_SECRET_ACCESS_KEY="your_cloudflare_r2_secret_access_key"
  heroku config:set R2_BUCKET_NAME="magebooks-prod"
  heroku config:set R2_ENDPOINT_URL="https://<account_id>.r2.cloudflarestorage.com"
  ```

---

## 5. Step-by-Step Heroku Deployment Execution Guide

Follow these exact steps from your terminal:

### Step 1: Login & Create Heroku App
```bash
# Login to Heroku
heroku login

# Create a new Heroku app (choose a unique name)
heroku create magebooks-backend --region eu # 'eu' or 'us'
```

### Step 2: Attach Heroku Postgres & Redis Add-ons
```bash
# Attach Managed PostgreSQL (Heroku automatically sets DATABASE_URL)
heroku addons:create heroku-postgresql:essential-0 -a magebooks-backend

# Attach Managed Redis (Heroku automatically sets REDIS_URL)
heroku addons:create heroku-redis:mini -a magebooks-backend
```

### Step 3: Configure Core Environment Variables
Set the mandatory Django production variables:

```bash
# 1. Django core secrets
heroku config:set DJANGO_DEBUG="False" -a magebooks-backend
heroku config:set DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" -a magebooks-backend

# 2. Hosts and domains (add your Heroku app name and frontend domain)
heroku config:set DJANGO_ALLOWED_HOSTS="magebooks-backend.herokuapp.com,api.magebooks.com,localhost" -a magebooks-backend

# 3. CORS and CSRF origins (your Next.js frontend URL)
heroku config:set DJANGO_CORS_ALLOWED_ORIGINS="https://magebooks.vercel.app,https://app.magebooks.com,http://localhost:3000" -a magebooks-backend
heroku config:set DJANGO_CSRF_TRUSTED_ORIGINS="https://magebooks.vercel.app,https://app.magebooks.com" -a magebooks-backend

# 4. Cookie Transport
heroku config:set JWT_COOKIE_SECURE="True" -a magebooks-backend
heroku config:set JWT_COOKIE_SAMESITE="None" -a magebooks-backend

# 5. Column-Level Field Encryption Key (32-byte url-safe base64)
heroku config:set FIELD_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" -a magebooks-backend

# 6. Live vs Mock flags (start in mock or set live keys)
heroku config:set USE_MOCK_REDIS="False" -a magebooks-backend
heroku config:set USE_MOCK_GRA="True" -a magebooks-backend   # Switch to False when GRA key is active
heroku config:set USE_MOCK_SMS="True" -a magebooks-backend   # Switch to False when Hubtel key is active
heroku config:set ACTIVE_PAYMENT_GATEWAY="mock" -a magebooks-backend # Switch to "paystack" when keys are active
```

### Step 4: Configure Monorepo Subtree Deployment
Because the Git repository contains both `src/` (Next.js) and `backend/` (Django), you deploy only the `backend/` directory to Heroku using `git subtree`:

```bash
# Add the Heroku remote (if not already added)
heroku git:remote -a magebooks-backend

# Deploy the backend directory to Heroku main branch
git subtree push --prefix backend heroku main
```

*(Alternative: You can use the `heroku-buildpack-python-subdir` buildpack to automatically deploy the `backend` folder on regular `git push heroku develop:main`).*

### Step 5: Verify Automated Database Migrations
Thanks to the `release: python manage.py migrate --noinput` line in the `Procfile`, Heroku automatically executes all forward database migrations against Heroku Postgres before the new dynos start serving traffic.

To verify migration status:
```bash
heroku run python manage.py showmigrations -a magebooks-backend
```

### Step 6: Create Superuser (Admin Access)
```bash
heroku run python manage.py createsuperuser -a magebooks-backend
```

---

## 6. Post-Deployment Verification & Smoke Tests

Verify that your backend is completely live and communicating properly:

### 1. Check Application Logs
```bash
heroku logs --tail -a magebooks-backend
```
Ensure you see Gunicorn workers booted:
`[INFO] Listening at: http://0.0.0.0:<PORT>`
`[INFO] Booting worker with pid: ...`

### 2. Smoke Test CSRF & Health Check
Run a curl command from your terminal:
```bash
curl -i -X GET https://magebooks-backend.herokuapp.com/api/v1/auth/csrf/
```
**Expected Response:**
* HTTP `200 OK`
* Response header: `Set-Cookie: csrftoken=...; SameSite=None; Secure; Path=/`
* Response body: `{"csrfToken": "..."}`

### 3. Smoke Test Authentication with Frontend
1. Update your frontend environment variable in `.env.local` or Vercel:
   ```env
   NEXT_PUBLIC_API_URL=https://magebooks-backend.herokuapp.com
   ```
2. Navigate to your frontend `/login` or `/signup` screen.
3. Register a new user.
4. Verify in browser DevTools:
   * Request header includes `X-CSRFToken` and `withCredentials: true`.
   * Response sets `access_token` and `refresh_token` cookies with `SameSite=None` and `Secure`.
   * User is successfully routed to `/dashboard`.

---

## 7. Operational Troubleshooting & Gotchas

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`403 Forbidden: CSRF verification failed`** | Frontend domain missing in `CSRF_TRUSTED_ORIGINS` | Run `heroku config:set DJANGO_CSRF_TRUSTED_ORIGINS="https://frontend-domain.com"` |
| **Cookies not saved in browser** | `SameSite` set to `Strict` or `Lax` across different domains, or `Secure=False` | Ensure `JWT_COOKIE_SAMESITE="None"` and `JWT_COOKIE_SECURE="True"` |
| **`psycopg.OperationalError: SSL connection error`** | Heroku Postgres requires SSL | Ensure `DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}` |
| **`DisallowedHost at /`** | Request Host header not in `ALLOWED_HOSTS` | Add the Heroku domain to `DJANGO_ALLOWED_HOSTS` |
| **Static files 404 in Django Admin** | WhiteNoise missing or `collectstatic` failed | Ensure `whitenoise.middleware.WhiteNoiseMiddleware` is in `MIDDLEWARE` and `STATIC_ROOT` is set |
| **Dyno crash on boot: `ModuleNotFoundError`** | Dependency missing from `requirements.txt` | Run `uv pip compile pyproject.toml -o requirements.txt` and redeploy |

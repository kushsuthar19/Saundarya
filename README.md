# Saundarya Beauty Care & Academy — Management System

Full-stack salon management system with FastAPI backend, Oracle DB, and a production-ready frontend.

---

## Project Structure

```
saundarya/
├── backend/
│   ├── core/
│   │   ├── config.py          # Settings from .env
│   │   ├── database.py        # Oracle connection pool
│   │   └── security.py        # JWT, bcrypt, RBAC
│   ├── middleware/
│   │   └── security.py        # Rate limiting, security headers
│   ├── routers/
│   │   ├── auth.py            # Login / logout / refresh
│   │   ├── clients.py         # Client CRUD
│   │   ├── entries.py         # Daily bills + PDF + WhatsApp
│   │   └── main_routers.py    # Appointments, Staff, Attendance,
│   │                          #   Bridal, Dashboard, Revenue, Reports
│   ├── schemas/
│   │   └── schemas.py         # Pydantic request/response models
│   ├── services/
│   │   ├── pdf_service.py     # PDF invoice generation (reportlab)
│   │   └── whatsapp_service.py # WhatsApp API (UltraMsg/CallMeBot/Meta)
│   └── main.py                # FastAPI app entry point
├── frontend/
│   └── index.html             # Complete salon management UI
├── database/
│   ├── schema.sql             # Oracle table definitions
│   └── seed.sql               # Default data (services, admin user)
├── scripts/
│   ├── setup.sh               # First-time setup
│   └── init_db.py             # Initialize Oracle DB
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Oracle Database (XE, Standard, or ATP)
  - Oracle XE (free): https://www.oracle.com/database/technologies/xe-downloads.html
  - Docker: `docker run -d -p 1521:1521 -e ORACLE_PASSWORD=pass gvenzl/oracle-free`

### 2. Clone & Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values:
nano .env
```

**Required .env values:**
```env
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ORACLE_USER=saundarya
ORACLE_PASSWORD=your_password
ORACLE_DSN=localhost:1521/XEPDB1
```

### 4. Create Oracle User & Initialize DB

```sql
-- Run as SYSDBA in SQL*Plus or SQLcl:
CREATE USER saundarya IDENTIFIED BY your_password;
GRANT CONNECT, RESOURCE, CREATE SESSION TO saundarya;
GRANT UNLIMITED TABLESPACE TO saundarya;
```

```bash
# Initialize tables and seed data
python3 scripts/init_db.py
```

### 5. Run

```bash
# Development
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Production
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Open http://localhost:8000 in your browser.

**Default login:**
- Username: `admin`
- Password: `Admin@Saundarya2024`
- ⚠️ **Change immediately after first login!**

---

## API Endpoints

All endpoints are prefixed with `/api/v1/`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | - | Login, returns JWT |
| POST | `/auth/refresh` | cookie | Refresh access token |
| POST | `/auth/logout` | ✅ | Logout |
| POST | `/auth/change-password` | ✅ | Change password |
| GET | `/dashboard` | ✅ | Dashboard stats |
| GET/POST | `/clients` | ✅ | Client CRUD |
| GET/POST | `/appointments` | ✅ | Appointment management |
| GET/POST | `/entries` | ✅ | Daily bill entries |
| GET | `/entries/{id}/pdf` | ✅ | Download invoice PDF |
| GET | `/entries/batch/pdf?entry_date=` | ✅ | All invoices for a date |
| POST | `/entries/{id}/whatsapp` | ✅ | Send invoice on WhatsApp |
| GET/POST | `/staff` | admin | Staff management |
| POST | `/attendance/upsert` | ✅ | Mark attendance with in/out time |
| GET/POST | `/bridal` | ✅ | Bridal bookings |
| GET | `/bridal/{id}/pdf` | ✅ | Bridal invoice PDF |
| POST | `/bridal/{id}/whatsapp` | ✅ | Send bridal invoice on WhatsApp |
| GET | `/revenue/stats` | admin | Revenue KPIs |
| GET | `/revenue/daily` | admin | Daily revenue table |
| GET | `/revenue/monthly` | admin | Monthly revenue chart data |
| GET | `/revenue/pending-dues` | admin | Bridal pending dues |
| GET | `/reports/summary` | admin | Reports overview |
| GET | `/reports/service-revenue` | admin | Revenue by service |
| GET | `/reports/staff-performance` | admin | Staff performance |
| GET | `/services` | ✅ | Service catalog |

Swagger UI: http://localhost:8000/api/docs (development mode only)

---

## WhatsApp Setup

### Option 1: UltraMsg (Recommended — ₹800/month)
1. Go to https://ultramsg.com → Create account
2. Create instance → Scan QR with WhatsApp
3. Get Instance ID and Token
4. Set in `.env`:
   ```
   WA_PROVIDER=ultramsg
   WA_API_URL=https://api.ultramsg.com
   WA_INSTANCE_ID=instance12345
   WA_TOKEN=your_token_here
   ```

### Option 2: CallMeBot (Free, limited)
1. Add `+34 644 97 44 69` on WhatsApp
2. Send: `I allow callmebot to send me messages`
3. You'll receive an API key
4. Set in `.env`:
   ```
   WA_PROVIDER=callmebot
   WA_TOKEN=your_api_key
   ```
   **Note:** CallMeBot only works for one phone number (the one you registered)

### Option 3: Meta Cloud API (Official)
1. https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
2. Requires business verification (1-2 weeks)
3. Set in `.env`:
   ```
   WA_PROVIDER=meta
   WA_INSTANCE_ID=your_phone_number_id
   WA_TOKEN=your_meta_bearer_token
   ```

---

## User Roles

| Feature | Admin | Staff |
|---------|-------|-------|
| Dashboard | ✅ | ✅ |
| Appointments | ✅ | ✅ |
| Bridal | ✅ | ✅ |
| Daily Entry | ✅ | ✅ |
| Clients | ✅ | ✅ |
| Staff Management | ✅ | ❌ |
| Revenue (with dues) | ✅ | ❌ |
| Reports & Analytics | ✅ | ❌ |

---

## Security Features

- **JWT access tokens** (30 min expiry) + **HttpOnly cookie refresh tokens** (7 days)
- **Token rotation** — each refresh generates a new token, old one revoked
- **bcrypt** password hashing (rounds=12)
- **Account lockout** after 5 failed logins (30 min lockout)
- **Rate limiting** — 60 req/min global, 10 login attempts/min per IP
- **Security headers** — CSP, HSTS, X-Frame-Options, X-XSS-Protection
- **Input validation** — Pydantic v2 with strict validators on all endpoints
- **SQL injection prevention** — parameterized queries only, no string interpolation
- **Role-based access control** — admin-only endpoints enforced server-side

---

## Production Deployment

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd Service

```ini
# /etc/systemd/system/saundarya.service
[Unit]
Description=Saundarya Beauty Care Backend
After=network.target

[Service]
Type=exec
User=saundarya
WorkingDirectory=/opt/saundarya
ExecStart=/opt/saundarya/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
EnvironmentFile=/opt/saundarya/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable saundarya
sudo systemctl start saundarya
```

### .env for Production

```env
ENV=production
DEBUG=false
SECRET_KEY=<strong_random_64_char_key>
ORACLE_DSN=your_prod_oracle_dsn
ALLOWED_ORIGINS=https://yourdomain.com
```

---

## Frontend API Integration

The frontend currently uses in-memory JS storage. To integrate with the backend API, add this JS block before `</script>` in `frontend/index.html`:

```javascript
const API = 'http://localhost:8000/api/v1';
let accessToken = localStorage.getItem('saundarya_token') || '';

async function apiCall(method, path, body=null) {
  const headers = {'Content-Type': 'application/json'};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  const opts = { method, headers, credentials: 'include' };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(API + path, opts);
  if (resp.status === 401) { accessToken = ''; window.location.reload(); return null; }
  return resp.ok ? resp.json() : null;
}
```

Then replace save functions (e.g. `saveDe()`, `saveAppt()`, etc.) to call `apiCall()`.

---

## Support

- Oracle APEX / SQL*Plus: https://www.oracle.com/database/technologies/appdev/sqldeveloper-landing.html
- FastAPI docs: https://fastapi.tiangolo.com
- UltraMsg WhatsApp API: https://ultramsg.com/resources/api

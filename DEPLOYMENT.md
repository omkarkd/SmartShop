# SmartShop — Deployment Strategy Document

## 1. Architecture Overview

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser    │────▶│  FastAPI Server   │────▶│   MongoDB     │
│  (Static FE) │     │  (uvicorn)        │     │  (Atlas/Local)│
└─────────────┘     │  Port 8000        │     └──────────────┘
                    │                   │
                    │  ┌─────────────┐  │
                    │  │ Static Files │  │
                    │  │  (frontend/) │  │
                    │  └─────────────┘  │
                    └──────────────────┘

┌──────────────────┐
│  Scraper (CLI)   │  ← separate, runs on cron/trigger
│  undetected-     │
│  chromedriver    │
│  + Selenium      │
└──────────────────┘
```

**Components:**
- **FastAPI server** — single Python process serving both API + static frontend
- **MongoDB** — all persistent state (products, users, carts)
- **Scraper** — headless Chrome browser, runs independently, writes to MongoDB
- **Frontend** — plain HTML/CSS/JS served by FastAPI (no build step)

---

## 2. Resource Requirements

### Application Server (FastAPI)
| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 512 MB | 1-2 GB |
| Storage | 200 MB (code) | 1 GB (logs) |
| Python | 3.11+ | 3.11+ |

### Database (MongoDB)
| Resource | Minimum | Recommended |
|---|---|---|
| Storage | 500 MB (current data ~9K products) | 5 GB (growth headroom) |
| RAM | 256 MB (cache) | 1 GB |
| Connections | 10 | 50 |

### Scraper (separate, burst usage)
| Resource | Requirement |
|---|---|
| CPU | 1-2 vCPU (Chrome is heavy) |
| RAM | 2-4 GB (Chrome + Selenium overhead) |
| Storage | Minimal |
| Chrome | Must match chromedriver version (currently v148 compat target) |
| **Max runtime** | ~30-60 min per full scrape |

---

## 3. Deployment Options Comparison

### Option A: Single VPS (simplest, cheapest)

**Stack:** One Linux VM + Docker Compose

```
┌──────────────┐
│   VPS Host   │
│  (2 vCPU,    │
│   2 GB RAM)  │
│              │
│  ┌────────┐  │
│  │ Nginx   │──▶ Internet (port 80/443)
│  │ (proxy) │  │
│  └────┬───┘  │
│       ▼      │
│  ┌────────┐  │
│  │FastAPI │  │
│  │ :8000  │  │
│  └────┬───┘  │
│       ▼      │
│  ┌────────┐  │
│  │MongoDB │  │
│  │ :27017 │  │
│  └────────┘  │
└──────────────┘
```

**Pros:** Single machine, lowest cost (~$10-20/mo), full control  
**Cons:** No HA, manual backup, MongoDB runs on same box (contention)

**Cost:** ~$12-25/mo (VPS)  

### Option B: Managed MongoDB + VPS (balanced)

**Stack:** VPS for FastAPI + MongoDB Atlas (free tier)

```
┌──────────────┐      ┌──────────────┐
│   VPS Host   │      │ MongoDB Atlas │
│  (1-2 vCPU,  │──────▶ (M0 free or  │
│   1 GB RAM)  │      │  M2 paid)     │
│              │      └──────────────┘
│  ┌────────┐  │
│  │ Nginx   │──▶ Internet
│  │ (proxy) │
│  └────┬───┘
│       ▼
│  ┌────────┐
│  │FastAPI │
│  │ :8000  │
│  └────────┘
└──────────────┘
```

**Pros:** Managed DB (backups, HA), lower VPS requirements, free tier possible  
**Cons:** Network latency to Atlas, free tier limited to 512 MB

**Cost:** ~$6-15/mo (VPS) + $0-57/mo (Atlas)

### Option C: Fully Managed (PaaS — Railway / Render / Fly.io)

**Stack:** PaaS for FastAPI + MongoDB Atlas

```
┌──────────────────┐     ┌──────────────┐
│  Railway / Render │────▶│ MongoDB Atlas │
│  (FastAPI)        │     └──────────────┘
│  Auto-deploy from │
│  GitHub           │
└──────────────────┘
```

**Pros:** Zero server management, auto-deploy from git, built-in SSL, logging  
**Cons:** Cold starts (free tier), more expensive at scale, vendor lock-in

**Cost:** ~$5-20/mo (Railway starter) + $0-57/mo (Atlas)

### Option D: Serverless (AWS Lambda + API Gateway)

**Stack:** Lambda + API Gateway + MongoDB Atlas (or DocumentDB)

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ API GW    │────▶│  Lambda       │────▶│ MongoDB Atlas │
│ (HTTPS)   │     │  (FastAPI via │     └──────────────┘
└──────────┘     │  Mangum)      │
                  └──────────────┘
```

**Pros:** Auto-scales to zero, no servers, pay per request  
**Cons:** Cold starts (3-5s), MongoDB connection pool management is complex, frontend needs S3/CloudFront, stateful cart logic is awkward in Lambda

**Cost:** ~$0-5/mo (low traffic)  

---

## 4. Recommended: Option B (VPS + Atlas)

### Rationale

| Concern | Why Option B wins |
|---|---|
| **Cost** | $6-15/mo VPS + free Atlas M0 = minimal |
| **Data safety** | Atlas provides automated backups, point-in-time restore |
| **Scraper** | Needs a full Chrome browser — impossible on PaaS/Lambda |
| **Complexity** | Single VPS = simple, but DB is separated for safety |
| **Scalability** | VPS can be vertically scaled; Atlas can be upgraded to M10+ |

---

## 5. Infrastructure Setup (Option B)

### 5.1 VPS Provisioning

**Recommended specs:**
- Provider: Hetzner CX22 / Linode 2 GB / DigitalOcean Basic 2 GB
- OS: Ubuntu 24.04 LTS
- Plan: 2 vCPU, 2 GB RAM, 40 GB SSD (~$12-15/mo)

**Initial setup:**
```bash
apt update && apt upgrade -y
apt install -y nginx certbot python3.11 python3.11-venv git
```

### 5.2 Application Deployment

**Systemd service** (`/etc/systemd/system/smartshop.service`):
```ini
[Unit]
Description=SmartShop FastAPI
After=network.target

[Service]
User=smartshop
WorkingDirectory=/opt/smartshop
Environment=MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net
Environment=SECRET_KEY=<random-256-bit-key>
Environment=DB_NAME=smartshop
ExecStart=/opt/smartshop/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Nginx reverse proxy** (`/etc/nginx/sites-enabled/smartshop`):
```nginx
server {
    listen 80;
    server_name smartshop.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Increase body size for potential batch brand extraction
    client_max_body_size 10M;
}
```

**SSL** (via certbot):
```bash
certbot --nginx -d smartshop.example.com
```

### 5.3 MongoDB Atlas Setup

1. Create a free M0 cluster (shared RAM, 512 MB storage)
2. Enable IP whitelist (VPS public IP + your dev IP)
3. Create a DB user with readWrite on `smartshop` database
4. Connection string format:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/smartshop?retryWrites=true&w=majority
   ```

**Data migration:**
```bash
# From dev machine (dump)
mongodump --db smartshop --out ./smartshop_backup

# To Atlas (restore)
mongorestore --uri "mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net" --db smartshop ./smartshop_backup/smartshop
```

---

## 6. Scraper Deployment

The scraper is a **separate concern** — it needs Chrome and does not need to be always-on.

### Options for running the scraper:

| Option | Setup | Cost | Notes |
|---|---|---|---|
| **Same VPS** | Run as cron job weekly | Included in VPS cost | Chrome needs 2-4 GB RAM; may contend with app server |
| **GitHub Actions** | Scheduled workflow | Free (2000 min/mo) | Needs self-hosted runner or use playwright instead of Chrome |
| **Separate micro VM** | Hetzner CX11 ($4/mo) | $4/mo | Dedicated, no contention |
| **Local machine** | Manual trigger | $0 | Developer's machine |

**Recommended:** Run on the same VPS with a `systemd timer` that runs during low-traffic hours (e.g., 3 AM Sunday). Ensure sufficient RAM or add swap.

```bash
# /etc/systemd/system/smartshop-scrape.service
[Unit]
Description=SmartShop Sainsbury's Scraper

[Service]
Type=oneshot
User=smartshop
WorkingDirectory=/opt/smartshop/scrapper/sainsburys
ExecStart=/opt/smartshop/.venv/bin/python scrape_sainsburys.py
Environment=MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net

# /etc/systemd/system/smartshop-scrape.timer
[Timer]
OnCalendar=Sun 03:00
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 7. Environment Variables

| Variable | Dev Value | Prod Value | Secret? |
|---|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | `mongodb+srv://...` | Yes |
| `DB_NAME` | `smartshop` | `smartshop` | No |
| `SECRET_KEY` | `smartshop-secret-key-change-in-production` | `<random-256-bit-key>` | Yes |

Generate production secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 8. CI/CD Pipeline

### GitHub Actions (`.github/workflows/deploy.yml`):

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Sync to VPS
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          source: "."
          target: "/opt/smartshop"
          strip_components: 0
          exclude: ".venv,.git,__pycache__,scrapper/sainsburys/data"
      - name: Restart app
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/smartshop
            .venv/bin/pip install -e .
            sudo systemctl restart smartshop
```

---

## 9. Security Checklist

- [ ] `SECRET_KEY` changed from default to random 256-bit value
- [ ] CORS `allow_origins` narrowed from `["*"]` to your domain
- [ ] MongoDB Atlas IP whitelist locked to VPS IP only (not `0.0.0.0/0`)
- [ ] MongoDB Atlas user has minimal privileges (`readWrite` on single DB)
- [ ] Nginx configured with TLS (certbot)
- [ ] `MONGO_URI` includes password (never hardcoded)
- [ ] VPS firewall: only ports 22, 80, 443 open
- [ ] Password hashed with bcrypt (already implemented)
- [ ] Rate limiting on login endpoint (optional: add `slowapi`)

---

## 10. Monitoring & Backup

### Monitoring (free):
- **Uptime:** Hetzner/Linode built-in monitoring (ping check)
- **Application:** FastAPI health endpoint (add `GET /health`)
- **Logs:** `journalctl -u smartshop -f` (systemd)
- **Metrics:** `psutil` + simple `/metrics` endpoint for Prometheus (optional)

### Backup strategy:
- **MongoDB Atlas:** Enable auto-backups ($) or use `mongodump` in a cron
- **Application:** Stateless (just git + env vars)
- **Frequency:** Daily DB backup, weekly full backup

```bash
# Daily DB backup cron (VPS → S3-compatible storage)
0 4 * * * mongodump --uri "$MONGO_URI" --out /tmp/mongo_backup && \
  tar czf /backups/smartshop-$(date +\%Y\%m\%d).tgz -C /tmp/mongo_backup && \
  aws s3 cp /backups/smartshop-*.tgz s3://my-backup-bucket/mongo/
```

---

## 11. Cost Breakdown

| Item | Option A (VPS only) | Option B (VPS + Atlas) | Option C (Railway + Atlas) |
|---|---|---|---|
| Compute | $12-15/mo | $6-12/mo | $5-20/mo |
| Database | — (on VPS) | $0-57/mo | $0-57/mo |
| Domain (optional) | $10/yr | $10/yr | $10/yr |
| SSL | Free (certbot) | Free (certbot) | Free (built-in) |
| **Total (monthly)** | **$12-15** | **$6-69** | **$5-77** |

---

## 12. Recommendation

**Adopt Option B (VPS + MongoDB Atlas).**

| Factor | Verdict |
|---|---|
| **Cheapest viable** | Yes — $6-15/mo with Atlas free tier |
| **Data safety** | Atlas provides automated backups — critical for scraped product data |
| **Scraper-friendly** | VPS can run Chrome; PaaS/serverless cannot |
| **Minimal migration** | No framework changes needed, just env vars |
| **Future growth** | Vertical scaling on VPS, Atlas upgrades to M10+ without downtime |

**If budget is extremely tight** ($0): Use Option A on a single $6/mo VPS with MongoDB installed directly, add swap for the scraper, and set up `mongodump` cron for backups.

**If you want zero ops** and don't mind scraper running locally: Option C (Railway + Atlas), but the scraper must run on your machine or a separate runner.

---

## 13. Migration Steps (dev → Option B)

```bash
# 1. Provision VPS + install dependencies
ssh root@your-vps
apt install -y python3.11 python3.11-venv nginx certbot git

# 2. Create deployment user
useradd -m -s /bin/bash smartshop
mkdir -p /opt/smartshop && chown smartshop:smartshop /opt/smartshop

# 3. Deploy code (from your machine)
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  --exclude 'scrapper/sainsburys/data' \
  ./ smartshop@your-vps:/opt/smartshop/

# 4. Set up Python environment on VPS
ssh smartshop@your-vps
cd /opt/smartshop
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 5. Create requirements.txt for reproducible builds
pip freeze > requirements.txt

# 6. Configure env + secrets
cat > /opt/smartshop/.env << EOF
MONGO_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net
DB_NAME=smartshop
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF

# 7. Set up systemd service + nginx + certbot
# (see sections 5.1-5.2 above)

# 8. Migrate MongoDB data
mongodump --db smartshop --out /tmp/smartshop_dump
mongosh "$MONGO_URI" --eval 'db.dropDatabase()'
mongorestore --uri "$MONGO_URI" --nsInclude 'smartshop.*' /tmp/smartshop_dump/smartshop

# 9. Enable + start
sudo systemctl enable smartshop
sudo systemctl start smartshop
sudo systemctl enable smartshop-scrape.timer
sudo systemctl start smartshop-scrape.timer
```

---

## 14. Quick-Start Config Files

### requirements.txt (create from current environment)
```txt
fastapi==0.137.1
uvicorn[standard]==0.49.0
pymongo==4.16.0
pydantic==2.12.5
python-multipart==0.0.32
passlib[bcrypt]==1.7.4
bcrypt==5.0.0
selenium==4.43.0
undetected-chromedriver==3.5.5
```

### Health endpoint (add to `main.py`)
```python
@app.get("/health")
def health():
    from backend.database import db
    try:
        db.command("ping")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
```

### Production CORS (update `main.py`)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://smartshop.example.com"],  # was ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

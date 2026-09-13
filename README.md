# Old & Rare Book Marketplace Backend

A multi-vendor used and vintage book commerce platform built with **Django 5.1**, **PostgreSQL**, **Redis**, and **Celery**.

---

##  Milestone Progress

- [x] **Phase 1 (~30%): Foundation & Core Architecture**
  - Project configuration & settings split (`base`, `local`, `production`)
  - User & Seller identity (`apps/accounts`)
  - Master canonical book catalog & taxonomy (`apps/books`)
  - REST API setup with OpenAPI 3.0 / Swagger documentation
  - Docker Compose setup (PostgreSQL 16 + Redis 7)

- [ ] **Phase 2 (~70%): Used Book Listings & Orders**
  - Physical wear condition grading & inspection photos (`apps/listings`)
  - Multi-vendor cart & shipment splitting (`apps/orders`)
  - Concurrency safety with 15-minute Redis TTL reservation

- [ ] **Phase 3 (~100%): Financials & Logistics**
  - Payment gateways & Escrow hold (`apps/payments`)
  - Courier dispatch & tracking webhooks (`apps/shipping`)
  - Buyer-seller condition messaging threads (`apps/messaging`)
  - Celery background tasks (WebP compression & expired lock sweeper)

---

## 🛠️ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/rafiq9090/bookmangement.git
cd bookmangement

# 2. Setup Virtual Environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # On Windows

# 3. Install Dependencies
pip install -r requirements/base.txt

# 4. Migrate and Run
python manage.py migrate
python manage.py runserver
```

Explore interactive Swagger docs at: `http://127.0.0.1:8000/api/docs/`

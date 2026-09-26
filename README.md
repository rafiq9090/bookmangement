#  Old & Rare Book Marketplace Backend & Platform

A comprehensive multi-vendor used, vintage, and rare book commerce platform engineered with **Django 5.1**, **PostgreSQL 16**, **Redis 7**, and **Celery**. Designed specifically to solve the unique challenges of second-hand and collectible book trading—including one-of-a-kind inventory preservation, condition verification, multi-vendor shipment splitting, buyer-seller pre-purchase negotiation, escrow security, and double-entry financial accounting.

---

##  Key Features Overview

### 1.  Master Canonical Catalog & Taxonomy Engine (`apps/books`)
* **Single Source of Truth Catalog:** Multiple sellers can attach their physical used copies to a single canonical `Book` entry, eliminating duplicate catalog noise and enabling price/condition comparisons.
* **Deep ISBN Normalization:** Indexed ISBN-10 and unique ISBN-13 lookup with automated slug generation.
* **Hierarchical Taxonomy:** Multi-author relationships and multi-tier category/subcategory structures (`Category.parent`).
* **Live Search & Autocomplete API:** Instant ISBN lookup and dynamic author search endpoints (`/seller/lookup-isbn/`, `/seller/authors/suggest/`).
* **Community Ratings & Verified Reviews:** 5-star rating system with verified purchase tags, headline reviews, and qualitative feedback.

---

### 2.  Condition Grading & Physical Wear Inspection (`apps/listings`)
* **Standardized 5-Tier Condition Grading:**
  * `LIKE_NEW`: Minimal signs of wear, pristine pages.
  * `VERY_GOOD`: Clean pages, light shelf wear or minor spine creasing.
  * `GOOD`: Typical used wear, intact binding, possible minor highlighting or marginalia.
  * `ACCEPTABLE`: Fully readable copy with significant wear, scuffs, or aging.
  * `COLLECTIBLE`: Rare first editions, vintage printings, antiquarian copies.
* **Physical Defect Documentation:** Detailed condition notes covering foxing, yellowed pages, binding soundness, and marginalia.
* **Rare Edition Attributes:** Dedicated toggles for **Hardcover**, **Original Dust Jacket**, and **Author-Signed** copies, plus original printing year tracking.
* **Multi-Photo Inspection:** High-resolution photo upload with primary thumbnail assignment for full buyer transparency.
* **Inventory Lifecycle & Soft Delete:** State management (`DRAFT`, `ACTIVE`, `RESERVED`, `SOLD`, `ARCHIVED`) with non-destructive soft deletion.

---

### 3.  Community Book Reviews & Rating System (`apps/books`)
* **1-to-5 Star Qualitative Feedback:** Readers can evaluate books on a 1–5 star rating scale, providing a headline summary and in-depth commentary.
* **Anti-Fraud & Marketplace Integrity Rules:**
  * **Seller Self-Review Prohibition:** Sellers are strictly prevented from reviewing or inflating ratings on books listed in their own store (`is_seller_of_book` guardrail).
  * **Duplicate Review Prevention:** Authenticated users are limited to one review per book (`user_has_reviewed` validation) to prevent vote-stacking.
* **Dynamic Rating Aggregations & Percentage Breakdown:** Live mathematical calculation of average rating (`Avg("rating")`) accompanied by an interactive 5-star distribution bar graph (showing percentage share and counts for 5★, 4★, 3★, 2★, and 1★ ratings).
* **Asynchronous AJAX Submission:** Seamless in-place review posting via AJAX with immediate DOM updates, real-time reviews count badge increments, and graceful traditional form fallback.
* **Marketplace-Wide Review Showcases:**
  * **Homepage Customer Testimonials:** Dedicated "Customer Reviews & Testimonials" showcase featuring recent reader feedback, star ratings, reviewer initials, and direct catalog links.
  * **Storefront Spotlight:** Featured community reviews spotlighted in the store sidebar alongside category filters.
  * **Direct Deep-Linking:** Interactive star ratings on catalog cards and collection carousels link directly to the `#reviews` anchor with automatic tab switching on the book detail page.

---

### 4.  Multi-Vendor Cart & Automated Shipment Splitting (`apps/orders`)
* **Universal Multi-Vendor Cart:** Seamlessly combine single-copy used books from multiple distinct sellers into one checkout transaction.
* **Automated Order Shipment Bifurcation (`OrderShipment`):** Automatically splits checkout orders into independent seller packages, each with its own shipping fee, dispatch status, and courier tracking.
* **Immutable Shipping Snapshot:** Serializes customer delivery address at the exact moment of order placement to guarantee auditability and dispute protection.
* **Full Order Lifecycle Management:** Complete state tracking (`PENDING`, `PAID`, `PROCESSING`, `COMPLETED`, `CANCELLED`).

---

### 5.  Concurrency Safety & Anti-Double-Selling Engine
* **15-Minute Reservation Lock:** Because used books are usually single, unique copies, initiating checkout places listings in a `RESERVED` status to prevent race conditions and double-purchasing.
* **Automated Celery Beat Sweeper (`sweep_expired_reservations`):** Periodic worker runs every 60 seconds to detect abandoned checkout locks (>15 minutes) and instantly restore books back to `ACTIVE` available inventory.

---

### 6.  Escrow Protection, Double-Entry Ledger & Payouts (`apps/payments`)
* **Milestone-Based Escrow Custody (`EscrowHold`):** Buyer funds are held securely in platform escrow and are only released to the seller after verified delivery or resolution of return windows.
* **Transparent Double-Entry Bookkeeping (`SellerLedger`):** Every transaction is recorded with audit-grade ledger entries:
  * `SALE_CREDIT`: Gross sale revenue allocated to the seller.
  * `PLATFORM_FEE`: Automated 15% platform commission deduction.
  * `PAYOUT_DEBIT`: Successful seller balance withdrawals.
  * `REFUND_DEBIT`: Order cancellations and disputes.
* **Seller Wallet & Balance Calculation:** Live tracking of **Available Balance** vs. **Held in Escrow**.
* **Multi-Channel Payout Batches:** Payout request and processing pipeline supporting **bKash**, **Nagad**, and direct **Bank Transfer**.
* **Payment Gateway Ready:** Architecture prepared for **SSLCommerz**, **Stripe**, and **bKash Direct** with full payload audit logging.

---

### 7.  Logistics Integration & Real-Time Tracking (`apps/shipping`)
* **Courier Framework:** Built to integrate with nationwide courier providers (**Steadfast**, **Pathao**, **Paperfly**, **RedX**).
* **Public Parcel Tracking Portal (`/tracking/` & `/tracking/<tracking_number>/`):** Real-time tracking page providing buyers with a chronological milestone timeline and event audit history (`TrackingEvent`).
* **Shipment Status Flow:** `WAITING_SELLER` ➔ `PICKED_UP` ➔ `IN_TRANSIT` ➔ `DELIVERED` ➔ `RETURNED`.

---

### 8.  Pre-Purchase Buyer-Seller Messaging & Negotiation (`apps/messaging`)
* **Listing-Anchored Inquiry Threads:** Direct, listing-specific communication between prospective buyers and sellers prior to purchasing.
* **Photo Evidence Exchange:** Buyers can request additional close-up photos of bindings, signatures, or page wear directly in the conversation.
* **In-Chat Price Negotiation & Order Confirmation:**
  * Interactive negotiation state (`INQUIRY` ➔ `CONFIRMED` ➔ `DECLINED` ➔ `COMPLETED`).
  * Sellers can confirm a negotiated price directly within the conversation.
  * Buyers can click **"Proceed to Checkout"** directly from an accepted chat offer with the negotiated price locked in.
* **Unread Message Indicators:** Dynamic badge notifications and real-time read receipts.

---

### 9.  Dedicated Modern Platform Admin Dashboard (`apps/accounts`)
* **Executive Financial KPIs:** Live summary of Gross Merchandise Value (GMV), 15% Platform Commission revenue, Escrow in Custody, and Total Completed Payouts.
* **Seller KYC Verification Queue:** Administrative queue to review submitted National IDs and store credentials with 1-click **Approve** or **Reject** actions.
* **Escrow & Payout Custody Manager:** Administrative control to manually release escrow holds or mark payout batches as completed.
* **Courier Dispatch Monitor:** Platform-wide monitoring of unfulfilled, in-transit, and delivered seller shipments.
* **Catalog & Listing Moderation:** Rapid moderation controls to activate, archive, or inspect marketplace book listings.
* **Dedicated Administrative Login (`/admin-login/`):** Role-gated portal separating platform admins from public customer accounts.

---

### 10.  Asynchronous Workers & Performance Optimization (Celery + Redis)
* **Background Image Compression (`process_listing_image_to_webp`):** Uploaded book condition photos are asynchronously converted to optimized **WebP** images via Pillow to drastically reduce mobile bandwidth and enhance page performance.
* **Automated Reservation Sweeper (`sweep_expired_reservations`):** Celery Beat background task continuously cleans up stalled checkouts without blocking HTTP request threads.

---

### 11.  Developer Experience, REST API & OpenAPI 3.0 Documentation
* **Complete RESTful API:** Full coverage across all platform modules under `/api/v1/`.
* **JWT Authentication:** Secure stateless access using `djangorestframework-simplejwt`.
* **Interactive OpenAPI 3.0 Docs:**
  * Swagger UI: `/api/docs/`
  * ReDoc: `/api/redoc/`
  * Raw OpenAPI Schema: `/api/schema/`
* **Automated Smoke Test Suite:** Ready-to-run test suite (`python test_endpoints.py`) to validate all public, authenticated, and administrative endpoints.

---

##  Architecture & Apps Structure

```
book/
├── apps/
│   ├── accounts/     # User identity, KYC verification, addresses, admin dashboard
│   ├── books/        # Master canonical catalog, authors, categories, reviews
│   ├── listings/     # Physical book listings, wear grading, WebP optimization
│   ├── orders/       # Cart, order splitting, 15-min reservation locks, sweeper
│   ├── payments/     # Escrow custody, double-entry ledger, seller payouts
│   ├── shipping/     # Courier providers, parcel tracking events
│   └── messaging/    # Pre-purchase inquiry chat, photo exchange, price negotiation
├── config/           # Django settings (base, local, production), Celery config, URLs
├── requirements/     # Dependency manifests (base.txt, local.txt, production.txt)
├── templates/        # Responsive HTML5 templates, components, and admin views
├── docker-compose.yml# Containerized PostgreSQL 16 & Redis 7 services
└── test_endpoints.py # Automated API endpoint smoke testing script
```

---

##  Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/rafiq9090/bookmangement.git
cd bookmangement
```

### 2. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements/base.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and adjust your database and Redis credentials:
```bash
cp .env.example .env
```

### 5. Spin Up Database & Cache (Docker)
```bash
docker compose up -d
```
* PostgreSQL available on `localhost:5432`
* Redis available on `localhost:6379`

### 6. Apply Database Migrations & Create Superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 7. Run Celery Worker & Beat (Optional for Background Tasks)
```bash
# Terminal 1: Celery Worker
celery -A config worker --loglevel=info

# Terminal 2: Celery Beat (Periodic sweeper)
celery -A config beat --loglevel=info
```

### 8. Run the Development Server
```bash
python manage.py runserver
```
Visit the platform at `http://127.0.0.1:8000/`.

---

##  Useful URLs & Endpoints

| Portal / Feature | URL Route | Description |
| :--- | :--- | :--- |
| **Marketplace Storefront** | `/store/` | Browse catalog with category & condition filters |
| **Book Detail & Listings** | `/books/<slug>/` | View canonical book info, reviews, & seller copies |
| **Buyer Shopping Cart** | `/cart/` | Multi-vendor shopping cart |
| **Checkout Flow** | `/checkout/` | Reservation lock & multi-vendor shipment creation |
| **Parcel Tracking** | `/tracking/` | Real-time parcel tracking with event timeline |
| **Buyer/Seller Inbox** | `/inbox/` | Direct condition inquiry chat & negotiation |
| **Seller Dashboard** | `/seller/dashboard/` | Manage listings, sales, wallet, and shipments |
| **Platform Admin Login** | `/admin-login/` | Dedicated modern admin authentication |
| **Platform Admin Dashboard**| `/admin/dashboard/` | KPIs, KYC approval queue, Escrow, Payouts |
| **Django Admin** | `/admin/` | Standard Django model administration |
| **Swagger UI Documentation**| `/api/docs/` | Interactive OpenAPI 3.0 API documentation |
| **ReDoc Documentation** | `/api/redoc/` | Clean OpenAPI reference documentation |

---

##  Testing the API

Run the automated endpoint smoke tests to verify server connectivity, authentication, catalog discovery, cart, messaging, and payments:

```bash
python test_endpoints.py
```

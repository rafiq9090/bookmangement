# Maintaining the pickup marketplace

## Where to change behavior

| Responsibility | File |
| --- | --- |
| Persistent transaction records and constraints | `apps/orders/models.py` |
| All offer/reservation/pickup/handover rules | `apps/orders/services/pickup.py` |
| Website and API adapters | `apps/orders/pickup_views.py` |
| Scheduled reservation expiry | `apps/orders/tasks.py` |
| Public location validation and image validation | `apps/listings/forms.py` |
| Public and private manual map pins | `static/js/location-map.js` |
| Tests, including PostgreSQL concurrency | `apps/orders/test_pickup.py` |

Views must call the domain service. Do not change agreement or reserved listing
status directly. Always lock listing first, agreement second within one database
transaction. API listing edits and uploads use the same listing lock so an accepted
copy cannot be edited concurrently.

## Lifecycle

`REQUESTED -> RESERVED -> PICKUP_AGREED -> AWAITING_CONFIRMATION -> COMPLETED`

- The buyer can revise a pending offer; seller acceptance freezes its price.
- Seller acceptance reserves for 48 hours. Only one live agreement per copy.
- Either participant proposes pickup. The other must accept. Acceptance extends
  expiry to at least 24 hours after the appointment, up to a 14-day scheduling horizon.
- Rescheduling preserves the reservation but requires renewed acceptance.
- Before handover, either party can cancel. Pending requests cannot release another
  buyer's reservation. Cancelled/declined/expired requests can be replaced with a new
  agreement in the same chat; historical agreements remain intact.
- Either confirmation freezes expiry and cancellation. Only both confirmations mark
  a copy SOLD. Missing confirmation or disputes require moderation.
- Reports freeze live reservations as DISPUTED; they do not establish wrongdoing.
- Staff resolve disputed agreements with a required reason. Resolution is recorded
  in a report and both parties are notified. Completed means SOLD; cancelled means
  the copy is still with the seller and may be restocked.
- One seller review per completed agreement, submitted only by its buyer.

## API (JWT authentication)

Create with `POST /api/v1/pickups/`:

```json
{"listing_id": 12, "offered_price": "400.00"}
```

List owned agreements with `GET /api/v1/pickups/`; inspect or act on one at
`/api/v1/pickups/<id>/`. POST actions use the same service as web forms:

```json
{"action": "accept"}
```

```json
{"action": "propose_pickup", "pickup_place": "Public library entrance", "pickup_at": "2026-10-10T15:00:00+06:00", "pickup_instructions": "Meet outside", "pickup_latitude": "23.810000", "pickup_longitude": "90.410000"}
```

Other actions: `accept_pickup`, `confirm`, `cancel`, `decline`, `report` with
`details`, and `review` with `rating` and optional `comment`.

API listings start DRAFT. Upload an actual-copy image via
`POST /api/v1/listings/<id>/images/` (multipart field `image`) to publish a valid
location-bearing draft. Web creation requires an actual-copy photo up front.
Images are validated and limited to 10 MB each and five per copy. Asynchronous
WebP optimization failure does not invalidate a committed upload.

## Privacy

Public listing serializers contain approximate area coordinates and district/area
only. They contain no exact pickup instructions, exact meeting coordinates or
phone numbers. Agreement endpoints and pages filter by participant before reading
or mutating. Admin access is separate. Exact pins should describe a public meeting
place. Map tile requests go to OpenStreetMap; private database access controls do
not make the external map provider unaware of the displayed map area.

## Existing data and operational notes

Migrations preserve historic courier orders/payment tables. Existing COLLECTIBLE
copies retain their old condition value and are flagged `condition_needs_review`;
they are hidden from discovery until the seller explicitly assigns a physical grade.
The collectible flag is retained. Existing listings missing area/photos should be
reviewed by their owners; migrations do not invent locations.

Pickup checkout redirects to agreements. API legacy checkout, payment initiation,
payment callbacks, payouts and courier callbacks are disabled while
`LOCAL_PICKUP_ENABLED=True`. Historic transaction pages remain readable.

Do not enable the legacy commerce flow merely to process an old transaction:
its gateway validation needs a separate hardening effort.

Notifications are in-app. Email delivery is currently used for password reset only.
Set EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD and
DEFAULT_FROM_EMAIL for production reset mail.

Run migrations before restarting the server. Do not auto-apply migrations on every
web request. Run the PostgreSQL test suite before changing reservation transitions.

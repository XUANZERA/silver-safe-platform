# Foreground Real Location Phase 1 — Detailed Design

Status: Implemented — Pending Manual Acceptance
Depends on finalized ADR-010

---

## 1. Purpose

This document defines the implementation boundary for foreground REAL location acquisition based on finalized ADR-010.

---

## 2. Expected Existing Backend Contract

Before implementation, the developer must inspect the actual repository and confirm the real Location API contract.

The following fields are expected from previous project work but must not be assumed without code inspection:

- client_location_id
- latitude
- longitude
- accuracy_meters
- speed_mps
- source
- recorded_at

Implementation must verify:

- exact endpoint;
- exact request schema;
- required/optional fields;
- response status codes;
- ownership/authentication;
- Trip state requirements;
- idempotency behavior;
- duplicate client_location_id behavior;
- accuracy handling;
- Risk invocation;
- persistence behavior.

If actual code differs, this document must be updated before implementation.

---

## 3. Proposed Frontend Structure

Preferred structure:

frontend/src/services/location/
    RealLocationProvider.js
    LocationUploadCoordinator.js
    locationSample.js
    locationMapper.js

However, implementation should follow existing repository style.

Do not create extra files/classes only for architectural appearance.

A smaller design is acceptable if responsibilities remain separated.

---

## 4. RealLocationProvider

### 4.1 Interface

Conceptual API:

createRealLocationProvider(options?)

provider.start(onLocation, onError)
provider.stop()
provider.getStatus()

### 4.2 Internal Browser API

Implementation shall use:

navigator.geolocation.watchPosition(...)

Browser options must be reviewed against actual product requirements.

Do not claim high precision merely because enableHighAccuracy is requested.

### 4.3 Start Behavior

start():

1. reject duplicate active start or return current status safely;
2. verify navigator.geolocation exists;
3. transition technical state to REQUESTING;
4. call watchPosition;
5. store returned watch ID;
6. translate successful positions to LocationSample;
7. translate geolocation errors into stable error categories.

### 4.4 Stop Behavior

stop():

1. if watch ID exists:
   navigator.geolocation.clearWatch(watchId)
2. clear internal watch ID;
3. prevent later stale callbacks from being accepted;
4. return state to IDLE.

Calling stop repeatedly must be safe.

---

## 5. Provider Error Mapping

The provider should normalize browser-specific errors into stable internal error types.

Required conceptual categories:

PERMISSION_DENIED
POSITION_UNAVAILABLE
TIMEOUT
UNSUPPORTED
UNKNOWN

These are technical location errors, not Safety results.

---

## 6. LocationSample Design

Conceptual shape:

{
  latitude: number,
  longitude: number,
  accuracyMeters: number | null,
  speedMps: number | null,
  recordedAt: string,
  source: string,
  sourceCrs: string
}

### Validation

latitude:
finite
-90 <= value <= 90

longitude:
finite
-180 <= value <= 180

accuracyMeters:
null or finite >= 0

speedMps:
null or finite value accepted according to actual backend contract

recordedAt:
valid ISO-8601 representation

source:
must correspond to the agreed REAL frontend source identifier.

sourceCrs:
must match ADR-010.

No CRS guessing is permitted.

---

## 7. Coordinate Contract

The coordinate contract is finalized per ADR-010:

Allowed source CRS:
WGS84 only (`CoordinateReferenceSystem.WGS84`)

Browser Geolocation source CRS:
WGS84 (per W3C Geolocation API standard specification)

Backend canonical CRS:
WGS84

Persisted Location CRS:
WGS84

Geofence CRS:
WGS84

AMap display CRS:
GCJ-02 (presentation boundary only)

Normalization function/location:
`app.core.coordinates.normalize_location_coordinates`
Phase 1 normalization is an explicit identity boundary: it validates that `source_crs == CoordinateReferenceSystem.WGS84` (rejecting any unsupported CRS with `422 / UNSUPPORTED_SOURCE_CRS`) and returns canonical coordinates unchanged as WGS84.

Unknown CRS behavior:
REJECT — no silent fallback.

---

## 8. LocationUploadCoordinator

### 8.1 Responsibilities

Coordinator owns:

- active Trip binding;
- sample acceptance;
- client_location_id;
- throttling;
- one request in flight;
- newest pending sample;
- payload mapping;
- API invocation;
- transport state;
- stopping.

Coordinator does not own:

- browser geolocation;
- Risk;
- Alert creation;
- Family UI;
- coordinate guessing.

---

## 9. Coordinator State

Conceptual internal state:

running
tripId
inFlight
pendingLatestSample
lastUploadStartedAt
timer
generation/lifecycle token

The implementation may use equivalent simpler state.

---

## 10. Start Coordinator

Conceptually:

coordinator.start(tripId)

Requirements:

- tripId must be a valid active backend Trip ID;
- duplicate start for the same lifecycle must not create duplicate timers;
- new lifecycle should invalidate stale callbacks from previous lifecycle.

---

## 11. Sample Handling

handleSample(sample):

1. reject if coordinator not running;
2. validate sample;
3. capture current lifecycle generation;
4. if request is currently in flight:
   overwrite pendingLatestSample;
   return;
5. calculate remaining throttle delay;
6. if delay required:
   retain latest pending sample;
   schedule one timer;
7. otherwise upload sample.

No unbounded queue.

---

## 12. Upload

upload(sample):

1. confirm coordinator still running;
2. confirm current Trip ID still valid for coordinator lifecycle;
3. build API payload;
4. create/reuse client_location_id;
5. mark inFlight;
6. invoke locationApi upload;
7. clear inFlight;
8. if pending latest sample exists:
   process only the latest pending sample according to throttle timing.

---

## 13. Throttling

Configuration:

VITE_LOCATION_UPLOAD_MIN_INTERVAL_MS

Recommended default:

10000

The exact implementation should use the project's existing configuration conventions.

The minimum interval must not be hardcoded in multiple components.

---

## 14. Client Location ID

Implementation must inspect the backend idempotency contract.

If backend treats client_location_id as an idempotency key:

the same logical sample retry must reuse the same client_location_id.

A retry must not generate a new ID for the same sample.

If backend does not support this contract:

do not invent a client-side durable retry protocol in Phase 1.

---

## 15. Failure Semantics

### API success

Location upload success indicates:

“backend accepted this location request”

It does not indicate:

SAFE.

### API failure

On network/5xx/appropriate backend failure:

location technical state may become DEGRADED.

No fake Safety value.

No Mock fallback.

No unbounded automatic retry queue.

A later new sample may be uploaded according to normal coordinator behavior.

---

## 16. ElderHome Integration

The REAL Elder page should expose location controls only when:

realMode
&& tripDataAvailable
&& currentTrip
&& currentTrip.status === "active"

Suggested UI:

状态区域:

定位守护：未开启

[开启定位守护]

After click:

正在请求定位权限…

Successful tracking:

定位守护运行中

辅助说明:

定位守护需要保持页面运行。

The UI must not state that:

- the user is safe;
- Family has already received the position;
- background tracking is guaranteed.

---

## 17. Disable Control

While active tracking is running, provide:

“关闭定位守护”

User disable:

provider.stop()
coordinator.stop()
technical state → IDLE

Stopping location protection must not end the Trip.

Trip lifecycle and location lifecycle remain distinct.

---

## 18. Trip End Integration

Before or as part of successful Trip End handling:

the active location lifecycle must stop.

No location callback may upload using an ended Trip after stop.

If an HTTP request was already in flight:

the coordinator must not schedule a subsequent pending upload after lifecycle invalidation.

Whether the already-sent request is cancellable depends on the current API implementation and is not required unless existing infrastructure supports AbortController.

---

## 19. Logout Integration

Logout must stop location tracking before local user state disappears.

No watch/timer should survive logout.

---

## 20. Component Unmount

onUnmounted:

provider.stop()
coordinator.stop()

Cleanup must be idempotent.

---

## 21. Reload Behavior

When ElderHome loads and backend reports an active Trip:

do not automatically call provider.start().

Display:

“开启定位守护”

and wait for user interaction.

No persisted browser “tracking enabled” flag is required in Phase 1.

---

## 22. REAL / DEMO Wiring

REAL:

RealLocationProvider
→ coordinator
→ REAL Location API

DEMO:

existing Mock/Simulator behavior.

Repo-wide constraints:

- Mock provider must not be imported into a REAL upload path.
- Demo simulator must not call REAL location upload.
- REAL geolocation error must never instantiate Mock provider.

---

## 23. Backend Processing

Actual backend flow must be verified in source.

Desired flow:

authenticated Elder
→ Trip ownership/state validation
→ Location request validation
→ source CRS validation
→ coordinate normalization
→ persistence
→ Risk evaluation
→ Alert transition when required
→ response

If current backend performs Risk before CRS normalization:

implementation is blocked until corrected.

---

## 24. Safety View

After backend persistence, existing Safety View should continue to derive:

trip_status
location_health
risk_status
open_alert_count
latest_location
latest_open_alert
calculated_at

The frontend location implementation must not create a competing local Safety View.

---

## 25. Privacy

Forbidden:

console.log(sample)
console.log(payload)
console.log(latitude, longitude)

Forbidden persistence:

localStorage
sessionStorage
IndexedDB
Demo itinerary storage

Forbidden transmission:

AI endpoints
query-string URLs
third-party services other than explicitly required positioning/map infrastructure.

---

## 26. Required Frontend Tests

### LOC-FE-001

No Trip:
Enable unavailable.

### LOC-FE-002

created Trip:
Enable unavailable.

### LOC-FE-003

active Trip:
Enable available.

### LOC-FE-004

Unsupported browser:
UNSUPPORTED.

### LOC-FE-005

Permission denied:
PERMISSION_DENIED.

### LOC-FE-006

Valid browser position:
correct LocationSample.

### LOC-FE-007

Invalid latitude/longitude:
sample rejected.

### LOC-FE-008

Repeated Enable:
one geolocation watch only.

### LOC-FE-009

One upload pending + multiple samples:
only latest pending sample retained.

### LOC-FE-010

Throttle:
requests respect configured minimum interval.

### LOC-FE-011

Stop:
clearWatch called once as needed;
timers cleared;
no later upload.

### LOC-FE-012

Trip End while upload pending:
no pending follow-up upload after lifecycle stop.

### LOC-FE-013

Unmount:
watch and timer cleaned.

### LOC-FE-014

Logout:
location lifecycle stopped.

### LOC-FE-015

REAL failure:
no Mock fallback.

### LOC-FE-016

Demo:
existing simulator behavior unchanged.

### LOC-FE-017

Upload failure:
DEGRADED.

### LOC-FE-018

Later upload success:
technical state may recover to TRACKING.

---

## 27. Required Backend Tests

Exact tests depend on current Location API contract.

At minimum verify:

### LOC-BE-001

Only authorized Elder can upload for their Trip.

### LOC-BE-002

Inactive/non-owned Trip rejected.

### LOC-BE-003

Valid sample persisted.

### LOC-BE-004

Invalid coordinates rejected.

### LOC-BE-005

Unknown CRS rejected.

### LOC-BE-006

Supported source CRS normalized before persistence/Risk.

### LOC-BE-007

Location and Geofence use canonical CRS consistently.

### LOC-BE-008

Risk is invoked after normalization.

### LOC-BE-009

Safety View latest_location reflects persisted normalized Location.

### LOC-BE-010

client_location_id duplicate semantics match actual contract.

---

## 28. Regression Tests

Must run:

backend full pytest
frontend npm test
frontend npm run build
ruff check
ruff format --check
git diff --check

Tests requiring database writes must use isolated test databases and must never mutate:

data/silver_safe.db

---

## 29. Manual Acceptance

After automated review passes, manually validate on a real mobile browser:

REAL login
→ Create Trip
→ Start Trip
→ active
→ Enable Location Protection
→ grant permission
→ real location acquired
→ POST Location
→ backend Location exists
→ Family Safety View latest_location updates

Then verify:

Disable Location
→ no further uploads.

Trip End
→ no further uploads.

Permission denial
→ no Demo fallback.

---

## 30. Known Non-Goals

Successful Phase 1 implementation does not prove:

- reliable background mobile tracking;
- lock-screen tracking;
- real-time guarantees;
- navigation;
- route deviation detection;
- fall detection;
- battery monitoring;
- WeChat Mini Program support.

Those require separate requirements and architecture decisions.
# Foreground Real Location Phase 1 — Requirements

Status: Implemented — Pending Manual Acceptance
Scope: REAL Mode Foreground Location Ingestion
Depends on: ADR-001, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-010

---

## 1. Background

The current REAL-mode workflow already supports:

- Backend-authenticated Elder / Family / Operator users.
- REAL / DEMO isolation.
- Elder REAL Trip creation.
- Trip lifecycle: created → active → completed.
- Elder SOS.
- Backend-authoritative Safety View.
- Alert lifecycle: NEW → PROCESSING → RESOLVED.
- Family monitoring.
- Operator alert handling.

The major missing link is real location ingestion.

At present, the system can create and start a REAL Trip, but the REAL frontend does not yet acquire actual device locations and upload them to the backend.

Therefore, the safety workflow currently has:

Trip
→ SOS
→ Alert
→ Family / Operator

but is still missing:

Active Trip
→ Real Device Location
→ Location Persistence
→ Risk Evaluation
→ Safety View

This phase fills that gap.

---

## 2. Goal

The goal of Phase 1 is to allow an Elder with an active REAL Trip to explicitly enable foreground location protection.

The target flow is:

Elder active Trip
→ user explicitly enables location protection
→ browser acquires real device location
→ RealLocationProvider emits LocationSample
→ LocationUploadCoordinator binds the sample to the active Trip
→ location is uploaded to the backend
→ backend validates and normalizes coordinates
→ backend persists Location
→ existing Risk pipeline evaluates the location
→ Family Safety View can expose the latest authoritative location/risk state

The backend remains the single source of truth for safety.

---

## 3. In Scope

This phase includes:

1. Foreground browser geolocation.
2. Explicit user permission/start action.
3. RealLocationProvider.
4. Standard LocationSample representation.
5. LocationUploadCoordinator.
6. Location payload mapping.
7. Upload throttling.
8. Single in-flight upload protection.
9. Latest-wins buffering while an upload is in flight.
10. Backend CRS validation/normalization according to finalized ADR-010.
11. Backend Location persistence.
12. Existing backend Risk invocation.
13. Safety View latest_location update.
14. Accurate frontend location technical states.
15. Explicit stop lifecycle.
16. REAL / DEMO isolation.
17. Privacy protections for real coordinates.

---

## 4. Out of Scope

The following are explicitly excluded from Phase 1:

- Guaranteed background location.
- Lock-screen continuous tracking.
- WeChat Mini Program implementation.
- Native mobile application.
- IndexedDB/offline durable location queue.
- Full trajectory replay.
- Route planning.
- POI search.
- Navigation.
- Route deviation detection.
- Long-stationary detection.
- Fall detection.
- Battery monitoring.
- New AI safety decisions.
- WebSocket.
- Redis.
- Message queue.
- Operator Trip creation.
- Complex geofence shapes.
- Map route rendering.

These may be addressed in later phases.

---

## 5. Preconditions

### PRE-LOC-001 Active Trip

REAL location protection may only be enabled when:

currentTrip != null
AND
currentTrip.status == "active"

No location acquisition or upload may begin for:

- no Trip;
- created Trip;
- completed Trip;
- cancelled Trip.

### PRE-LOC-002 CRS Contract

The CRS contract is finalized per ADR-010:

- Browser/H5 source = WGS84
- Backend canonical = WGS84
- Persisted Location = WGS84
- Geofence = WGS84
- Risk evaluation = WGS84
- AMap presentation = GCJ-02
- Phase 1 source_crs = exact WGS84 only

No implementation may guess WGS84, GCJ-02, EPSG values, or perform silent conversion. Any unknown or unsupported CRS is strictly rejected.

---

## 6. Functional Requirements

### FR-LOC-001 Explicit Enable

The system shall not automatically request geolocation permission on page load.

After the Trip is confirmed by the backend as active, the Elder page shall display:

“开启定位守护”

Only an explicit user action may start foreground geolocation.

---

### FR-LOC-002 Foreground-Only Truthfulness

Phase 1 is foreground-only.

The UI must state that location protection requires the page to remain running.

The UI must not claim:

- guaranteed background tracking;
- lock-screen tracking;
- always-on protection;
- “北斗已连接”;
- uninterrupted real-time positioning.

---

### FR-LOC-003 RealLocationProvider

REAL mode shall use a RealLocationProvider backed by the browser geolocation API.

Conceptual interface:

start(onLocation, onError)
stop()
getStatus()

The provider shall only be responsible for acquiring raw device positions.

The provider must not:

- know trip_id;
- call backend APIs;
- calculate risk;
- create alerts;
- access Family/Operator logic;
- persist location into browser storage;
- fall back to MockLocationProvider.

---

### FR-LOC-004 LocationSample

RealLocationProvider shall emit a normalized frontend LocationSample containing at least:

- latitude
- longitude
- accuracyMeters
- speedMps
- recordedAt
- source
- sourceCrs

sourceCrs must be exact "WGS84" per finalized ADR-010.

LocationSample validation shall reject invalid local samples before upload:

- latitude must be finite and within [-90, 90];
- longitude must be finite and within [-180, 180];
- accuracy, when provided, must be finite and >= 0;
- recordedAt must be a valid timestamp.

Frontend validation is input hygiene only.

Frontend must not perform final safety/risk classification.

---

### FR-LOC-005 LocationUploadCoordinator

Location upload orchestration shall be separated from RealLocationProvider.

The coordinator is responsible for:

- binding samples to the current active Trip;
- generating/reusing client_location_id as required by the actual backend contract;
- mapping frontend field names to API payload field names;
- upload throttling;
- one in-flight upload at a time;
- latest-wins buffering;
- stopping uploads when the Trip/lifecycle ends.

---

### FR-LOC-006 Upload Throttling

The frontend shall not POST every geolocation callback.

A configurable minimum upload interval shall be used.

Proposed configuration:

VITE_LOCATION_UPLOAD_MIN_INTERVAL_MS

Recommended initial default:

10000 ms

The value shall remain configurable and shall not be duplicated as magic numbers across components.

Final implementation must verify whether 10 seconds is appropriate for the existing backend/risk logic.

---

### FR-LOC-007 Single In-Flight Request

At most one location upload may be in flight for one coordinator.

If new samples arrive while an upload is running:

P1 uploading
P2 arrives
P3 arrives
P4 arrives

the system shall not create an unbounded queue.

Phase 1 shall use latest-wins behavior:

retain only P4.

After P1 completes, P4 may be uploaded when allowed by the throttle.

---

### FR-LOC-008 Upload Failure

A location upload failure shall not be interpreted as a safety result.

The frontend technical location state may enter:

DEGRADED

The UI must not show SAFE because an upload failed.

The frontend must not automatically switch to Demo location.

---

### FR-LOC-009 Backend Authority

The frontend shall never determine final:

SAFE
PENDING
ALERT

based solely on device location.

The authoritative sequence remains:

Location
→ backend validation / normalization
→ persistence
→ backend Risk
→ backend Alert if required
→ Safety View

---

### FR-LOC-010 REAL / DEMO Isolation

REAL mode:

RealLocationProvider only.

DEMO mode:

existing Mock/Simulator behavior only.

Forbidden transitions:

REAL geolocation error
→ MockLocationProvider

and:

Mock location
→ REAL backend location upload

---

### FR-LOC-011 Stop Lifecycle

The provider and coordinator must stop when any of the following occurs:

- user explicitly disables location protection;
- Trip ends;
- logout;
- Elder page/component unmounts.

Stopping must:

- clear browser geolocation watch;
- clear internal timers;
- stop further uploads;
- prevent stale callbacks from uploading against an ended Trip.

---

### FR-LOC-012 Reload Behavior

If a page reload occurs while the backend Trip is already active:

the frontend must not silently restart real geolocation.

The page shall again show:

“开启定位守护”

and wait for explicit user action.

---

## 7. Location Technical States

Location acquisition/upload technical state is independent from backend RiskStatus.

Required conceptual states:

IDLE
REQUESTING
TRACKING
DEGRADED
PERMISSION_DENIED
UNSUPPORTED

Examples of valid combinations:

TRACKING + SAFE
TRACKING + ALERT
DEGRADED + PENDING

The frontend technical location state must never overwrite backend Safety state.

---

## 8. Error Semantics

### Unsupported browser

If browser geolocation is unavailable:

state = UNSUPPORTED

UI shall explain that the current browser does not support location acquisition.

No Mock fallback.

### Permission denied

If the user denies location permission:

state = PERMISSION_DENIED

No automatic re-prompt loop.
No Mock fallback.

### Temporary geolocation failure

Temporary acquisition errors shall be surfaced accurately.

The frontend must not claim active positioning while no usable sample is being received.

### Backend upload failure

Upload failure:

→ DEGRADED

Later successful upload may recover:

→ TRACKING

No fake Safety result may be derived from either state.

---

## 9. Coordinate Requirements

ADR-010 is authoritative.

The final pipeline must conceptually be:

Incoming Location
→ explicit source_crs
→ validate allowed CRS
→ Coordinate Normalizer
→ canonical CRS
→ persistence
→ Risk evaluation

Unknown CRS shall not be silently guessed.

Risk and Geofence coordinates must be evaluated in the same canonical coordinate system.

---

## 10. Privacy Requirements

Real coordinates are sensitive user data.

Phase 1 must not:

- console.log full coordinates;
- write coordinates to localStorage;
- write coordinates to sessionStorage;
- write coordinates to Demo itinerary storage;
- send coordinates to AI services;
- place coordinates in URL query parameters.

Coordinates may only be sent to the defined backend Location API.

---

## 11. Acceptance Criteria

### AC-LOC-001

Given a REAL active Trip:

Elder clicks “开启定位守护”
→ browser requests permission
→ provider starts
→ real LocationSample is produced.

### AC-LOC-002

A valid sample:

→ frontend coordinator
→ backend Location API
→ backend Location persisted.

### AC-LOC-003

After successful backend processing:

Family Safety View can retrieve a non-null latest_location corresponding to the REAL Trip.

### AC-LOC-004

REAL geolocation failure never starts MockLocationProvider.

### AC-LOC-005

No inactive Trip can upload REAL location.

### AC-LOC-006

At most one location upload is in flight.

### AC-LOC-007

Multiple samples received while one upload is pending do not form an unbounded queue; latest-wins behavior is applied.

### AC-LOC-008

Trip End / logout / component unmount stops the provider and coordinator.

### AC-LOC-009

The frontend never derives final SAFE/PENDING/ALERT from browser samples.

### AC-LOC-010

Unknown or unsupported CRS is rejected according to ADR-010 rather than guessed.

---

## 12. Required Tests

At minimum:

LOC-001 active Trip can enable location
LOC-002 no/inactive Trip cannot enable
LOC-003 permission denied
LOC-004 unsupported browser
LOC-005 valid LocationSample
LOC-006 invalid latitude/longitude
LOC-007 single in-flight upload
LOC-008 latest-wins
LOC-009 throttling
LOC-010 stop clears watch/timer
LOC-011 REAL never uses Mock
LOC-012 Demo unchanged
LOC-013 upload failure → DEGRADED
LOC-014 later upload success → TRACKING
LOC-015 unknown CRS rejected
LOC-016 normalization occurs before Risk
LOC-017 backend Location persistence
LOC-018 Safety View latest_location updated

If backend client_location_id idempotency already exists:

LOC-019 duplicate client_location_id behavior.

---

## 13. Definition of Done

Phase 1 is complete only when the following REAL chain works:

REAL Elder login
→ create Trip
→ start Trip
→ backend confirms active
→ explicitly enable location protection
→ real device position acquired
→ real position uploaded
→ backend persists Location
→ backend Risk pipeline executes
→ Family Safety View exposes latest_location

Map rendering and background tracking are not required for Phase 1 completion.
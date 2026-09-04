# Foreground Real Location Phase 1 — Overall Design

Status: Implemented — Pending Manual Acceptance
Related Requirements: real-location-phase1.md
Related ADRs: ADR-001, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-010

---

## 1. Design Objective

This design introduces the first REAL device-location ingestion path without changing the existing backend-authoritative safety architecture.

The system shall extend the current workflow:

Trip
→ Safety / SOS / Alert

into:

Active Trip
→ Real Location
→ Backend Location
→ Backend Risk
→ Safety View
→ Family / Operator

The frontend remains responsible for acquiring and transporting location data.

The backend remains responsible for authoritative safety interpretation.

---

## 2. Architecture

High-level architecture:

Elder UI
    |
    | explicit enable
    v
RealLocationProvider
    |
    | LocationSample
    v
LocationUploadCoordinator
    |
    | payload mapping
    v
locationApi
    |
    | HTTP POST
    v
Backend Location Endpoint
    |
    v
Coordinate Validation / Normalization
    |
    v
Location Persistence
    |
    v
Existing Risk Service
    |
    +----> Alert, when applicable
    |
    v
Safety View
    |
    +------------+
    |            |
    v            v
 Family       Operator

---

## 3. Architectural Principles

### 3.1 Backend Single Source of Truth

Frontend location acquisition is not equivalent to safety determination.

The frontend may know:

“a device sample was acquired”

or:

“an upload succeeded”

but must not infer:

SAFE
PENDING
ALERT

The final safety state must come from backend Risk/Safety logic.

---

### 3.2 Provider / Transport Separation

RealLocationProvider must not perform HTTP requests.

Its responsibility ends at:

device API
→ LocationSample

LocationUploadCoordinator handles:

LocationSample
→ Trip binding
→ API payload
→ upload lifecycle

This prevents device-specific code from becoming coupled to backend business logic.

---

### 3.3 REAL / DEMO Isolation

The existing Mock location path remains a Demo mechanism.

The architecture shall not implement:

RealLocationProvider failure
→ fallback MockLocationProvider

REAL and DEMO must remain separate at both route/presentation and upload levels.

---

## 4. Proposed Components

### 4.1 Elder UI

Responsibilities:

- check authoritative current Trip;
- expose “开启定位守护” only for active REAL Trip;
- initiate provider lifecycle;
- display technical location state;
- stop location lifecycle when required.

The Elder UI must not contain coordinate conversion or Risk logic.

---

### 4.2 RealLocationProvider

Conceptual responsibilities:

navigator.geolocation.watchPosition
→ LocationSample

Conceptual interface:

start(onLocation, onError)
stop()
getStatus()

It does not know:

- trip_id;
- APIs;
- backend;
- Safety state;
- Alert state.

---

### 4.3 LocationSample

Frontend internal representation:

LocationSample {
    latitude
    longitude
    accuracyMeters
    speedMps
    recordedAt
    source
    sourceCrs
}

The sourceCrs value is WGS84 per finalized ADR-010.

---

### 4.4 LocationUploadCoordinator

Responsibilities:

- bind active Trip ID;
- validate sample eligibility;
- generate/reuse client location identifier;
- throttle uploads;
- prevent overlap;
- retain latest pending sample;
- map payload fields;
- invoke Location API;
- update transport technical state;
- stop safely.

The coordinator does not calculate Risk.

---

### 4.5 Backend Coordinate Boundary

The backend must own the normalization boundary.

Conceptually:

API request
→ validate source_crs
→ normalize to canonical CRS
→ persist canonical coordinates
→ invoke Risk

Risk must never run against mixed coordinate systems.

Behavior is governed by finalized ADR-010 (identity normalization for WGS84, reject unknown CRS).

---

## 5. Location State Model

Location technical state is independent from Safety state.

Conceptual state model:

IDLE
  |
  | user Enable
  v
REQUESTING
  |
  +---- unsupported ------> UNSUPPORTED
  |
  +---- permission denied -> PERMISSION_DENIED
  |
  v
TRACKING
  |
  +---- upload failures --> DEGRADED
  |                         |
  |                         | later successful upload
  |                         v
  +---------------------- TRACKING
  |
  | stop
  v
IDLE

This is not a backend Risk state machine.

---

## 6. Enable Flow

REAL Elder page:

GET current-trip
→ active Trip confirmed
→ display “开启定位守护”
→ user clicks
→ state REQUESTING
→ browser geolocation permission flow
→ provider begins watch
→ valid sample
→ state TRACKING / upload processing

If Trip is not active:

location cannot start.

---

## 7. Upload Flow

Location callback
→ validate sample
→ coordinator.handleSample(sample)
→ throttle check
→ in-flight check
→ map API payload
→ POST Location
→ backend authoritative processing

If another sample arrives while upload is pending:

only the newest pending sample is retained.

No unbounded FIFO location queue is introduced in Phase 1.

---

## 8. Failure Flow

### Device permission failure

REQUESTING
→ PERMISSION_DENIED

No backend upload.
No Mock fallback.

### Unsupported API

REQUESTING
→ UNSUPPORTED

### Backend failure

TRACKING
→ upload error
→ DEGRADED

Future valid upload success may restore TRACKING.

The frontend still does not infer Safety.

---

## 9. Stop Flow

Any of:

user Disable
Trip End
logout
component unmount

must cause:

provider.stop()
coordinator.stop()

which must:

clearWatch
clear timers
invalidate current lifecycle
prevent subsequent stale callbacks from uploading.

---

## 10. CRS Architecture

Finalized per ADR-010:

- Browser/H5 source = WGS84
- Backend canonical = WGS84
- Persisted Location = WGS84
- Geofence = WGS84
- Risk evaluation = WGS84
- AMap presentation = GCJ-02
- Phase 1 source_crs = exact WGS84 only

Architecture:

Source CRS
      |
      v
Allowed-source validation
      |
      v
CoordinateNormalizer
      |
      v
Canonical CRS
      |
      +----> Location persistence
      |
      +----> Geofence / Risk

The following are forbidden:

- silent source CRS assumption;
- mixed Geofence and Location CRS;
- frontend-only conversion with backend unaware;
- Risk before normalization.

---

## 11. Persistence

Phase 1 shall reuse the current backend Location persistence model where possible.

No database schema change shall be introduced solely for architecture aesthetics.

If finalized CRS contract requires persistent metadata not supported by the current schema:

implementation must stop and request a schema/migration decision.

---

## 12. Polling and Downstream Consumers

Family and Operator do not consume browser location directly.

They continue to read backend-derived endpoints such as:

Safety View
Alerts
current Trip

No WebSocket is introduced.

Existing polling-first architecture remains unchanged.

---

## 13. Privacy Architecture

Real coordinates shall exist only in:

- browser process memory while active;
- HTTPS/API request body;
- authorized backend persistence.

They shall not be placed in:

- URL;
- localStorage;
- sessionStorage;
- Demo cache;
- console logs;
- AI prompts/services.

---

## 14. Deployment Scope

Phase 1 is designed for foreground H5/browser validation.

It is explicitly not evidence of reliable background mobile tracking.

Future WeChat Mini Program or native implementations may provide different provider implementations while preserving:

Provider
→ LocationSample
→ UploadCoordinator
→ Backend

---

## 15. Implementation Boundary

Expected frontend changes should be limited to location-related services/components and the Elder REAL location control.

Expected backend changes enforce the finalized ADR-010 CRS contract.

The following should remain unchanged unless review proves direct necessity:

- Trip creation architecture;
- SOS semantics;
- Alert lifecycle;
- Operator concurrency;
- Safety View meaning;
- polling architecture;
- Demo simulator behavior.

---

## 16. Phase Completion

Phase 1 is considered architecturally complete when:

Real browser location
→ backend Location persistence
→ existing backend Risk pipeline
→ Safety View latest_location

is demonstrated without:

- Mock fallback;
- local Risk authority;
- mixed CRS;
- persistent frontend location cache;
- background-location claims.
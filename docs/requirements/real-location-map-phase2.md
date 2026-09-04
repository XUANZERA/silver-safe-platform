# REAL Location Map Presentation Phase 2 — Requirements

Status: Draft for Review

Depends on:
- Foreground Real Location Phase 1
- ADR-001
- ADR-004
- ADR-006
- ADR-007
- ADR-010

## 1. Background

Phase 1 provides the authoritative pipeline:

Real Device Location
→ Backend WGS84 Location
→ Persistence
→ Risk
→ Safety View

However, Family and Operator users still lack a trustworthy map
presentation of the backend location.

Phase 2 introduces backend-authoritative map visualization.

## 2. Goal

Allow authorized Family and Operator users to view:

- the Elder's latest authoritative location;
- location timestamp / freshness information;
- recent authoritative track when an existing backend endpoint supports it;
- safety/alert state alongside, but independent from, the map.

The map must never consume the Elder browser's raw location directly.

## 3. In Scope

- Family REAL latest-location map.
- Operator REAL latest-location context where existing UI supports it.
- Existing backend Location/Safety/track endpoint consumption.
- WGS84 backend coordinates.
- WGS84 → GCJ-02 conversion only at AMap presentation boundary.
- Latest-position marker.
- Recent track only if an existing authoritative endpoint already supports it.
- Polling using the project's existing polling-first architecture.
- No-data, stale/unavailable and conversion-failure presentation.
- REAL / DEMO isolation.
- Privacy and access-control validation.

## 4. Out of Scope

- Navigation.
- Route planning.
- POI search.
- Background location.
- WeChat Mini Program.
- New Risk algorithms.
- Route deviation.
- Fall detection.
- WebSocket.
- Redis.
- Persistent frontend location cache.
- New backend Location schema solely for map rendering.

## 5. Preconditions

Phase 1 must be accepted.

ADR-010 is authoritative:

Backend Location:
WGS84

Backend Risk / Geofence:
WGS84

AMap presentation:
GCJ-02

The backend must never persist converted map coordinates.

## 6. Functional Requirements

### FR-MAP-001 Backend Authority

Family and Operator maps consume only backend-returned Location data.

Forbidden:

Elder browser location
→ directly to Family map

### FR-MAP-002 Coordinate Boundary

Backend WGS84 coordinates must not be passed directly to AMap.

Required path:

Backend WGS84
→ presentation coordinate adapter
→ GCJ-02
→ AMap

Conversion must not modify backend/domain data.

### FR-MAP-003 Latest Location

When Safety View or the authoritative Location API returns a latest Location,
the UI may render an Elder marker only after successful map-coordinate conversion.

### FR-MAP-004 No Location

No latest Location:

show:

“暂无可用定位数据”

Do not place a fake/default Elder marker.

### FR-MAP-005 Unavailable

Backend unavailable:

show:

“暂时无法获取最新位置”

Do not retain stale location and present it as current without labeling.

### FR-MAP-006 Safety Separation

Map display state is independent from RiskStatus.

A successfully rendered marker does not imply SAFE.

A map conversion failure does not imply ALERT.

### FR-MAP-007 Timestamp

Where backend data provides recorded_at,
the UI must expose when the location was recorded.

Do not describe old data as “实时位置”.

### FR-MAP-008 Recent Track

Recent track may only be rendered if the current backend already exposes an
authorized authoritative track/history endpoint.

If no suitable endpoint exists:

Phase 2 must ship latest-location marker only.

Do not invent a local track from Family polling snapshots.

### FR-MAP-009 Polling

Reuse the existing polling-first mechanism.

Polling must:

- prevent overlapping requests;
- pause/reduce while the page is hidden according to existing architecture;
- refetch backend authoritative state.

### FR-MAP-010 REAL / DEMO

REAL:
backend locations only.

DEMO:
existing simulator/mock map behavior only.

REAL failure must never fall back to Demo coordinates.

## 7. Privacy

Do not:

- log coordinates;
- persist map coordinates in browser storage;
- place coordinates in URL query parameters;
- send them to AI endpoints.

GCJ-02 presentation coordinates remain ephemeral in browser memory.

## 8. Acceptance Criteria

AC-MAP-001:
Family receives backend WGS84 latest_location
→ converts to GCJ-02
→ renders exactly one Elder marker.

AC-MAP-002:
No Location
→ no fake marker.

AC-MAP-003:
Backend unavailable
→ unavailable presentation, not SAFE/Mock.

AC-MAP-004:
AMap conversion failure
→ map unavailable/degraded, backend Safety state remains independent.

AC-MAP-005:
REAL code never renders Demo coordinates.

AC-MAP-006:
Backend WGS84 object remains unchanged after rendering conversion.

AC-MAP-007:
Recent track, if implemented, uses ordered backend Location records only.

## 9. Definition of Done

REAL Location Phase 2 is complete when:

Real device
→ backend WGS84 Location
→ Family backend read
→ presentation conversion
→ AMap marker

works end-to-end without:

- CRS mixing;
- fake markers;
- local Safety decisions;
- Mock fallback.
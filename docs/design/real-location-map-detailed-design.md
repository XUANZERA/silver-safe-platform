# REAL Location Map Presentation Phase 2 — Detailed Design

Status: Draft for Review

## 1. Pre-implementation Inspection

Before coding, inspect actual repository contracts:

- Safety View latest_location schema;
- Location history/track endpoint, if any;
- Family current polling implementation;
- Operator current map/dashboard implementation;
- MapCanvas props/contracts;
- AMap SDK initialization and current coordinate assumptions.

Do not assume a track endpoint exists.

## 2. Proposed Frontend Components

Prefer minimal additions such as:

frontend/src/services/map/
    amapCoordinateAdapter.js
    mapLocationMapper.js

Existing MapCanvas should be reused where practical.

Do not build a new map framework.

## 3. Canonical Input

Only accept authoritative backend locations explicitly identified as WGS84.

Conceptual validator:

isCanonicalLocation(location)

must verify:

- finite latitude;
- finite longitude;
- valid range;
- source_crs === "WGS84";
- valid recorded_at where required.

Unknown/missing CRS:

fail closed.

## 4. AMapCoordinateAdapter

Conceptual interface:

convertCanonicalLocation(location)
→ Promise<MapPoint>

Input:
WGS84

Output:
GCJ-02

Implementation must use the verified AMap/platform conversion mechanism.

Do not implement an undocumented home-grown conversion formula unless separately
reviewed and accepted.

Do not silently return the WGS84 coordinate if conversion fails.

## 5. Conversion Result

MapPoint:

{
  longitude,
  latitude,
  displayCrs: "GCJ-02"
}

MapPoint is presentation-only.

It must not be written to:

- Pinia persistent state;
- localStorage;
- sessionStorage;
- backend;
- Demo cache.

## 6. Latest Marker Flow

poll backend
→ latest_location
→ validate WGS84
→ convert
→ update display MapPoint
→ MapCanvas marker

A newer backend Location supersedes the old marker only after successful conversion.

If conversion fails:

show degraded map state.

Do not claim the new Location has been displayed.

## 7. Staleness

Map freshness must use backend timestamp information.

The map layer must not invent its own Safety freshness threshold.

If Safety View already exposes location_health:

reuse its authoritative meaning.

Map copy can show recorded timestamp without changing RiskStatus.

## 8. Track Flow

Only when existing backend track/history is verified:

GET authoritative ordered locations
→ filter/validate WGS84 contract
→ convert in chronological order
→ AMap Polyline

Do not construct a "track" from repeated Family polling responses.

## 9. MapCanvas Contract

Prefer MapCanvas receiving display-ready GCJ-02 points.

Example conceptual props:

latestPoint
trackPoints
locationState

MapCanvas should not perform:

backend API calls
Safety calculations
CRS guessing
Demo/REAL mode selection

## 10. Polling

Reuse existing polling controller.

Family:

poll backend Safety/location
→ presentation mapper
→ map

Operator:

only integrate where current dashboard already has an appropriate Elder/location context.

Do not add a new Operator Trip system in this phase.

## 11. Race Handling

If polling response A begins conversion,
then newer response B arrives:

the UI must not allow late completion of A
to overwrite B.

Use request/generation ordering.

Expected:

A old Location
B new Location
B becomes authoritative
late A conversion resolves
→ discard A result

## 12. AMap Lifecycle

Component unmount:

- destroy map/listeners according to existing MapCanvas lifecycle;
- invalidate pending conversion callbacks where practical.

No stale marker update after unmount.

## 13. Error Presentation

NO_LOCATION:
“暂无可用定位数据”

DATA_UNAVAILABLE:
“暂时无法获取最新位置”

MAP_CONVERSION_FAILED:
“位置暂时无法在地图中显示”

MAP_UNAVAILABLE:
“地图暂时无法加载”

Do not display:

“老人安全”
unless backend Risk says so in a separate Safety component.

## 14. Required Tests

MAP-001 canonical WGS84 accepted
MAP-002 missing/unknown CRS rejected
MAP-003 invalid coordinates rejected
MAP-004 conversion invoked before AMap rendering
MAP-005 conversion failure does not identity-fallback
MAP-006 backend canonical object not mutated
MAP-007 latest marker uses newest backend Location
MAP-008 old async conversion cannot overwrite newer Location
MAP-009 no Location → no marker
MAP-010 backend unavailable → no Mock fallback
MAP-011 REAL never consumes Demo coordinates
MAP-012 Demo behavior unchanged
MAP-013 Map failure does not change Safety state
MAP-014 recorded_at presentation preserved
MAP-015 track order preserved, if track implemented
MAP-016 Family authorization/backend endpoint remains authoritative

## 15. Manual Acceptance

Using a real Phase-1 Location:

Elder device
→ upload Location
→ Family page polling
→ backend latest_location
→ map conversion
→ marker near actual physical location

Verify:

- marker visually matches real position;
- refresh produces no fake jump to old Demo marker;
- no-data produces no default marker;
- backend failure produces unavailable state;
- backend WGS84 values remain unchanged.

## 16. Out of Scope

No:

background tracking
navigation
route deviation
WebSocket
WeChat implementation
persistent browser coordinate cache
new Risk rules
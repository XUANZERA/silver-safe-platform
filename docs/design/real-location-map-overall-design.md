# REAL Location Map Presentation Phase 2 — Overall Design

Status: Draft for Review

## 1. Objective

Visualize authoritative backend Location data on AMap without allowing
map-vendor coordinate requirements to enter the backend domain.

## 2. Architecture

Backend
  |
  | WGS84
  v
Safety View / Location API
  |
  v
Family / Operator polling
  |
  v
CanonicalLocation
  | WGS84
  v
AMapCoordinateAdapter
  |
  | GCJ-02
  v
Map Presentation Model
  |
  v
MapCanvas / AMap

Backend canonical data remains WGS84.

AMap-specific GCJ-02 exists only in the presentation layer.

## 3. Component Responsibilities

### Backend APIs

Provide authoritative:

- latest Location;
- recorded_at;
- Safety state;
- recent track only when already supported.

No GCJ-02 response field is required.

### Polling Layer

Uses existing polling infrastructure.

Responsibilities:

- fetch backend state;
- prevent overlap;
- update authoritative frontend read model.

### AMapCoordinateAdapter

Responsibilities:

WGS84
→ validated conversion
→ GCJ-02 MapPoint

It must not:

- mutate backend Location;
- cache coordinates persistently;
- calculate Risk;
- fallback to identity conversion.

### MapCanvas

MapCanvas renders display coordinates.

It should not decide:

- backend CRS;
- Risk;
- Alert state;
- location freshness.

## 4. Data Types

CanonicalLocation:

{
  latitude,
  longitude,
  recordedAt,
  sourceCrs: "WGS84"
}

MapPoint:

{
  latitude,
  longitude,
  displayCrs: "GCJ-02"
}

These types are conceptually distinct.

## 5. Coordinate Flow

Backend WGS84
→ validate source CRS
→ copy/adapter input
→ WGS84-to-GCJ02 conversion
→ AMap marker/polyline

Never:

Backend WGS84
→ AMap directly

Never:

converted GCJ-02
→ backend persistence

## 6. Failure States

Backend error:
DATA_UNAVAILABLE

No Location:
NO_LOCATION

Coordinate conversion failure:
MAP_CONVERSION_FAILED

AMap SDK failure:
MAP_UNAVAILABLE

These states must not overwrite backend RiskStatus.

## 7. Recent Track

If existing backend support is verified:

ordered canonical WGS84 locations
→ batch/individual conversion
→ GCJ-02 path
→ AMap Polyline

If no authoritative track endpoint exists:

do not add a backend API automatically;
deliver latest marker only.

## 8. REAL / DEMO Isolation

REAL map data source:
backend only.

DEMO map data source:
existing mock/simulator.

No fallback across this boundary.

## 9. Security

Family and Operator access continues to rely on existing backend authorization.

Frontend must not expand access by querying arbitrary elder IDs.

## 10. Phase Completion

The phase succeeds when backend WGS84 Location can be shown accurately on AMap
while Risk/Safety remains backend-authoritative and independent of map rendering.
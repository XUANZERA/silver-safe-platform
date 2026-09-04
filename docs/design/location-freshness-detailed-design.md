# Location Freshness Warning Phase 3 — Detailed Design

Status: Draft for Implementation

## 1. Preflight Inspection

Before implementation inspect actual:

backend/app/core/config.py
backend/app/schemas/safety.py
backend/app/services/safety.py
backend/app/services/locations.py
backend/app/models/location.py

frontend/src/views/child/ChildHome.vue
frontend/src/views/operator/EldersPanel.vue
frontend/src/services/safetyPresentation.js
frontend polling implementation

Do not assume current FRESHNESS_TBD behavior.

Report the existing implementation first.

## 2. Backend Configuration

Add a setting following existing config conventions:

location_stale_after_seconds

Environment form:

LOCATION_STALE_AFTER_SECONDS

Recommended default:

60

Validation:

> 0

Do not expose this as a frontend VITE variable.

## 3. Canonical Latest Location

Only Location rows satisfying the current canonical contract may participate:

source_crs == WGS84

Legacy NULL CRS rows remain excluded.

Reuse the existing latest-location query.

Do not create a second competing query implementation.

## 4. Calculation

Use timezone-aware UTC datetimes.

Conceptual:

calculated_at = utc_now()

latest = canonical latest location

if latest is None:
    location_health = NO_DATA
else:
    age_seconds = max(
        0,
        (calculated_at - latest.recorded_at).total_seconds()
    )

    if age_seconds > threshold:
        location_health = STALE
    else:
        location_health =
            existing accuracy classification / FRESH

Do not compare naive and aware datetime values.

## 5. Threshold Boundary

Define exactly:

age <= threshold
→ not stale

age > threshold
→ stale

Tests must cover:

threshold - 1
threshold
threshold + 1

## 6. Existing Accuracy Rule

Inspect current accuracy classification.

Do not delete it.

Required precedence:

1. NO_DATA
2. STALE
3. existing INACCURATE rule
4. FRESH

unless current repository behavior proves a stronger existing domain contract.

If a conflict exists, stop and report it before changing semantics.

## 7. Safety View

Keep current response structure whenever possible.

Expected relevant fields:

location_health
latest_location
calculated_at

Do not create a new SafetyState table.

Do not add persistent stale state.

Safety GET must not modify Trip, Location, Alert, Geofence, or Risk business state.
The existing deduplicated `safety.read` AuditLog remains an allowed privacy/security
side effect after an authorized successful read. Failed or unauthorized reads must
not record a successful `safety.read` audit.

## 8. RiskStatus

Do not create a new RiskStatus enum.

Existing:

SAFE
PENDING
ALERT

remains unchanged.

Presentation must ensure:

location_health=STALE

does not appear to users as “current location confirmed safe”.

Do not mutate RiskStatus simply to implement stale presentation unless existing ADR requires it.

## 9. Family UI

Use backend:

safetyView.location_health

No frontend threshold.

Recommended mapping:

NO_DATA
→ 暂无定位数据

FRESH
→ 定位正常

STALE
→ 定位较久未更新

INACCURATE
→ 定位精度不足

For STALE show:

最新记录位置
最后定位：<recorded_at>

Map marker may remain visible.

Use non-success visual treatment.

## 10. Operator UI

When selected Elder Safety View returns:

location_health=STALE

show:

“定位较久未更新”

and latest recorded time.

Do not create an Alert item.

Do not add Accept / Resolve controls.

## 11. Polling

Reuse existing polling.

Each poll obtains a newly derived Safety View.

No setInterval solely for local stale calculation.

No duplicate polling controller.

## 12. Recovery

Scenario:

T0:
Location received

T0 + threshold + 1:
Safety request
→ STALE

T1:
new Location received

next Safety request:
→ FRESH

No reset endpoint.

## 13. Required Backend Tests

FRESH-001
no canonical location → NO_DATA

FRESH-002
age threshold-1 → FRESH

FRESH-003
age exactly threshold → FRESH

FRESH-004
age threshold+1 → STALE

FRESH-005
legacy NULL CRS ignored

FRESH-006
STALE does not modify Trip, Location, or Alert and does not create persistent stale
business state; the existing deduplicated `safety.read` privacy/security audit is allowed

FRESH-007
new latest Location restores FRESH

FRESH-008
timezone-aware timestamps work

FRESH-009
slightly future timestamp does not produce negative-age failure

FRESH-010
existing INACCURATE behavior preserved

## 14. Required Frontend Tests

FRESH-FE-001
STALE → stale warning

FRESH-FE-002
NO_DATA → no-data message

FRESH-FE-003
FRESH → normal location copy

FRESH-FE-004
INACCURATE → existing inaccurate copy

FRESH-FE-005
STALE preserves latest recorded marker

FRESH-FE-006
STALE uses recordedAt wording, not current/real-time wording

FRESH-FE-007
map state failure remains independent

FRESH-FE-008
no frontend numeric stale threshold exists in business logic

Prefer runtime presentation tests over source regex.

## 15. Manual Demo Acceptance

1. Start an active Trip.
2. Enable location protection.
3. Confirm Family shows FRESH.
4. Disable Elder location protection.
5. Wait slightly longer than configured stale threshold.
6. Refresh/wait for Family polling.
7. Confirm Family shows:
   “定位较久未更新”
   and last recorded time.
8. Confirm no new Alert is created.
9. Re-enable Elder location.
10. Confirm next Family poll returns FRESH again.

## 16. Out of Scope

No stale Alert.
No scheduler.
No Redis.
No WebSocket.
No push notification.
No background positioning.

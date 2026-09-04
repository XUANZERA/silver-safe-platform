# Location Freshness Warning Phase 3 — Requirements

Status: Draft for Implementation

Depends on:
- Foreground Real Location Phase 1
- REAL Location Map Presentation Phase 2
- ADR-001 Backend Single Source of Truth
- ADR-004 Polling First
- ADR-006 Derived Safety View
- ADR-010 Coordinate System Contract

## 1. Background

The current REAL workflow supports:

Elder Device
→ Foreground Geolocation
→ WGS84 Location Upload
→ Backend Persistence
→ Risk Evaluation
→ Safety View
→ Family / Operator Map

However, a previously valid location can become old when:

- the Elder closes the page;
- browser geolocation stops;
- network connectivity is lost;
- Location upload fails for an extended period.

Displaying an old coordinate without clearly communicating its age may cause Family or Operator users to interpret stale data as the Elder's current position.

Phase 3 introduces an authoritative Location Freshness Warning.

## 2. Goal

The backend shall derive whether the latest authoritative Location is still fresh.

Target flow:

latest canonical Location
→ recorded_at
→ backend current time
→ freshness calculation
→ Safety View.location_health
→ Family / Operator presentation

The frontend must not independently invent a stale threshold.

## 3. Scope

IN SCOPE:

- Backend configurable freshness threshold.
- Authoritative STALE determination.
- Safety View location_health.
- Family stale-location warning.
- Operator stale-location warning where current location context exists.
- Recorded-time presentation.
- Polling-based recovery.
- Automated tests.
- REAL / DEMO isolation.

OUT OF SCOPE:

- Persistent LOCATION_STALE Alert.
- Operator Accept / Resolve for stale state.
- Scheduler / cron / background worker.
- WebSocket.
- Redis.
- SMS / phone notification.
- Push notification.
- Background browser geolocation.
- Route deviation.
- Fall detection.
- Battery monitoring.
- New map CRS behavior.

## 4. Business Rule

### FR-FRESH-001 Backend Authority

Location freshness shall be calculated by the backend.

Frontend must not contain an independent hardcoded freshness threshold.

### FR-FRESH-002 Threshold

The threshold shall be configurable by the backend.

Proposed configuration:

LOCATION_STALE_AFTER_SECONDS

Recommended MVP default:

60 seconds.

The implementation must first inspect the existing backend configuration system.

Do not duplicate this value across frontend files.

### FR-FRESH-003 NO_DATA

If no valid canonical Location exists:

location_health = NO_DATA

The UI shall show:

“暂无定位数据”

It must not show SAFE based on missing location information.

### FR-FRESH-004 FRESH

Given a valid canonical Location:

age = calculated_at - recorded_at

If:

age <= LOCATION_STALE_AFTER_SECONDS

the Location is fresh, subject to the existing accuracy rule.

### FR-FRESH-005 STALE

If:

age > LOCATION_STALE_AFTER_SECONDS

then:

location_health = STALE

The UI must clearly communicate:

“定位较久未更新”

and show the last recorded time.

### FR-FRESH-006 Accuracy Independence

Existing accuracy semantics must remain independent.

If the existing project already defines INACCURATE behavior, Phase 3 shall preserve it.

Recommended precedence:

NO_DATA
→ STALE
→ existing INACCURATE rule
→ FRESH

STALE has higher presentation priority than accuracy because an old location should not be described as current even if the old GPS sample was accurate.

### FR-FRESH-007 Safety Separation

STALE is not equivalent to:

ALERT

and must not create an Alert in Phase 3.

It is also not proof of:

SAFE.

Location freshness and RiskStatus remain separate concepts.

### FR-FRESH-008 Map Truthfulness

When location_health = STALE:

the latest recorded marker may remain visible for historical context.

However it must be labeled as:

“最新记录位置”

and must display its recorded time / stale warning.

It must never be labeled:

“实时位置”
or
“当前位置”.

### FR-FRESH-009 Recovery

If a new valid Location arrives:

STALE
→ FRESH

on the next authoritative Safety View calculation.

No manual reset is required.

### FR-FRESH-010 Polling

Reuse existing polling-first architecture.

Do not introduce WebSocket or background frontend timers solely for freshness calculation.

The backend response remains authoritative.

## 5. Edge Cases

### Clock Skew

A Location timestamp slightly in the future must not produce a negative age.

Conceptually:

age = max(0, calculated_at - recorded_at)

Do not silently accept extreme future timestamps if existing backend validation already rejects them.

### Backend unavailable

Backend failure must remain:

DATA_UNAVAILABLE

not:

STALE.

### Legacy CRS

Legacy Location with unknown/null CRS must continue to be excluded from authoritative freshness calculation.

## 6. UI Requirements

Family:

FRESH:
“定位正常”

STALE:
“定位较久未更新”

NO_DATA:
“暂无定位数据”

INACCURATE:
retain existing accurate wording.

For STALE, show:

“最后定位：HH:mm:ss”

and an amber/non-success presentation.

Operator Elder detail:

show the same authoritative location_health and recorded timestamp.

Do not create a fake Alert card.

## 7. Acceptance Criteria

AC-FRESH-001:
No canonical location
→ NO_DATA.

AC-FRESH-002:
Location age below/equal threshold
→ FRESH, subject to existing accuracy logic.

AC-FRESH-003:
Location age above threshold
→ STALE.

AC-FRESH-004:
STALE location does not create an Alert.

AC-FRESH-005:
New valid location restores FRESH.

AC-FRESH-006:
Frontend has no independent stale threshold.

AC-FRESH-007:
STALE marker may remain visible but is explicitly identified as latest recorded location.

AC-FRESH-008:
Backend unavailable is not reported as STALE.

## 8. Definition of Done

Phase 3 is complete when:

Elder location upload stops
→ enough time passes
→ Family polls Safety View
→ backend returns location_health=STALE
→ Family clearly shows stale warning and last recorded time
→ no fake SAFE
→ no persistent Alert is created

and:

new Location upload
→ next Safety View
→ location_health returns to FRESH.

# Location Freshness Warning Phase 3 — Overall Design

Status: Draft for Implementation

## 1. Objective

Introduce backend-authoritative location freshness without adding a background processing system.

## 2. Architecture

Latest canonical WGS84 Location
          |
          | recorded_at
          v
Backend Safety View
          |
          | current UTC time
          | freshness threshold
          v
LocationHealth Derivation
          |
     +----+-----+-----------+
     |          |           |
   NO_DATA    FRESH       STALE
                            |
                            v
                    Family / Operator
                       presentation

RiskStatus and AlertStatus remain separate.

## 3. Backend Authority

Freshness shall be calculated in the existing Safety View derivation path.

Frontend receives:

location_health
latest_location
calculated_at

and only renders the result.

No frontend:

Date.now() - recorded_at > 60000

business rule shall exist.

## 4. Configuration

Use the existing backend settings/config system.

Conceptual setting:

LOCATION_STALE_AFTER_SECONDS = 60

Expose it only inside backend business logic.

No new database table is required.

No migration is required.

## 5. Freshness Derivation

Conceptually:

latest = latest canonical WGS84 Location

if latest is None:
    NO_DATA

ageSeconds =
    max(0, calculatedAt - latest.recordedAt)

if ageSeconds > staleThreshold:
    STALE

else:
    apply existing accuracy classification

The implementation must inspect existing Safety logic before changing precedence.

## 6. Safety / Alert Separation

This phase does not create:

LOCATION_STALE Alert

because a stale condition can occur without any new Location request, and reliable event generation would require a scheduler/background execution model.

That is intentionally deferred.

Phase 3 therefore provides:

derived monitoring state

rather than:

persistent workflow event.

## 7. Family Presentation

Family polling:

GET Safety View
→ location_health
→ presentation state
→ existing MapCanvas

For STALE:

- keep latest recorded marker if available;
- show stale warning;
- show recorded time;
- do not visually imply current/real-time location.

## 8. Operator Presentation

Existing Operator Elder detail may consume the same Safety View.

Do not add a new Operator polling subsystem if one is unnecessary.

When an Elder is selected:

Safety View
→ location_health
→ location freshness text.

## 9. Recovery

No explicit state transition persistence exists.

Each Safety View request derives freshness again:

old location
→ STALE

new upload
→ latest changes
→ next derivation
→ FRESH

## 10. Infrastructure

No:

- worker;
- cron;
- queue;
- Redis;
- WebSocket;
- migration.

This keeps the current modular-monolith + polling-first architecture.

## 11. Failure Boundaries

Backend unavailable:
DATA_UNAVAILABLE

No canonical Location:
NO_DATA

Old canonical Location:
STALE

Poor accuracy:
INACCURATE

These states must remain distinguishable.

## 12. Phase Completion

Phase 3 is complete when stale location is visible to Family and Operator using authoritative backend-derived state, while existing Risk and Alert contracts remain unchanged.
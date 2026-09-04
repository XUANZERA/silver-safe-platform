import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

test('REAL logout wiring calls the remote revocation before clearing local session', () => {
  const dashboard = source('../src/views/operator/OperatorDashboard.vue')
  assert.match(dashboard, /logoutRemote:\s*logoutRequest/)
  assert.match(dashboard, /clearLocal:\s*userStore\.logout/)
})

test('REAL elder and family views sanitize backend destinations at their UI boundary', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  const childHome = source('../src/views/child/ChildHome.vue')
  assert.match(elderHome, /destination:\s*realDestinationOrPlaceholder\(trip, ''\)/)
  assert.match(elderHome, /realDestinationOrPlaceholder\(currentTrip\)/)
  assert.doesNotMatch(elderHome, /destination:\s*trip\.destination/)
  assert.match(childHome, /destination:\s*realDestinationOrPlaceholder\(trip\)/)
})

test('REAL demo-only routing delegates directly to the shared role-aware redirect', () => {
  const router = source('../src/router/index.js')
  assert.match(router, /demoOnlyRedirect\(isApiConfigured\(\), userStore\.isLoggedIn/)
  assert.doesNotMatch(router, /demoOnly\s*&&\s*isApiConfigured\(\)\) return '\/elder'/)
})

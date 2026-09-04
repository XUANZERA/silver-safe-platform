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
  assert.match(elderHome, /elder\.destination\s*=\s*realDestinationOrPlaceholder\(trip, ''\)/)
  assert.match(elderHome, /realDestinationOrPlaceholder\(currentTrip\)/)
  assert.doesNotMatch(elderHome, /destination:\s*trip\.destination/)
  assert.match(childHome, /destination:\s*realDestinationOrPlaceholder\(trip\)/)
})

test('REAL demo-only routing delegates directly to the shared role-aware redirect', () => {
  const router = source('../src/router/index.js')
  assert.match(router, /demoOnlyRedirect\(isApiConfigured\(\), userStore\.isLoggedIn/)
  assert.doesNotMatch(router, /demoOnly\s*&&\s*isApiConfigured\(\)\) return '\/elder'/)
})

test('REAL Trip create/start UI is wired to authoritative refresh without POST response truth', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  assert.match(elderHome, /async function loadCurrentTrip\(\)/)
  assert.match(elderHome, /createTrip:\s*\(destination\) => tripApi\.create\(destination\)/)
  assert.match(elderHome, /startTrip:\s*\(tripId\) => tripApi\.start\(tripId\)/)
  assert.match(elderHome, /refreshTrip:\s*loadCurrentTrip/g)
  assert.match(elderHome, /行程请求结果暂时无法确认/)
  assert.match(elderHome, />刷新行程状态</)
  assert.match(elderHome, /v-model="destinationInput"[^>]*maxlength="200"/)
  assert.doesNotMatch(elderHome, /destinationInput\s*=\s*ref\('(天坛|广州塔|永庆坊)/)
  assert.doesNotMatch(elderHome, /currentTrip\.value\s*=\s*(createdTrip|startedTrip|result\.value)/)
})

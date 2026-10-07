import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { createElderApi } from '../src/services/api.js'
import {
  createSingleFlightAction,
  saveGeofenceForMode
} from '../src/services/geofenceConfiguration.js'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

test('REAL family geofence API sends PUT with radius and enabled only', async () => {
  const calls = []
  const elderApi = createElderApi(async (...args) => {
    calls.push(args)
    return { elder_id: 12, radius_meters: 100, enabled: true, crs: 'WGS84' }
  })
  const update = () => elderApi.updateGeofence(12, {
    radius_meters: 100,
    enabled: true,
    center_latitude: 23.1,
    center_longitude: 113.2
  })
  const refreshed = { elder_id: 12, radius_meters: 100, enabled: true, crs: 'WGS84' }

  let refreshes = 0
  const result = await saveGeofenceForMode({
    realMode: true,
    update,
    refresh: async () => { refreshes += 1; return refreshed }
  })

  assert.equal(result.status, 'CONFIRMED')
  assert.deepEqual(result.geofence, { elder_id: 12, radius_meters: 100, enabled: true, crs: 'WGS84' })
  assert.equal(refreshes, 1)
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], '/elders/12/geofence')
  assert.equal(calls[0][1].method, 'PUT')
  assert.deepEqual(JSON.parse(calls[0][1].body), { radius_meters: 100, enabled: true })
  assert.equal('center_latitude' in JSON.parse(calls[0][1].body), false)
  assert.equal('center_longitude' in JSON.parse(calls[0][1].body), false)
})

test('successful geofence PUT is followed by authoritative refresh', async () => {
  const calls = []
  const result = await saveGeofenceForMode({
    realMode: true,
    update: async () => { calls.push('put') },
    refresh: async () => { calls.push('get'); return { radius_meters: 100 } }
  })
  assert.deepEqual(calls, ['put', 'get'])
  assert.equal(result.status, 'CONFIRMED')
})

test('failed geofence PUT rejects before refresh or success can be reported', async () => {
  let refreshes = 0
  await assert.rejects(
    saveGeofenceForMode({
      realMode: true,
      update: async () => { throw new Error('LOCATION_STALE') },
      refresh: async () => { refreshes += 1 }
    }),
    /LOCATION_STALE/
  )
  assert.equal(refreshes, 0)

  const childHome = source('../src/views/child/ChildHome.vue')
  assert.match(childHome, /catch \(error\) \{[\s\S]*geofenceSyncStatus\.value = 'WRITE_FAILED'/)
  assert.match(childHome, /if \(result\.status === 'CONFIRMED'\)[\s\S]*showSuccessToast\(/)
  assert.match(childHome, /SAVED_REFRESH_FAILED[\s\S]*围栏已保存，但状态刷新失败/)
  assert.match(childHome, /v-if="geofenceNeedsConfirmation"[\s\S]*@click="confirmSavedGeofenceState"/)
})

test('PUT success with failed refetch stays saved and reports refresh unconfirmed', async () => {
  let localGeofence = null
  const result = await saveGeofenceForMode({
    realMode: true,
    update: async () => ({ elder_id: 5, radius_meters: 100, enabled: true, crs: 'WGS84' }),
    onSaved: (value) => { localGeofence = value },
    refresh: async () => { throw new Error('network down') }
  })

  assert.equal(result.status, 'SAVED_REFRESH_FAILED')
  assert.equal(localGeofence, result.geofence)
  assert.match(result.error.message, /network down/)
})

test('superseded authoritative refetch is not reported as a write failure', async () => {
  const result = await saveGeofenceForMode({
    realMode: true,
    update: async () => ({ elder_id: 5, radius_meters: 100, enabled: true }),
    refresh: async () => false
  })
  assert.equal(result.status, 'SAVED_REFRESH_UNCONFIRMED')

  let refreshed = false
  const noLongerCurrent = await saveGeofenceForMode({
    realMode: true,
    update: async () => ({ elder_id: 5 }),
    isCurrent: () => false,
    refresh: async () => { refreshed = true }
  })
  assert.equal(noLongerCurrent.status, 'SAVED_REFRESH_UNCONFIRMED')
  assert.equal(refreshed, false)
})

test('stale Elder A save response cannot replace Elder B geofence state', async () => {
  let activeElderId = 22
  let localGeofence = { elder_id: 22, radius_meters: 250, enabled: true, crs: 'WGS84' }
  const result = await saveGeofenceForMode({
    realMode: true,
    update: async () => ({ elder_id: 11, radius_meters: 100, enabled: true, crs: 'WGS84' }),
    isCurrent: () => activeElderId === 11,
    onSaved: (value) => { localGeofence = value },
    refresh: async () => { activeElderId = 22; return false }
  })

  assert.equal(result.status, 'SAVED_REFRESH_UNCONFIRMED')
  assert.deepEqual(localGeofence, { elder_id: 22, radius_meters: 250, enabled: true, crs: 'WGS84' })
})

test('confirmation pending single-flight guard allows only one geofence PUT', async () => {
  const runAction = createSingleFlightAction()
  let releaseConfirmation
  let putCount = 0
  const confirmation = new Promise((resolve) => { releaseConfirmation = resolve })
  const first = runAction(async () => {
    await confirmation
    return saveGeofenceForMode({
      realMode: true,
      update: async () => { putCount += 1; return { elder_id: 12 } },
      refresh: async () => true
    })
  })
  const duplicate = await runAction(async () => {
    putCount += 1
    return { status: 'CONFIRMED' }
  })

  assert.equal(duplicate.status, 'IGNORED_DUPLICATE')
  releaseConfirmation()
  assert.equal((await first).status, 'CONFIRMED')
  assert.equal(putCount, 1)

  const childHome = source('../src/views/child/ChildHome.vue')
  assert.match(childHome, /const runGeofenceAction = createSingleFlightAction\(\)/)
  assert.match(childHome, /return runGeofenceAction\(async \(\) => \{[\s\S]*showConfirmDialog/)
})

test('DEMO geofence action never calls backend callbacks', async () => {
  let calls = 0
  const result = await saveGeofenceForMode({
    realMode: false,
    update: async () => { calls += 1 },
    refresh: async () => { calls += 1 }
  })
  assert.deepEqual(result, { skipped: true })
  assert.equal(calls, 0)

  const childHome = source('../src/views/child/ChildHome.vue')
  assert.match(childHome, /if \(!realMode \|\| !elder\.id\) return/)
  assert.match(childHome, /<section v-if="realMode" class="geofence-settings">/)
  assert.match(childHome, /elderApi\.geofence\(currentElder\.id\)/)
})

test('REAL and DEMO geofence modes remain isolated', async () => {
  const calls = []
  await saveGeofenceForMode({
    realMode: false,
    update: async () => calls.push('demo-put'),
    refresh: async () => calls.push('demo-get')
  })
  await saveGeofenceForMode({
    realMode: true,
    update: async () => calls.push('real-put'),
    refresh: async () => { calls.push('real-get'); return true }
  })
  assert.deepEqual(calls, ['real-put', 'real-get'])
})

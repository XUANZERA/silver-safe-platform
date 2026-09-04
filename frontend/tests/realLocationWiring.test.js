import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

test('LOC UI is shown only for a REAL authoritative active Trip', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  assert.match(elderHome, /realMode\s*&&\s*tripDataAvailable\.value\s*&&\s*currentTrip\.value\?\.status === 'active'/)
  assert.match(elderHome, /v-if="showRealLocationControl"/)
  assert.match(elderHome, /@click="toggleRealLocation"/)
})

test('LOC UI contains the required truthful technical states and foreground notice', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  for (const copy of [
    '未开启',
    '等待定位授权',
    '请允许浏览器访问您的位置；若未看到提示，请点击地址栏左侧的定位图标。',
    '定位守护运行中',
    '定位暂不可用',
    '定位权限未开启',
    '请在浏览器的网站权限中允许定位后再试。',
    '当前浏览器不支持定位',
    '定位守护需要保持页面运行。'
  ]) {
    assert.match(elderHome, new RegExp(copy))
  }
  assert.doesNotMatch(elderHome, /当前安全|家属已看到位置|北斗已连接|后台持续定位/)
})

test('LOC-FE-012/013/014 Trip end, logout, and unmount all stop the lifecycle', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  const stopBeforeEnd = elderHome.indexOf('stopRealLocation()', elderHome.indexOf('async function toggleTrip'))
  const endRequest = elderHome.indexOf('await tripApi.end', stopBeforeEnd)
  assert.ok(stopBeforeEnd > 0 && endRequest > stopBeforeEnd)
  assert.match(elderHome, /watch\(\(\) => userStore\.isLoggedIn[\s\S]*if \(!isLoggedIn\) stopRealLocation\(\)/)
  assert.match(elderHome, /onUnmounted\(stopRealLocation\)/)
})

test('LOC reload is opt-in and REAL wiring never imports Demo providers', () => {
  const elderHome = source('../src/views/elder/ElderHome.vue')
  const mountedBody = elderHome.slice(elderHome.indexOf('onMounted('), elderHome.indexOf('watch('))
  assert.doesNotMatch(mountedBody, /locationProvider\.start|toggleRealLocation\(/)
  assert.doesNotMatch(elderHome, /locationSimulator|simulationLocation|MockLocationProvider/)
})

test('ADR-010 REAL mapper sends an explicit WGS84 contract without GCJ-02', async () => {
  const mapperModule = await import('../src/services/location/locationMapper.js')
  const payload = mapperModule.mapRealLocationSampleToPayload({
    tripId: 7,
    clientLocationId: 'h5:7:sample',
    sample: {
      latitude: 23.1291,
      longitude: 113.2644,
      accuracyMeters: 8,
      speedMps: null,
      recordedAt: '2026-09-04T06:00:00.000Z',
      source: 'h5',
      sourceCrs: 'WGS84'
    }
  })
  assert.deepEqual(payload, {
    client_location_id: 'h5:7:sample',
    latitude: 23.1291,
    longitude: 113.2644,
    speed_mps: null,
    accuracy_meters: 8,
    source: 'h5',
    source_crs: 'WGS84',
    recorded_at: '2026-09-04T06:00:00.000Z'
  })
  assert.throws(
    () => mapperModule.mapRealLocationSampleToPayload({
      tripId: 7,
      clientLocationId: 'h5:7:sample',
      sample: {
        latitude: 23.1291,
        longitude: 113.2644,
        accuracyMeters: 8,
        speedMps: null,
        recordedAt: '2026-09-04T06:00:00.000Z',
        source: 'h5',
        sourceCrs: 'wgs84'
      }
    }),
    /sourceCrs/
  )
  const mapperSource = source('../src/services/location/locationMapper.js')
  assert.doesNotMatch(mapperSource, /GCJ-?02/i)
})

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createDemoItinerary,
  demoOnlyRedirect,
  emergencyContactPresentation,
  homePathForRole,
  loadDemoItinerary,
  loginForMode,
  logoutForMode,
  presentElderPlan,
  presentRealSchedule,
  realDestinationOrPlaceholder,
  sessionMatchesMode,
  startTripForMode
} from '../src/services/modeBoundary.js'

test('MODE-001 real login failure creates no Demo session', async () => {
  const sessions = []
  await assert.rejects(
    loginForMode({
      realMode: true,
      username: 'elder01',
      password: 'demo123',
      login: async () => { throw new Error('Failed to fetch') },
      saveSession: (session) => sessions.push(session)
    }),
    /Failed to fetch/
  )
  assert.deepEqual(sessions, [])
})

test('MODE-002 explicit Demo login still uses the local Demo account', async () => {
  const sessions = []
  const session = await loginForMode({
    realMode: false,
    username: 'elder01',
    password: 'demo123',
    login: async () => { throw new Error('real login must not run') },
    saveSession: (value) => sessions.push(value)
  })
  assert.equal(session.mode, 'demo')
  assert.equal(session.path, '/elder')
  assert.deepEqual(sessions, [session])
  assert.equal(sessionMatchesMode(session, false), true)
  assert.equal(sessionMatchesMode(session, true), false)
})

test('MODE-003 logout revokes the REAL session and always clears local state', async () => {
  const calls = []
  await logoutForMode({
    realMode: true,
    logoutRemote: async () => { calls.push('remote') },
    clearLocal: () => { calls.push('local') }
  })
  assert.deepEqual(calls, ['remote', 'local'])

  calls.length = 0
  await logoutForMode({
    realMode: true,
    logoutRemote: async () => { calls.push('remote'); throw new Error('offline') },
    clearLocal: () => { calls.push('local') }
  })
  assert.deepEqual(calls, ['remote', 'local'])

  calls.length = 0
  await logoutForMode({
    realMode: false,
    logoutRemote: async () => { calls.push('remote') },
    clearLocal: () => { calls.push('local') }
  })
  assert.deepEqual(calls, ['local'])
})

test('MODE-004 REAL demo-only routes redirect directly for the current role', () => {
  assert.equal(demoOnlyRedirect(false, null), null)
  assert.equal(demoOnlyRedirect(true, null), '/login')
  assert.equal(demoOnlyRedirect(true, { role: 'elder' }), '/elder')
  assert.equal(demoOnlyRedirect(true, { role: 'family' }), '/child')
  assert.equal(demoOnlyRedirect(true, { role: 'operator' }), '/operator')
  assert.equal(homePathForRole('family'), '/child')
})

test('ELDER-REAL-001 real mode with no backend Trip has no TianTan plan', () => {
  const plan = presentElderPlan({ realMode: true, dataAvailable: true, trip: null })
  assert.equal(plan.title, '暂无进行中的真实行程')
  assert.doesNotMatch(JSON.stringify(plan), /天坛|慢游/)
})

test('ELDER-REAL-002 real plan destination comes only from backend Trip', () => {
  const plan = presentElderPlan({
    realMode: true,
    dataAvailable: true,
    trip: { id: 17, destination: '人民公园', status: 'active' }
  })
  assert.deepEqual(plan, { kind: 'ready', title: '人民公园' })
})

test('ELDER-REAL-003 placeholder destinations are never presented as business data', () => {
  const legacyTrip = { id: 19, destination: '暂无行程', status: 'active' }
  const plan = presentElderPlan({ realMode: true, dataAvailable: true, trip: legacyTrip })
  assert.equal(plan.kind, 'error')
  assert.equal(realDestinationOrPlaceholder(legacyTrip), '暂无真实行程')
  assert.equal(realDestinationOrPlaceholder(legacyTrip, ''), '')
  assert.doesNotMatch(JSON.stringify(plan), /待出发：暂无行程|正在前往：暂无行程/)
})

test('ELDER-DEMO-001 explicit Demo mode keeps TianTan content', () => {
  assert.equal(presentElderPlan({ realMode: false }).title, '天坛公园慢游')
  assert.match(JSON.stringify(createDemoItinerary()), /天坛公园慢游/)
})

test('SCHEDULE-REAL-001 real mode never reads Demo sessionStorage itinerary', () => {
  let reads = 0
  const storage = {
    getItem() { reads += 1; return JSON.stringify(createDemoItinerary()) },
    removeItem() {}
  }
  assert.equal(loadDemoItinerary(true, storage), null)
  assert.equal(reads, 0)
})

test('SCHEDULE-REAL-002 backend empty stays a neutral real empty state', () => {
  const state = presentRealSchedule({ trip: null })
  assert.equal(state.kind, 'empty')
  assert.equal(state.title, '暂无真实行程')
  assert.doesNotMatch(JSON.stringify(state), /天坛|演示/)
})

test('SCHEDULE-REAL-003 backend error stays unavailable without Demo fallback', () => {
  const state = presentRealSchedule({ error: '网络中断' })
  assert.equal(state.kind, 'error')
  assert.match(state.title, /数据不可用.*无法获取真实行程/)
  assert.doesNotMatch(JSON.stringify(state), /天坛|演示/)
})

test('TRIP-REAL-001 missing real destination never starts or creates a placeholder Trip', async () => {
  let starts = 0
  let demoStarts = 0
  await assert.rejects(
    startTripForMode({
      realMode: true,
      trip: { id: null, destination: '暂无行程' },
      startExisting: async () => { starts += 1 },
      startDemo: async () => { demoStarts += 1 }
    }),
    /请先设置真实目的地/
  )
  assert.equal(starts, 0)
  assert.equal(demoStarts, 0)
  assert.equal(
    presentRealSchedule({ trip: { id: 12, destination: '暂无行程', status: 'created' } }).kind,
    'error'
  )
})

test('EMERGENCY-002 contact action describes an information view, not a phone call', () => {
  const presentation = emergencyContactPresentation(true)
  assert.equal(presentation.label, '查看紧急联系信息')
  assert.match(presentation.message, /不会发起拨号/)
  assert.doesNotMatch(JSON.stringify(presentation), /138|110|120|tel:/)
})

import assert from 'node:assert/strict'
import test from 'node:test'

import { ApiError } from '../src/services/api.js'
import {
  CREATE_RESULT,
  CREATE_STATE,
  START_RESULT,
  canCreateRealTrip,
  createTripAndRefresh,
  isStartableTrip,
  isValidDestination,
  normalizeDestination,
  refreshUnknownCreation,
  startTripAndRefresh
} from '../src/services/tripCreation.js'

function deferred() {
  let resolve
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

function pendingState() {
  let pending = false
  return {
    isPending: () => pending,
    setPending: (value) => { pending = value }
  }
}

test('TC-TRIP-001 REAL with authoritative null exposes Create', () => {
  assert.equal(canCreateRealTrip({
    realMode: true,
    tripDataAvailable: true,
    currentTrip: null,
    createState: CREATE_STATE.READY
  }), true)
  assert.equal(canCreateRealTrip({
    realMode: true,
    tripDataAvailable: true,
    currentTrip: null,
    createState: CREATE_STATE.UNKNOWN
  }), false)
})

test('TC-TRIP-002 empty and spaces cause zero POST requests', async () => {
  for (const destination of ['', '   ']) {
    let posts = 0
    const result = await createTripAndRefresh({
      destination,
      ...pendingState(),
      createTrip: async () => { posts += 1 },
      refreshTrip: async () => null
    })
    assert.equal(result.type, CREATE_RESULT.INVALID)
    assert.equal(posts, 0)
  }
})

test('TC-TRIP-003 reserved sentinels cause zero frontend POST requests', async () => {
  for (const destination of ['暂无行程', ' 暂无真实行程 ']) {
    let posts = 0
    const result = await createTripAndRefresh({
      destination,
      ...pendingState(),
      createTrip: async () => { posts += 1 },
      refreshTrip: async () => null
    })
    assert.equal(result.type, CREATE_RESULT.INVALID)
    assert.equal(posts, 0)
  }
  assert.equal(isValidDestination('行'.repeat(200)), true)
  assert.equal(isValidDestination('行'.repeat(201)), false)
})

test('TC-TRIP-004 trims destination, POSTs once, and uses GET as final truth', async () => {
  const posts = []
  let gets = 0
  const backendTrip = { id: 8, destination: '广州塔', status: 'created' }
  const result = await createTripAndRefresh({
    destination: '  广州塔  ',
    ...pendingState(),
    createTrip: async (destination) => {
      posts.push(destination)
      return { id: 7, destination: 'ignored POST response', status: 'created' }
    },
    refreshTrip: async () => { gets += 1; return backendTrip }
  })

  assert.equal(normalizeDestination('  广州塔  '), '广州塔')
  assert.deepEqual(posts, ['广州塔'])
  assert.equal(gets, 1)
  assert.equal(result.type, CREATE_RESULT.CREATED)
  assert.equal(result.trip, backendTrip)
})

test('TC-TRIP-005 synchronous pending guard turns double Create into one POST', async () => {
  const gate = deferred()
  const state = pendingState()
  let posts = 0
  const options = {
    destination: '人民公园',
    ...state,
    createTrip: async () => { posts += 1; await gate.promise },
    refreshTrip: async () => ({ id: 9, destination: '人民公园', status: 'created' })
  }

  const first = createTripAndRefresh(options)
  const second = await createTripAndRefresh(options)
  assert.equal(second.type, CREATE_RESULT.PENDING)
  assert.equal(posts, 1)
  gate.resolve()
  assert.equal((await first).type, CREATE_RESULT.CREATED)
  assert.equal(posts, 1)
})

test('TC-TRIP-006 POST 500 reconciles once without repost or fake success', async () => {
  let posts = 0
  let gets = 0
  const result = await createTripAndRefresh({
    destination: '人民公园',
    ...pendingState(),
    createTrip: async () => {
      posts += 1
      throw new ApiError('server failed', { status: 500, code: 'SERVER_ERROR', hasResponse: true })
    },
    refreshTrip: async () => { gets += 1; return null }
  })

  assert.equal(result.type, CREATE_RESULT.UNKNOWN)
  assert.equal(posts, 1)
  assert.equal(gets, 1)
})

test('TC-TRIP-007 POST 409 reconciles and the backend existing Trip wins', async () => {
  const existing = { id: 10, destination: '越秀公园', status: 'active' }
  const result = await createTripAndRefresh({
    destination: '人民公园',
    ...pendingState(),
    createTrip: async () => {
      throw new ApiError('conflict', {
        status: 409,
        code: 'UNFINISHED_TRIP_EXISTS',
        hasResponse: true
      })
    },
    refreshTrip: async () => existing
  })

  assert.equal(result.type, CREATE_RESULT.RECONCILED)
  assert.equal(result.trip, existing)
})

test('TC-TRIP-008 created and active Trips hide Create', () => {
  for (const status of ['created', 'active']) {
    assert.equal(canCreateRealTrip({
      realMode: true,
      tripDataAvailable: true,
      currentTrip: { id: 11, destination: '人民公园', status },
      createState: CREATE_STATE.READY
    }), false)
  }
})

test('TC-TRIP-009 Start only accepts created Trip and double Start POSTs once', async () => {
  const gate = deferred()
  const state = pendingState()
  let posts = 0
  let gets = 0
  const created = { id: 12, destination: '人民公园', status: 'created' }
  const active = { ...created, destination: '后端目的地', status: 'active' }
  const options = {
    trip: created,
    ...state,
    startTrip: async () => { posts += 1; await gate.promise },
    refreshTrip: async () => { gets += 1; return active }
  }

  assert.equal(isStartableTrip(created), true)
  assert.equal(isStartableTrip({ ...created, status: 'active' }), false)
  assert.equal(isStartableTrip({ ...created, destination: '暂无行程' }), false)
  assert.equal((await startTripAndRefresh({ ...options, trip: { ...created, status: 'active' } })).type, START_RESULT.INVALID)

  const first = startTripAndRefresh(options)
  const second = await startTripAndRefresh(options)
  assert.equal(second.type, START_RESULT.PENDING)
  assert.equal(posts, 1)
  gate.resolve()
  const result = await first
  assert.equal(result.type, START_RESULT.CONFIRMED)
  assert.equal(result.trip, active)
  assert.equal(posts, 1)
  assert.equal(gets, 1)
})

test('TC-TRIP-009B Start 409 and network/5xx errors reconcile without a second POST', async () => {
  const created = { id: 21, destination: '人民公园', status: 'created' }
  const active = { ...created, status: 'active' }

  for (const error of [
    new ApiError('conflict', { status: 409, code: 'TRIP_ALREADY_STARTED', hasResponse: true }),
    new ApiError('offline', { hasResponse: false }),
    new ApiError('server failed', { status: 503, code: 'SERVER_ERROR', hasResponse: true })
  ]) {
    let posts = 0
    let gets = 0
    const result = await startTripAndRefresh({
      trip: created,
      ...pendingState(),
      startTrip: async () => { posts += 1; throw error },
      refreshTrip: async () => { gets += 1; return active }
    })

    assert.equal(result.type, START_RESULT.RECONCILED)
    assert.equal(result.trip, active)
    assert.equal(posts, 1)
    assert.equal(gets, 1)
  }
})

test('TC-TRIP-010 DEMO never exposes real Create', () => {
  assert.equal(canCreateRealTrip({
    realMode: false,
    tripDataAvailable: true,
    currentTrip: null,
    createState: CREATE_STATE.READY
  }), false)
})

test('TC-TRIP-011 POST success plus GET failure becomes CREATE_UNKNOWN', async () => {
  const result = await createTripAndRefresh({
    destination: '人民公园',
    ...pendingState(),
    createTrip: async () => ({ id: 13, destination: 'POST value', status: 'created' }),
    refreshTrip: async () => { throw new Error('GET failed') }
  })

  assert.equal(result.type, CREATE_RESULT.UNKNOWN)
})

test('TC-TRIP-012 network error plus GET null stays unknown without auto retry', async () => {
  let posts = 0
  const result = await createTripAndRefresh({
    destination: '人民公园',
    ...pendingState(),
    createTrip: async () => {
      posts += 1
      throw new ApiError('Failed to fetch', { hasResponse: false })
    },
    refreshTrip: async () => null
  })

  assert.equal(result.type, CREATE_RESULT.UNKNOWN)
  assert.equal(posts, 1)
})

test('TC-TRIP-013 manual refresh null returns CREATE_READY without POST', async () => {
  const result = await refreshUnknownCreation({
    ...pendingState(),
    refreshTrip: async () => null
  })
  assert.equal(result.type, CREATE_RESULT.READY)
})

test('TC-TRIP-014 GET destination B overrides POST response destination A', async () => {
  const getTrip = { id: 15, destination: '目的地 B', status: 'created' }
  const result = await createTripAndRefresh({
    destination: '目的地 A',
    ...pendingState(),
    createTrip: async () => ({ id: 14, destination: '目的地 A', status: 'created' }),
    refreshTrip: async () => getTrip
  })

  assert.equal(result.trip, getTrip)
  assert.equal(result.trip.destination, '目的地 B')
})

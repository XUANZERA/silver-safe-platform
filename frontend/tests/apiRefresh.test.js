import assert from 'node:assert/strict'
import test from 'node:test'

import { ApiError, createApiClient } from '../src/services/api.js'

function jsonResponse(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return payload }
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, reject, resolve }
}

test('AUTH-REFRESH-001 and 002 share one refresh and retry every original request', async () => {
  const refreshGate = deferred()
  const attempts = new Map()
  const retryTokens = []
  let refreshCalls = 0
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async (url, options) => {
      const path = new URL(url).pathname
      if (path === '/auth/refresh') {
        refreshCalls += 1
        await refreshGate.promise
        return jsonResponse(200, { data: { access_token: 'fresh-token', user: { id: 1 } } })
      }
      const count = (attempts.get(path) || 0) + 1
      attempts.set(path, count)
      if (count === 2) retryTokens.push(options.headers.Authorization)
      return count === 1
        ? jsonResponse(401, { error: { message: 'access token expired' } })
        : jsonResponse(200, { data: { path } })
    }
  })

  const pending = ['/one', '/two', '/three'].map((path) => client.request(path))
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(refreshCalls, 1)

  refreshGate.resolve()
  const results = await Promise.all(pending)

  assert.deepEqual(results, [{ path: '/one' }, { path: '/two' }, { path: '/three' }])
  assert.deepEqual([...attempts.values()], [2, 2, 2])
  assert.deepEqual(retryTokens, ['Bearer fresh-token', 'Bearer fresh-token', 'Bearer fresh-token'])
  assert.equal(refreshCalls, 1)
})

test('AUTH-REFRESH-003 shares one refresh failure across all waiting requests', async () => {
  const refreshGate = deferred()
  let refreshCalls = 0
  let resourceCalls = 0
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname
      if (path === '/auth/refresh') {
        refreshCalls += 1
        await refreshGate.promise
        return jsonResponse(401, { error: { message: 'refresh rejected' } })
      }
      resourceCalls += 1
      return jsonResponse(401, { error: { message: 'access token expired' } })
    }
  })

  const pending = ['/one', '/two', '/three'].map((path) => client.request(path))
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(refreshCalls, 1)

  refreshGate.resolve()
  const results = await Promise.allSettled(pending)

  assert.equal(refreshCalls, 1)
  assert.equal(resourceCalls, 3)
  assert.deepEqual(results.map((result) => result.status), ['rejected', 'rejected', 'rejected'])
  assert.deepEqual(results.map((result) => result.reason.message), [
    'access token expired',
    'access token expired',
    'access token expired'
  ])
})

test('AUTH-REFRESH-004 retries an original request only once', async () => {
  let refreshCalls = 0
  let resourceCalls = 0
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname
      if (path === '/auth/refresh') {
        refreshCalls += 1
        return jsonResponse(200, { data: { access_token: 'still-invalid', user: { id: 1 } } })
      }
      resourceCalls += 1
      return jsonResponse(401, { error: { message: 'still unauthorized' } })
    }
  })

  await assert.rejects(client.request('/protected'), /still unauthorized/)
  assert.equal(refreshCalls, 1)
  assert.equal(resourceCalls, 2)
})

test('AUTH-LOGOUT-001 calls backend logout and clears the access token even on failure', async () => {
  const calls = []
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async (url, options) => {
      const path = new URL(url).pathname
      calls.push({ path, authorization: options.headers.Authorization })
      if (path === '/auth/login') {
        return jsonResponse(200, { data: { access_token: 'operator-token', user: { id: 9 } } })
      }
      if (path === '/auth/logout') {
        return jsonResponse(503, { error: { message: 'backend unavailable' } })
      }
      return jsonResponse(200, { data: { ok: true } })
    }
  })

  await client.loginRequest('operator01', 'secret')
  await assert.rejects(client.logoutRequest(), /backend unavailable/)
  await client.request('/after-logout', {}, false)

  assert.deepEqual(calls, [
    { path: '/auth/login', authorization: undefined },
    { path: '/auth/logout', authorization: 'Bearer operator-token' },
    { path: '/after-logout', authorization: undefined }
  ])
})

test('API-ERROR-001 preserves HTTP status, backend code, message, and response presence', async (t) => {
  for (const status of [400, 403, 409, 422, 500]) {
    await t.test(String(status), async () => {
      const client = createApiClient({
        baseUrl: 'https://api.test',
        fetchImpl: async () => jsonResponse(status, {
          error: { code: `BACKEND_${status}`, message: `backend message ${status}` }
        })
      })

      await assert.rejects(
        client.request('/failure', {}, false),
        (error) => {
          assert.ok(error instanceof ApiError)
          assert.equal(error.message, `backend message ${status}`)
          assert.equal(error.status, status)
          assert.equal(error.code, `BACKEND_${status}`)
          assert.equal(error.hasResponse, true)
          return true
        }
      )
    })
  }
})

test('API-ERROR-002 reliably exposes a backend 409 conflict', async () => {
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async () => jsonResponse(409, {
      error: { code: 'UNFINISHED_TRIP_EXISTS', message: '当前已有未完成的出游任务' }
    })
  })

  await assert.rejects(
    client.request('/trips', { method: 'POST' }, false),
    (error) => error.status === 409 && error.code === 'UNFINISHED_TRIP_EXISTS'
  )
})

test('API-ERROR-003 wraps fetch rejection without claiming an HTTP response', async () => {
  const client = createApiClient({
    baseUrl: 'https://api.test',
    fetchImpl: async () => { throw new TypeError('Failed to fetch') }
  })

  await assert.rejects(
    client.request('/offline'),
    (error) => {
      assert.ok(error instanceof ApiError)
      assert.equal(error.message, 'Failed to fetch')
      assert.equal(error.status, null)
      assert.equal(error.code, null)
      assert.equal(error.hasResponse, false)
      return true
    }
  )
})

import assert from 'node:assert/strict'
import test from 'node:test'

import { createApiClient } from '../src/services/api.js'

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

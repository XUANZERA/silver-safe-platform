import assert from 'node:assert/strict'
import test from 'node:test'

import { createViteLaunch, REAL_API_BASE_URL } from '../scripts/start-vite.js'

test('dev:real pins the API base and IPv4 strict port regardless of shell values', () => {
  const launch = createViteLaunch('real', {
    VITE_API_BASE_URL: 'http://unexpected.example/api',
    DEBUG: 'release'
  })

  assert.equal(launch.env.VITE_API_BASE_URL, REAL_API_BASE_URL)
  assert.equal(launch.env.DEBUG, 'release')
  assert.deepEqual(launch.args, [
    '--mode', 'real', '--host', '127.0.0.1', '--port', '5173', '--strictPort'
  ])
})

test('dev:demo clears an inherited API base and uses the same IPv4 strict port', () => {
  const launch = createViteLaunch('demo', {
    VITE_API_BASE_URL: 'http://unexpected.example/api'
  })

  assert.equal(launch.env.VITE_API_BASE_URL, '')
  assert.equal(Boolean(launch.env.VITE_API_BASE_URL), false)
  assert.deepEqual(launch.args, [
    '--mode', 'demo', '--host', '127.0.0.1', '--port', '5173', '--strictPort'
  ])
})

test('dev launcher rejects modes outside real and demo', () => {
  assert.throws(() => createViteLaunch('staging'), /Unknown frontend mode/)
})

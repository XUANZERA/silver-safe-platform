'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { API_BASE_URL, resolveConfig, resolveEnvironment } = require('../config')

function wxForVersion(envVersion) {
  return {
    getAccountInfoSync() {
      return { miniProgram: { envVersion } }
    }
  }
}

test('development mini program uses the centralized localhost API URL', () => {
  const config = resolveConfig(wxForVersion('develop'))

  assert.equal(resolveEnvironment(wxForVersion('develop')), 'development')
  assert.equal(config.apiBaseUrl, API_BASE_URL.development)
  assert.match(config.apiBaseUrl, /^http:\/\/127\.0\.0\.1:/)
})

test('trial and release mini programs use the centralized testing HTTPS API URL', () => {
  for (const envVersion of ['trial', 'release']) {
    const config = resolveConfig(wxForVersion(envVersion))
    assert.equal(config.environment, 'testing')
    assert.equal(config.apiBaseUrl, API_BASE_URL.testing)
    assert.match(config.apiBaseUrl, /^https:\/\//)
  }
})

test('missing account information safely falls back to development', () => {
  assert.equal(resolveConfig(null).environment, 'development')
  assert.equal(resolveEnvironment({ getAccountInfoSync() { throw new Error('unsupported') } }), 'development')
})

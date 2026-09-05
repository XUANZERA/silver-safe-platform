'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { NETWORK_MESSAGE, userFacingError } = require('../services/userMessage')

test('network and server failures use the volunteer-facing network message', () => {
  assert.equal(userFacingError({ code: 'NETWORK_ERROR' }), NETWORK_MESSAGE)
  assert.equal(userFacingError({ status: 503 }), NETWORK_MESSAGE)
})

test('authentication failures use understandable messages', () => {
  assert.equal(
    userFacingError({ status: 401, code: 'INVALID_CREDENTIALS' }),
    '账号或密码错误，请重新输入'
  )
  assert.equal(userFacingError({ status: 401 }), '登录状态已失效，请重新登录')
})

test('unknown technical errors do not leak raw details', () => {
  assert.equal(userFacingError(new Error('internal debug details'), '安全信息加载失败'), '安全信息加载失败')
})

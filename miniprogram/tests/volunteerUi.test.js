'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

function pageMarkup(relativePath) {
  return fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8')
}

test('elder page hides development fields and offers feedback', () => {
  const markup = pageMarkup('pages/elder/index.wxml')

  assert.doesNotMatch(markup, /Backend|Active trip|行程 ID/)
  assert.match(markup, /今日任务/)
  assert.match(markup, /open-type="feedback"/)
})

test('family page uses user-facing labels and offers feedback', () => {
  const markup = pageMarkup('pages/family/map.wxml')

  assert.doesNotMatch(markup, /Backend|Safety View|location_health|recorded_at|WGS84/)
  assert.match(markup, /安全状态/)
  assert.match(markup, /更新时间/)
  assert.match(markup, /open-type="feedback"/)
})

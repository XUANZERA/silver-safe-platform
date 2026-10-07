import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { createPollingController } from '../src/services/polling.js'
import {
  presentAlertWorkflow,
  selectFamilyAlert
} from '../src/services/safetyPresentation.js'

const childHomeSource = readFileSync(
  new URL('../src/views/child/ChildHome.vue', import.meta.url),
  'utf8'
)

test('Family REAL page fetches authorized elder alerts and wires the emergency presentation into its card', () => {
  assert.match(childHomeSource, /elderApi\.alerts\(currentElder\.id\)/)
  assert.match(childHomeSource, /<section v-if="realMode" class="event-card"/)
  assert.match(childHomeSource, /alertPresentation\.label/)
  assert.match(childHomeSource, /alertPresentation\.createdAt/)

  const alert = {
    id: 42,
    elder_id: 7,
    trip_id: 18,
    type: 'emergency',
    status: 'new',
    occurred_at: '2026-10-07T08:30:00Z'
  }
  const presentation = presentAlertWorkflow(alert, true)
  assert.equal(presentation.label, '老人发起紧急求助')
  assert.equal(presentation.detail, '待处理')
})

test('Family polling updates the rendered alert after an initially empty response', async () => {
  const responses = [
    { items: [], total: 0 },
    {
      items: [{
        id: 42,
        elder_id: 7,
        trip_id: 18,
        type: 'emergency',
        status: 'new',
        occurred_at: '2026-10-07T08:30:00Z'
      }],
      total: 1
    }
  ]
  let responseIndex = 0
  let alertItems = []
  let presentation = presentAlertWorkflow(null, true)
  const controller = createPollingController({
    task: async () => {
      const result = responses[responseIndex++]
      alertItems = result.items
      presentation = presentAlertWorkflow(selectFamilyAlert(null, alertItems), true)
    },
    intervalMs: 15000,
    scheduleTimer: () => 1,
    cancelTimer: () => {}
  })

  await controller.start()
  assert.equal(presentation.label, '暂无告警')

  await controller.refresh()
  assert.equal(presentation.label, '老人发起紧急求助')
  assert.equal(presentation.detail, '待处理')
  assert.match(presentation.createdAt, /^创建时间：/)
  controller.stop()
})

test('REAL empty alerts stay empty and alert request failures are visible', () => {
  assert.equal(selectFamilyAlert(null, []), null)
  assert.equal(presentAlertWorkflow(null, true).label, '暂无告警')
  assert.equal(presentAlertWorkflow(null, false).label, '告警状态暂时无法获取')
  assert.match(childHomeSource, /alertSyncState\.value = 'error'/)
  assert.match(childHomeSource, /alertSyncState\.value === 'ready'/)
  assert.match(childHomeSource, /alerts\.value = alertResult\.alertList\?\.items \|\| \[\]/)
  assert.match(childHomeSource, /<section v-if="realMode" class="event-card"/)
})

test('Family load generation is checked before applying alert and elder state', () => {
  const responseStart = childHomeSource.indexOf('const [view, alertResult, trip, configuredGeofence]')
  const staleGuard = childHomeSource.indexOf(
    'if (loadGen !== currentLoadGeneration) return false',
    responseStart
  )
  const stateMutation = childHomeSource.indexOf('Object.assign(elder', responseStart)

  assert.ok(responseStart >= 0)
  assert.ok(staleGuard > responseStart)
  assert.ok(stateMutation > staleGuard)
  assert.match(childHomeSource, /currentLoadGeneration\+\+/)
})

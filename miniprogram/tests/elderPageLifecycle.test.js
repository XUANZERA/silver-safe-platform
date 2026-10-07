'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

function createElderPageHarness({ currentTrip = { id: 27, status: 'active' }, showModal, showToast } = {}) {
  const api = require('../services/api')
  const originalRequestSos = api.requestSos
  let pageDefinition
  global.wx = {
    getStorageSync() { return '' },
    showModal: showModal || ((options) => options?.success?.({ confirm: true, cancel: false })),
    showToast: showToast || (() => {})
  }
  global.Page = (definition) => { pageDefinition = definition }

  delete require.cache[require.resolve('../pages/elder/index')]
  require('../pages/elder/index')
  const page = {
    ...pageDefinition,
    data: {
      ...pageDefinition.data,
      loggedIn: true,
      currentTrip,
      locationStatus: 'TRACKING',
      guardRunning: true
    },
    setData(update) { Object.assign(this.data, update) }
  }

  return {
    api,
    page,
    restore() {
      api.requestSos = originalRequestSos
      delete global.Page
      delete global.wx
    }
  }
}

test('elder page load and pull-down refresh remain IDLE without calling wx.getLocation', async () => {
  let pageDefinition
  let locationCalls = 0
  global.wx = {
    getStorageSync() { return '' },
    getLocation() { locationCalls += 1 },
    stopPullDownRefresh() {}
  }
  global.Page = (definition) => { pageDefinition = definition }

  delete require.cache[require.resolve('../pages/elder/index')]
  require('../pages/elder/index')
  const page = {
    ...pageDefinition,
    data: { ...pageDefinition.data },
    setData(update) { Object.assign(this.data, update) }
  }

  assert.equal(page.data.username, '')
  assert.equal(page.data.password, '')

  page.onLoad()
  assert.equal(page.data.locationStatus, 'IDLE')
  assert.equal(locationCalls, 0)

  await page.onPullDownRefresh()
  assert.equal(page.data.locationStatus, 'IDLE')
  assert.equal(locationCalls, 0)

  page.onUnload()
  delete global.Page
  delete global.wx
})

test('elder page handleOpenSetting calls wx.openSetting and clears errorText', async () => {
  let pageDefinition
  let openSettingOptions = null
  global.wx = {
    getStorageSync() { return '' },
    getLocation() {},
    openSetting(options) {
      openSettingOptions = options
      options?.success?.({ authSetting: { 'scope.userLocation': true } })
    }
  }
  global.Page = (definition) => { pageDefinition = definition }

  delete require.cache[require.resolve('../pages/elder/index')]
  require('../pages/elder/index')
  const page = {
    ...pageDefinition,
    data: { ...pageDefinition.data, errorText: '定位权限被拒绝' },
    setData(update) { Object.assign(this.data, update) }
  }

  await page.handleOpenSetting()
  assert.notEqual(openSettingOptions, null)
  assert.equal(page.data.errorText, '')

  delete global.Page
  delete global.wx
})

test('elder SOS sends one request after confirmation for the active trip', async () => {
  let modalCount = 0
  const toastCalls = []
  const harness = createElderPageHarness({
    showModal(options) {
      modalCount += 1
      assert.equal(options.title, '确认发送紧急求助？')
      assert.equal(options.content, '系统将向家属/平台发送当前行程的紧急求助信息。')
      assert.equal(options.cancelText, '取消')
      assert.equal(options.confirmText, '确认求助')
      options.success({ confirm: true, cancel: false })
    },
    showToast(options) { toastCalls.push(options) }
  })
  const calls = []
  const trip = harness.page.data.currentTrip
  harness.api.requestSos = async (tripId) => { calls.push(tripId); return { id: 9 } }

  await harness.page.handleSos()

  assert.equal(modalCount, 1)
  assert.deepEqual(calls, [27])
  assert.deepEqual(toastCalls, [{ title: '紧急求助已发送', icon: 'success' }])
  assert.equal(harness.page.data.currentTrip, trip)
  assert.equal(harness.page.data.locationStatus, 'TRACKING')
  assert.equal(harness.page.data.guardRunning, true)
  assert.equal(harness.page.data.sosPending, false)
  assert.equal(harness.page.data.sosSending, false)
  harness.restore()
})

test('elder SOS cancellation sends no request', async () => {
  let calls = 0
  const harness = createElderPageHarness({
    showModal(options) { options.success({ confirm: false, cancel: true }) }
  })
  harness.api.requestSos = async () => { calls += 1 }

  await harness.page.handleSos()

  assert.equal(calls, 0)
  assert.equal(harness.page.data.sosPending, false)
  harness.restore()
})

for (const [label, currentTrip] of [
  ['no current trip', null],
  ['trip that has not started', { id: 27, status: 'created' }]
]) {
  test(`elder SOS with ${label} shows a friendly message and sends no request`, async () => {
    let modalCount = 0
    let requestCount = 0
    const harness = createElderPageHarness({ currentTrip, showModal() { modalCount += 1 } })
    harness.api.requestSos = async () => { requestCount += 1 }

    await harness.page.handleSos()

    assert.equal(modalCount, 0)
    assert.equal(requestCount, 0)
    assert.equal(harness.page.data.sosFeedbackText, '当前没有进行中的行程，无法发送行程紧急求助。')
    harness.restore()
  })
}

test('elder SOS single-flight covers a confirmation modal that is still open', async () => {
  let modalCount = 0
  let modalOptions
  let requestCount = 0
  const harness = createElderPageHarness({
    showModal(options) { modalCount += 1; modalOptions = options }
  })
  harness.api.requestSos = async () => { requestCount += 1; return { id: 9 } }

  const first = harness.page.handleSos()
  const second = harness.page.handleSos()
  assert.equal(modalCount, 1)
  assert.equal(harness.page.data.sosPending, true)
  assert.equal(harness.page.data.sosSending, false)

  modalOptions.success({ confirm: true, cancel: false })
  await Promise.all([first, second])

  assert.equal(requestCount, 1)
  assert.equal(harness.page.data.sosPending, false)
  harness.restore()
})

test('elder SOS single-flight blocks duplicate taps while the API request is pending', async () => {
  let requestCount = 0
  let resolveRequest
  const harness = createElderPageHarness()
  harness.api.requestSos = () => {
    requestCount += 1
    return new Promise((resolve) => { resolveRequest = resolve })
  }

  const first = harness.page.handleSos()
  await Promise.resolve()
  assert.equal(harness.page.data.sosSending, true)
  const second = harness.page.handleSos()
  assert.equal(requestCount, 1)
  assert.equal(harness.page.data.sosPending, true)

  resolveRequest({ id: 9 })
  await Promise.all([first, second])
  assert.equal(requestCount, 1)
  assert.equal(harness.page.data.sosPending, false)
  assert.equal(harness.page.data.sosSending, false)
  harness.restore()
})

test('elder SOS handles explicit no-active-trip response without success feedback', async () => {
  let refreshCount = 0
  let toastCount = 0
  const harness = createElderPageHarness({ showToast() { toastCount += 1 } })
  harness.api.requestSos = async () => { throw { status: 409, code: 'NO_ACTIVE_TRIP' } }
  harness.page.loadCurrentTrip = async () => { refreshCount += 1 }

  await harness.page.handleSos()

  assert.equal(refreshCount, 1)
  assert.equal(harness.page.data.sosFeedbackText, '当前没有进行中的行程，无法发送行程紧急求助。')
  assert.equal(toastCount, 0)
  harness.restore()
})

test('elder SOS reports network failure as failed or unknown and never shows success', async () => {
  let toastCount = 0
  const harness = createElderPageHarness({ showToast() { toastCount += 1 } })
  harness.api.requestSos = async () => { throw { code: 'NETWORK_ERROR' } }

  await harness.page.handleSos()

  assert.equal(harness.page.data.sosFeedbackText, '发送失败或状态未知，请重试或直接联系家人。')
  assert.equal(toastCount, 0)
  harness.restore()
})

test('volunteer pages do not prefill test credentials', () => {
  let elderPageDef
  let familyPageDef
  global.wx = { getStorageSync() { return '' } }
  global.Page = (definition) => {
    if (!elderPageDef) elderPageDef = definition
    else familyPageDef = definition
  }

  delete require.cache[require.resolve('../pages/elder/index')]
  delete require.cache[require.resolve('../pages/family/map')]
  require('../pages/elder/index')
  require('../pages/family/map')

  assert.equal(elderPageDef.data.username, '')
  assert.equal(elderPageDef.data.password, '')
  assert.equal(familyPageDef.data.username, '')
  assert.equal(familyPageDef.data.password, '')

  delete global.Page
  delete global.wx
})

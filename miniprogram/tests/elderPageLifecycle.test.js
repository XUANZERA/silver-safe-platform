'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

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

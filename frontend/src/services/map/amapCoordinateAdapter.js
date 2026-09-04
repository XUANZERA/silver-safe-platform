import { CANONICAL_CRS, validateCanonicalLocation, validateCanonicalTrack } from './mapLocationMapper.js'

export const DISPLAY_CRS = 'GCJ-02'
export const AMAP_MAX_BATCH_SIZE = 40

export class AmapConversionError extends Error {
  constructor(message = '高德坐标转换失败', { cause = null, code = 'MAP_CONVERSION_FAILED' } = {}) {
    super(message, cause === null ? undefined : { cause })
    this.name = 'AmapConversionError'
    this.code = code
  }
}

let cachedSdkPromise = null
let customSdkLoader = null

export function setAMapSdkLoader(loaderFn) {
  customSdkLoader = loaderFn
  cachedSdkPromise = null
}

export function resetAMapSdk() {
  customSdkLoader = null
  cachedSdkPromise = null
}

export function formatPolylinePath(points) {
  if (!Array.isArray(points) || points.length < 2) {
    return []
  }

  const path = []
  for (let i = 0; i < points.length; i++) {
    const pt = points[i]
    if (!pt || typeof pt !== 'object') {
      return []
    }

    let lng = null
    let lat = null

    if (Number.isFinite(pt.longitude) && Number.isFinite(pt.latitude)) {
      lng = pt.longitude
      lat = pt.latitude
    } else if (
      Array.isArray(pt) &&
      pt.length >= 2 &&
      Number.isFinite(pt[0]) &&
      Number.isFinite(pt[1])
    ) {
      lng = pt[0]
      lat = pt[1]
    } else {
      return []
    }

    if (lng < -180 || lng > 180 || lat < -90 || lat > 90) {
      return []
    }

    path.push([lng, lat])
  }

  return path.length >= 2 ? path : []
}

export function loadAMapSdk() {
  if (typeof window !== 'undefined' && window.AMap && typeof window.AMap.convertFrom === 'function') {
    return Promise.resolve(window.AMap)
  }
  if (cachedSdkPromise) {
    return cachedSdkPromise
  }

  if (customSdkLoader) {
    cachedSdkPromise = Promise.resolve()
      .then(() => customSdkLoader())
      .then((sdk) => {
        if (!sdk || typeof sdk.convertFrom !== 'function') {
          throw new AmapConversionError('高德地图SDK未包含convertFrom接口', { code: 'MAP_UNAVAILABLE' })
        }
        return sdk
      })
      .catch((err) => {
        cachedSdkPromise = null
        if (err instanceof AmapConversionError) throw err
        throw new AmapConversionError(`高德地图SDK加载失败: ${err?.message || '未知错误'}`, {
          code: 'MAP_UNAVAILABLE',
          cause: err
        })
      })
    return cachedSdkPromise
  }

  if (typeof window === 'undefined') {
    return Promise.reject(
      new AmapConversionError('高德地图SDK未在当前环境中就绪', { code: 'MAP_UNAVAILABLE' })
    )
  }

  const key =
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_AMAP_KEY) ||
    (typeof process !== 'undefined' && process.env?.VITE_AMAP_KEY) ||
    ''
  const securityJsCode =
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_AMAP_SECURITY_JS_CODE) ||
    (typeof process !== 'undefined' && process.env?.VITE_AMAP_SECURITY_JS_CODE) ||
    ''

  const normalizedKey = typeof key === 'string' ? key.trim() : ''
  const normalizedSecurityJsCode = typeof securityJsCode === 'string' ? securityJsCode.trim() : ''

  if (!normalizedKey || !normalizedSecurityJsCode) {
    return Promise.reject(
      new AmapConversionError('高德地图配置缺失(VITE_AMAP_KEY 或 VITE_AMAP_SECURITY_JS_CODE)', {
        code: 'MAP_UNAVAILABLE'
      })
    )
  }

  window._AMapSecurityConfig = {
    securityJsCode: normalizedSecurityJsCode
  }

  cachedSdkPromise = (async () => {
    try {
      const loaderModule = await import('@amap/amap-jsapi-loader')
      const AMapLoader = loaderModule.default || loaderModule
      const AMap = await AMapLoader.load({
        key: normalizedKey,
        version: '2.0'
      })
      if (!AMap || typeof AMap.convertFrom !== 'function') {
        throw new AmapConversionError('高德地图SDK未包含convertFrom接口', { code: 'MAP_UNAVAILABLE' })
      }
      return AMap
    } catch (err) {
      cachedSdkPromise = null
      if (err instanceof AmapConversionError) throw err
      throw new AmapConversionError(`高德地图SDK加载失败: ${err?.message || '未知错误'}`, {
        code: 'MAP_UNAVAILABLE',
        cause: err
      })
    }
  })()

  return cachedSdkPromise
}

function extractLngLatFromResult(location) {
  if (!location) return null
  let lng = null
  let lat = null
  if (typeof location.getLng === 'function' && typeof location.getLat === 'function') {
    lng = location.getLng()
    lat = location.getLat()
  } else if (Number.isFinite(location.lng) && Number.isFinite(location.lat)) {
    lng = location.lng
    lat = location.lat
  } else if (Array.isArray(location) && location.length >= 2 && Number.isFinite(location[0]) && Number.isFinite(location[1])) {
    lng = location[0]
    lat = location[1]
  }
  if (lng !== null && lat !== null && Number.isFinite(lng) && Number.isFinite(lat) && lng >= -180 && lng <= 180 && lat >= -90 && lat <= 90) {
    return [lng, lat]
  }
  return null
}

export async function convertCoordinatesWithAMap(points, { aMap = null, converter = null } = {}) {
  if (!Array.isArray(points) || points.length === 0) {
    return []
  }

  if (typeof converter === 'function') {
    let res
    try {
      res = await converter(points, 'gps')
    } catch (err) {
      throw new AmapConversionError('坐标转换器调用失败', { cause: err })
    }
    if (!Array.isArray(res) || res.length !== points.length) {
      throw new AmapConversionError(`自定义转换器返回坐标数量不匹配: 期望 ${points.length}, 收到 ${res?.length ?? 0}`)
    }
    for (let i = 0; i < res.length; i++) {
      const pt = res[i]
      if (!pt || !Number.isFinite(pt[0]) || !Number.isFinite(pt[1])) {
        throw new AmapConversionError(`自定义转换器返回非法坐标[${i}]`)
      }
    }
    return res
  }

  if (points.length > AMAP_MAX_BATCH_SIZE) {
    throw new AmapConversionError(`单次坐标转换点数超过高德上限(${AMAP_MAX_BATCH_SIZE}): ${points.length}`)
  }

  let amapInstance = aMap
  if (!amapInstance) {
    try {
      amapInstance = await loadAMapSdk()
    } catch (err) {
      if (err instanceof AmapConversionError) throw err
      throw new AmapConversionError('高德地图SDK未就绪', { code: 'MAP_UNAVAILABLE', cause: err })
    }
  }

  if (!amapInstance || typeof amapInstance.convertFrom !== 'function') {
    throw new AmapConversionError('高德地图SDK未包含convertFrom接口', { code: 'MAP_UNAVAILABLE' })
  }

  return new Promise((resolve, reject) => {
    try {
      amapInstance.convertFrom(points, 'gps', (status, result) => {
        if (status === 'complete' && result?.info === 'ok' && Array.isArray(result?.locations)) {
          if (result.locations.length !== points.length) {
            reject(new AmapConversionError(`高德转换返回数量不匹配: 期望 ${points.length}, 收到 ${result.locations.length}`))
            return
          }
          const parsed = result.locations.map(extractLngLatFromResult)
          if (parsed.some((p) => p === null)) {
            reject(new AmapConversionError('高德转换返回的坐标格式不合法'))
            return
          }
          resolve(parsed)
          return
        }
        reject(new AmapConversionError(`高德坐标转换失败: ${result?.info || status || '未知错误'}`))
      })
    } catch (err) {
      reject(new AmapConversionError('调用高德转换API抛出异常', { cause: err }))
    }
  })
}

export async function convertCanonicalLocation(canonical, options = {}) {
  const validated = validateCanonicalLocation(canonical)
  if (validated.sourceCrs !== CANONICAL_CRS) {
    throw new AmapConversionError(`仅支持转换 ${CANONICAL_CRS} 坐标，收到: ${validated.sourceCrs}`)
  }

  const wgsPoint = [validated.longitude, validated.latitude]
  const convertedList = await convertCoordinatesWithAMap([wgsPoint], options)
  const converted = convertedList?.[0]
  if (!converted || !Number.isFinite(converted[0]) || !Number.isFinite(converted[1])) {
    throw new AmapConversionError('高德转换未返回有效经纬度')
  }

  return {
    longitude: converted[0],
    latitude: converted[1],
    displayCrs: DISPLAY_CRS,
    recordedAt: validated.recordedAt,
    accuracyMeters: validated.accuracyMeters,
    id: validated.id,
    tripId: validated.tripId
  }
}

export async function convertCanonicalTrack(canonicalPoints, options = {}) {
  if (!Array.isArray(canonicalPoints) || canonicalPoints.length === 0) {
    return []
  }

  // Preserve chronological order
  const validatedList = canonicalPoints.map((pt) => validateCanonicalLocation(pt))
  const convertedAll = []

  for (let i = 0; i < validatedList.length; i += AMAP_MAX_BATCH_SIZE) {
    const batchValidated = validatedList.slice(i, i + AMAP_MAX_BATCH_SIZE)
    const batchWgs = batchValidated.map((pt) => [pt.longitude, pt.latitude])
    const batchConverted = await convertCoordinatesWithAMap(batchWgs, options)
    if (!Array.isArray(batchConverted) || batchConverted.length !== batchValidated.length) {
      throw new AmapConversionError('轨迹批量转换结果数量与输入不一致')
    }
    convertedAll.push(...batchConverted)
  }

  if (convertedAll.length !== validatedList.length) {
    throw new AmapConversionError('轨迹批量转换结果总数与输入不一致')
  }

  return validatedList.map((validated, index) => {
    const converted = convertedAll[index]
    if (!converted || !Number.isFinite(converted[0]) || !Number.isFinite(converted[1])) {
      throw new AmapConversionError(`轨迹点[${index}]转换未返回有效坐标`)
    }
    return {
      longitude: converted[0],
      latitude: converted[1],
      displayCrs: DISPLAY_CRS,
      recordedAt: validated.recordedAt,
      accuracyMeters: validated.accuracyMeters,
      id: validated.id,
      tripId: validated.tripId
    }
  })
}

export function createLatestLocationCoordinator({
  convertLocation = convertCanonicalLocation
} = {}) {
  let latestGeneration = 0

  return {
    async update(canonical, options = {}) {
      const currentGen = ++latestGeneration
      const mapPoint = await convertLocation(canonical, options)
      if (currentGen !== latestGeneration) {
        return {
          discarded: true,
          generation: currentGen,
          latestGeneration,
          mapPoint: null
        }
      }
      return {
        discarded: false,
        generation: currentGen,
        latestGeneration,
        mapPoint
      }
    },
    reset() {
      latestGeneration++
    },
    getGeneration: () => latestGeneration
  }
}

export function createOperatorSelectionCoordinator({
  fetchSafety,
  convertLocation = convertCanonicalLocation,
  validateLocation = validateCanonicalLocation,
  onStateChange = () => {}
} = {}) {
  let currentGeneration = 0
  let currentElderId = null

  async function selectElder(elder) {
    const generation = ++currentGeneration
    const elderId = elder?.id ?? null
    currentElderId = elderId

    if (!elder || !elderId) {
      onStateChange({
        status: 'NO_LOCATION',
        point: null,
        generation,
        elderId: null
      })
      return
    }

    onStateChange({
      status: 'DATA_UNAVAILABLE',
      point: null,
      generation,
      elderId
    })

    let view = null
    try {
      view = await fetchSafety(elderId)
    } catch (err) {
      if (generation !== currentGeneration || currentElderId !== elderId) {
        return
      }
      onStateChange({
        status: 'DATA_UNAVAILABLE',
        point: null,
        generation,
        elderId,
        error: err
      })
      return
    }

    if (generation !== currentGeneration || currentElderId !== elderId) {
      return
    }

    if (!view?.latest_location) {
      onStateChange({
        status: 'NO_LOCATION',
        point: null,
        generation,
        elderId
      })
      return
    }

    let canonical = null
    try {
      canonical = validateLocation(view.latest_location)
    } catch (err) {
      if (generation !== currentGeneration || currentElderId !== elderId) {
        return
      }
      onStateChange({
        status: 'MAP_CONVERSION_FAILED',
        point: null,
        generation,
        elderId,
        error: err
      })
      return
    }

    try {
      const mapPoint = await convertLocation(canonical)
      if (generation !== currentGeneration || currentElderId !== elderId) {
        return
      }
      onStateChange({
        status: 'READY',
        point: mapPoint,
        generation,
        elderId
      })
    } catch (err) {
      if (generation !== currentGeneration || currentElderId !== elderId) {
        return
      }
      const status = err?.code === 'MAP_UNAVAILABLE' ? 'MAP_UNAVAILABLE' : 'MAP_CONVERSION_FAILED'
      onStateChange({
        status,
        point: null,
        generation,
        elderId,
        error: err
      })
    }
  }

  function clearSelection() {
    currentGeneration++
    currentElderId = null
    onStateChange({
      status: 'NO_LOCATION',
      point: null,
      generation: currentGeneration,
      elderId: null
    })
  }

  return {
    selectElder,
    clearSelection,
    getGeneration: () => currentGeneration,
    getCurrentElderId: () => currentElderId
  }
}

export function createFamilyStateCoordinator({
  fetchElders,
  fetchSafety,
  fetchAlerts,
  fetchCurrentTrip,
  fetchTrack,
  convertLocation = convertCanonicalLocation,
  convertTrack = convertCanonicalTrack,
  validateLocation = validateCanonicalLocation,
  validateTrack = validateCanonicalTrack,
  onStateChange = () => {}
} = {}) {
  let currentLoadGeneration = 0
  let currentTripId = null

  async function loadAuthoritativeState() {
    const loadGen = ++currentLoadGeneration
    onStateChange({ type: 'LOADING', loading: true, generation: loadGen })

    try {
      const elderList = await fetchElders()
      if (loadGen !== currentLoadGeneration) return

      const currentElder = elderList?.items?.[0]
      if (!currentElder) {
        throw new Error('没有可查看的老人资料')
      }

      const [view, alertList, trip] = await Promise.all([
        fetchSafety(currentElder.id),
        fetchAlerts(currentElder.id),
        fetchCurrentTrip(currentElder.id)
      ])
      if (loadGen !== currentLoadGeneration) return
      if (!view) {
        throw new Error('后端未返回安全状态')
      }

      const tripIdSnapshot = trip?.id || null
      currentTripId = tripIdSnapshot

      onStateChange({
        type: 'AUTHORITATIVE_DATA',
        elder: currentElder,
        trip,
        safetyView: view,
        alerts: alertList?.items || [],
        generation: loadGen
      })

      const latestLocation = view.latest_location
      if (latestLocation) {
        try {
          const canonical = validateLocation(latestLocation)
          const converted = await convertLocation(canonical)
          if (loadGen === currentLoadGeneration) {
            onStateChange({
              type: 'LOCATION_READY',
              mapPoint: converted,
              mapStatus: 'READY',
              generation: loadGen
            })
          }
        } catch (err) {
          if (loadGen === currentLoadGeneration) {
            const status = err?.code === 'MAP_UNAVAILABLE' ? 'MAP_UNAVAILABLE' : 'MAP_CONVERSION_FAILED'
            onStateChange({
              type: 'LOCATION_ERROR',
              mapPoint: null,
              mapStatus: status,
              generation: loadGen,
              error: err
            })
          }
        }
      } else {
        if (loadGen === currentLoadGeneration) {
          onStateChange({
            type: 'LOCATION_NONE',
            mapPoint: null,
            mapStatus: 'NO_LOCATION',
            generation: loadGen
          })
        }
      }

      if (tripIdSnapshot && fetchTrack) {
        try {
          const trackRes = await fetchTrack(tripIdSnapshot)
          if (loadGen === currentLoadGeneration && currentTripId === tripIdSnapshot) {
            if (trackRes?.items?.length) {
              const canonicalItems = validateTrack(trackRes.items)
              const convertedTrack = await convertTrack(canonicalItems)
              if (loadGen === currentLoadGeneration && currentTripId === tripIdSnapshot) {
                onStateChange({
                  type: 'TRACK_READY',
                  trackPoints: convertedTrack,
                  generation: loadGen,
                  tripId: tripIdSnapshot
                })
              }
            } else {
              onStateChange({
                type: 'TRACK_EMPTY',
                trackPoints: [],
                generation: loadGen,
                tripId: tripIdSnapshot
              })
            }
          }
        } catch (err) {
          if (loadGen === currentLoadGeneration && currentTripId === tripIdSnapshot) {
            onStateChange({
              type: 'TRACK_ERROR',
              trackPoints: [],
              generation: loadGen,
              tripId: tripIdSnapshot,
              error: err
            })
          }
        }
      } else {
        if (loadGen === currentLoadGeneration) {
          onStateChange({
            type: 'TRACK_EMPTY',
            trackPoints: [],
            generation: loadGen,
            tripId: tripIdSnapshot
          })
        }
      }
    } catch (err) {
      if (loadGen === currentLoadGeneration) {
        onStateChange({
          type: 'ERROR',
          error: err,
          mapStatus: 'DATA_UNAVAILABLE',
          generation: loadGen
        })
        throw err
      }
    } finally {
      if (loadGen === currentLoadGeneration) {
        onStateChange({ type: 'FINISH', loading: false, generation: loadGen })
      }
    }
  }

  function reset() {
    currentLoadGeneration++
    currentTripId = null
  }

  return {
    loadAuthoritativeState,
    reset,
    getLoadGeneration: () => currentLoadGeneration,
    getCurrentTripId: () => currentTripId
  }
}

export function createMapLifecycleManager({
  loadSdk = loadAMapSdk,
  initMap = () => {},
  onReady = () => {},
  onError = () => {}
} = {}) {
  let isAlive = true
  let mapInstance = null

  async function mount() {
    try {
      const AMap = await loadSdk()
      if (!isAlive) {
        return { initialized: false, reason: 'destroyed_before_sdk' }
      }
      mapInstance = await initMap(AMap)
      if (!isAlive) {
        if (mapInstance && typeof mapInstance.destroy === 'function') {
          mapInstance.destroy()
        }
        mapInstance = null
        return { initialized: false, reason: 'destroyed_before_ready' }
      }
      onReady(mapInstance)
      return { initialized: true, mapInstance }
    } catch (err) {
      if (!isAlive) {
        return { initialized: false, reason: 'destroyed_on_error', error: err }
      }
      onError(err)
      throw err
    }
  }

  function destroy() {
    isAlive = false
    if (mapInstance && typeof mapInstance.destroy === 'function') {
      mapInstance.destroy()
    }
    mapInstance = null
  }

  return {
    mount,
    destroy,
    isAlive: () => isAlive,
    getMapInstance: () => mapInstance
  }
}


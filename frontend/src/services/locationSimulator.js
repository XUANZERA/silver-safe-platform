/**
 * 创建定位数据模拟器。
 *
 * points：
 * 要依次发送的定位点。
 *
 * intervalMs：
 * 两个定位点之间的时间间隔。
 *
 * onPoint：
 * 每产生一个定位点时调用。
 *
 * onStatusChange：
 * 模拟器状态变化时调用。
 *
 * onComplete：
 * 所有定位点发送完成时调用。
 */
export function createLocationSimulator({
  points,
  intervalMs = 2000,
  onPoint,
  onStatusChange,
  onComplete,
}) {
  if (!Array.isArray(points)) {
    throw new TypeError("模拟轨迹必须是数组")
  }

  let currentIndex = 0
  let timerId = null
  let status = "IDLE"

  function changeStatus(nextStatus) {
    status = nextStatus
    onStatusChange?.(nextStatus)
  }

  function clearTimer() {
    if (timerId !== null) {
      window.clearInterval(timerId)
      timerId = null
    }
  }

  function finish() {
    clearTimer()
    changeStatus("COMPLETED")
    onComplete?.()
  }

  function emitNextPoint() {
    if (currentIndex >= points.length) {
      finish()
      return
    }

    const point = points[currentIndex]

    onPoint?.(point, currentIndex)

    currentIndex += 1

    if (currentIndex >= points.length) {
      finish()
    }
  }

  function start() {
    if (points.length === 0) {
      console.warn("没有可模拟的定位点")
      return
    }

    // 防止重复点击开始，产生多个定时器
    if (timerId !== null) {
      return
    }

    changeStatus("RUNNING")

    // 点击开始后，立即发送第一个点
    emitNextPoint()

    if (currentIndex < points.length) {
      timerId = window.setInterval(
        emitNextPoint,
        intervalMs,
      )
    }
  }

  function pause() {
    if (timerId === null) {
      return
    }

    clearTimer()
    changeStatus("PAUSED")
  }

  function reset() {
    clearTimer()
    currentIndex = 0
    changeStatus("IDLE")
  }

  function destroy() {
    clearTimer()
  }

  function getCurrentIndex() {
    return currentIndex
  }

  return {
    start,
    pause,
    reset,
    destroy,
    getCurrentIndex,
  }
}
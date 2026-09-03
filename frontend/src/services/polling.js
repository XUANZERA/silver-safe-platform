export function normalizePollingInterval(value, fallback = 15000) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 1000 ? parsed : fallback
}

export function createPollingController({
  task,
  intervalMs,
  onError = () => {},
  scheduleTimer = setTimeout,
  cancelTimer = clearTimeout
}) {
  let running = false
  let timerId = null
  let inFlight = null
  let consecutiveFailures = 0

  function clearScheduledRun() {
    if (timerId !== null) cancelTimer(timerId)
    timerId = null
  }

  function scheduleNextRun() {
    clearScheduledRun()
    if (!running) return
    const multiplier = 2 ** Math.min(consecutiveFailures, 2)
    timerId = scheduleTimer(() => { void execute() }, intervalMs * multiplier)
  }

  function execute() {
    if (inFlight) return inFlight
    clearScheduledRun()
    inFlight = Promise.resolve()
      .then(task)
      .then((value) => {
        consecutiveFailures = 0
        return { ok: true, value }
      })
      .catch((error) => {
        consecutiveFailures += 1
        onError(error)
        return { ok: false, error }
      })
      .finally(() => {
        inFlight = null
        scheduleNextRun()
      })
    return inFlight
  }

  return {
    start() {
      if (running) return inFlight || Promise.resolve({ ok: true })
      running = true
      return execute()
    },
    stop() {
      running = false
      clearScheduledRun()
    },
    refresh: execute,
    async refreshAfterCurrent() {
      if (inFlight) await inFlight
      return execute()
    },
    isRunning: () => running,
    isRequestInFlight: () => inFlight !== null
  }
}

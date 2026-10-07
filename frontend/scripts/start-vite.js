import { spawn } from 'node:child_process'
import { resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

export const REAL_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'

export function createViteLaunch(mode, inheritedEnv = process.env) {
  if (mode !== 'real' && mode !== 'demo') {
    throw new Error(`Unknown frontend mode: ${mode}`)
  }

  return {
    args: ['--mode', mode, '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    env: {
      ...inheritedEnv,
      VITE_API_BASE_URL: mode === 'real' ? REAL_API_BASE_URL : ''
    }
  }
}

function startVite() {
  let launch
  try {
    launch = createViteLaunch(process.argv[2])
  } catch (error) {
    console.error(error.message)
    process.exitCode = 2
    return
  }

  const viteCli = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url))
  const child = spawn(process.execPath, [viteCli, ...launch.args], {
    env: launch.env,
    stdio: 'inherit'
  })

  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => child.kill(signal))
  }

  child.on('error', (error) => {
    console.error(error)
    process.exitCode = 1
  })
  child.on('exit', (code, signal) => {
    process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 1)
  })
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  startVite()
}

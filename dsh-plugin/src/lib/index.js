/**
 * dsh-aiwish-timetable — host half.
 *
 * This plugin owns no scheduling logic.  It starts the bundled Python sidecar
 * (the unchanged AI-WISH engine/API) on a loopback port and proxies
 * `/plugins/aiwish/*` to it, so the browser sees one same-origin plugin app.
 */
import { spawn } from 'node:child_process'
import { createWriteStream, existsSync, mkdirSync, chmodSync, readFileSync, readdirSync, statSync } from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'aiwish-timetable'
export const inject = ['webServer']

const BASE = '/plugins/aiwish'
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SERVER_DIR = path.join(ROOT, 'server')
const APP_DIR = path.join(ROOT, 'app')
const RUNTIME_DIR = path.join(ROOT, 'runtime')
const DATA_DIR = process.env.AIWISH_DATA_DIR || path.join(process.env.DSH_HOME || path.join(os.homedir(), '.dsh'), 'plugin-data', 'dsh-aiwish-timetable')
const LOG_FILE = path.join(DATA_DIR, 'server.log')

let child = null
let childPort = 0
let starting = null
let lastError = ''
let disposed = false
let logStream = null

function pythonPath() {
  if (process.env.AIWISH_PYTHON) return process.env.AIWISH_PYTHON
  return process.platform === 'win32'
    ? path.join(RUNTIME_DIR, 'python.exe')
    : path.join(RUNTIME_DIR, 'bin', 'python3')
}

function appendLog(line) {
  try {
    if (!logStream) {
      mkdirSync(DATA_DIR, { recursive: true })
      logStream = createWriteStream(LOG_FILE, { flags: 'a' })
    }
    logStream.write(line)
  } catch {
    /* Logging must not stop the server. */
  }
}

function tailLog() {
  try {
    const text = readFileSync(LOG_FILE, 'utf8')
    return text.slice(-6000)
  } catch {
    return ''
  }
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function health(port) {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(1200) })
    return res.ok
  } catch {
    return false
  }
}

async function startServer() {
  if (disposed) throw new Error('plugin 已卸载')
  if (child && child.exitCode === null && childPort) return childPort
  if (starting) return starting
  starting = (async () => {
    mkdirSync(DATA_DIR, { recursive: true })
    const exe = pythonPath()
    if (!existsSync(exe)) {
      throw new Error(`未找到内置 Python 运行时：${exe}。请安装对应平台的插件包。`)
    }
    if (process.platform !== 'win32') {
      try { chmodSync(exe, 0o755) } catch { /* best effort */ }
    }
    const serverFile = path.join(SERVER_DIR, 'backend', 'app', 'plugin_server.py')
    if (!existsSync(serverFile)) throw new Error(`插件服务端文件缺失：${serverFile}`)

    const env = {
      ...process.env,
      PYTHONPATH: [path.join(SERVER_DIR, 'backend'), path.join(SERVER_DIR, 'engine')].join(path.delimiter),
      PYTHONNOUSERSITE: '1',
      PYTHONDONTWRITEBYTECODE: '1',
      AIWISH_DB: path.join(DATA_DIR, 'aiwish.db'),
      AIWISH_STATIC_DIR: APP_DIR,
      AIWISH_STATIC_PREFIX: '/app',
      AIWISH_LOG_LEVEL: 'warning',
    }
    appendLog(`\n[aiwish] ${new Date().toISOString()} spawn ${exe}\n`)
    child = spawn(exe, ['-m', 'app.plugin_server'], {
      cwd: SERVER_DIR,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    let buffer = ''
    let portResolve
    let portReject
    const portPromise = new Promise((resolve, reject) => { portResolve = resolve; portReject = reject })
    const onData = (text) => {
      appendLog(text)
      buffer += text
      const m = buffer.match(/AIWISH_PORT=(\d+)/)
      if (m) portResolve(Number(m[1]))
    }
    child.stdout.on('data', onData)
    child.stderr.on('data', onData)
    child.on('error', (error) => {
      lastError = String(error?.message ?? error)
      appendLog(`\n[aiwish] spawn error: ${lastError}\n`)
      portReject(new Error(lastError))
    })
    child.on('exit', (code, signal) => {
      appendLog(`\n[aiwish] exited code=${code} signal=${signal}\n`)
      if (childPort === 0) portReject(new Error(`sidecar 启动前退出（code=${code}, signal=${signal}）`))
      child = null
      childPort = 0
    })
    const port = await Promise.race([
      portPromise,
      wait(30000).then(() => { throw new Error('sidecar 启动超时（30秒）') }),
    ])
    let ok = false
    for (let i = 0; i < 80; i++) {
      if (await health(port)) { ok = true; break }
      await wait(150)
    }
    if (!ok) throw new Error(`sidecar 已报告端口 ${port}，但健康检查未通过`)
    childPort = port
    lastError = ''
    return port
  })()
  try {
    return await starting
  } catch (error) {
    lastError = String(error?.message ?? error)
    appendLog(`\n[aiwish] startup failed: ${lastError}\n`)
    throw error
  } finally {
    starting = null
  }
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj)
  res.statusCode = status
  res.setHeader('content-type', 'application/json; charset=utf-8')
  res.setHeader('cache-control', 'no-store')
  res.end(body)
}

function proxy(req, res, port) {
  const url = new URL(req.url ?? '/', 'http://127.0.0.1')
  let target = url.pathname.slice(BASE.length) || '/'
  if (!target.startsWith('/')) target = '/' + target
  if (target === '/') {
    res.statusCode = 302
    res.setHeader('location', `${BASE}/app/index.html`)
    res.end()
    return
  }
  const headers = { ...req.headers, host: `127.0.0.1:${port}` }
  delete headers['accept-encoding']
  const upstream = http.request({
    host: '127.0.0.1', port, path: target + url.search,
    method: req.method, headers,
  }, (up) => {
    res.writeHead(up.statusCode ?? 502, up.headers)
    up.pipe(res)
  })
  upstream.on('error', (error) => {
    if (!res.headersSent) sendJson(res, 502, { error: `sidecar 代理失败：${error.message}`, log: tailLog() })
    else res.end()
  })
  req.pipe(upstream)
}

export function apply(ctx) {
  const handler = async (req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://127.0.0.1')
      if (url.pathname === `${BASE}/diag`) {
        return sendJson(res, 200, {
          plugin: name, platform: process.platform, arch: process.arch,
          python: pythonPath(), server_dir: SERVER_DIR, data_dir: DATA_DIR,
          port: childPort, running: Boolean(child && child.exitCode === null),
          last_error: lastError, log_tail: tailLog(),
        })
      }
      const port = await startServer()
      proxy(req, res, port)
    } catch (error) {
      const message = String(error?.message ?? error)
      lastError = message
      if (url.pathname.startsWith(`${BASE}/api/`)) return sendJson(res, 503, { error: message, log: tailLog() })
      res.statusCode = 503
      res.setHeader('content-type', 'text/html; charset=utf-8')
      res.end(`<!doctype html><html><head><meta charset="utf-8"><title>AI-WISH 启动失败</title></head>
<body style="font-family:system-ui;padding:40px;color:#142033;background:#f4f6f9">
<h1 style="color:#b42318">AI-WISH 排课服务未启动</h1>
<p>${message.replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}</p>
<p style="color:#667085">请检查插件是否是对应平台包，或打开 <code>${BASE}/diag</code> 查看日志。</p>
<pre style="background:#fff;border:1px solid #e4e8ef;padding:12px;max-height:360px;overflow:auto">${tailLog().replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}</pre>
</body></html>`)
    }
  }
  const dispose = ctx.webServer.register({ kind: 'prefix', path: BASE, handler })
  ctx.effect(() => () => {
    disposed = true
    try { dispose?.() } catch { /* ignore */ }
    try { child?.kill() } catch { /* ignore */ }
    child = null
    childPort = 0
    try { logStream?.end() } catch { /* ignore */ }
  })
}

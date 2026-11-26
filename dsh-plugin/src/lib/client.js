window.__ModuleLoader__.load({
  id: 'dsh-aiwish-timetable',
  factory: (require) => {
    const module = { exports: {} }
    const exports = module.exports
    const ENTRY = 'data-dsh-aiwish-entry'
    const PANEL = 'data-dsh-aiwish-panel'
    const ACTIVE = 'data-dsh-aiwish-active'
    const STYLE = 'dsh-aiwish-style'
    const APP_URL = '/plugins/aiwish/app/index.html'
    const SIDEBAR = ['[data-pane="sidebar"]','[class*="sidebarCol"]','[class*="dshDesktopSidebarSurface"]','[class*="dshDesktopUpstreamSidebar"]'].join(', ')
    const CENTER = '[data-pane="conversation"], [class*="centerCol"]'
    const ICON = '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.1" y="3.1" width="11.8" height="10.5" rx="1.7"/><path d="M2.1 6.2h11.8M5.3 1.7v2.7M10.7 1.7v2.7M5.2 9h2.1M8.7 9h2.1M5.2 11.4h2.1M8.7 11.4h2.1"/></svg>'
    const CSS = `
      .dsh-aw-entry{display:flex;align-items:center;gap:9px;width:100%;padding:8px 12px;margin:2px 0;border:0;border-radius:10px;background:transparent;color:inherit;font:inherit;font-size:13.5px;cursor:pointer;text-align:left;opacity:.82;transition:background .15s ease,opacity .15s ease}
      .dsh-aw-entry:hover{background:rgba(127,127,127,.12);opacity:1}
      .dsh-aw-entry[data-active="true"]{background:rgba(127,127,127,.16);opacity:1;font-weight:600}
      .dsh-aw-entry .dsh-aw-icon{display:grid;place-items:center;width:18px;height:18px;flex:none;opacity:.92}
      .dsh-aw-panel{position:absolute;inset:0;z-index:30;box-sizing:border-box;padding-top:var(--dsh-aw-top,0px);background:#f4f6f9;display:none;overflow:hidden;-webkit-app-region:no-drag}
      .dsh-aw-panel[data-open="true"]{display:block}
      .dsh-aw-panel iframe{width:100%;height:100%;border:0;display:block;background:#f4f6f9;-webkit-app-region:no-drag}
      .dsh-aw-close{position:absolute;top:calc(var(--dsh-aw-top,0px) + 12px);right:16px;z-index:3;width:30px;height:30px;border-radius:8px;border:1px solid rgba(0,0,0,.12);background:rgba(255,255,255,.9);color:#33302a;font-size:15px;line-height:1;cursor:pointer;display:grid;place-items:center}
      .dsh-aw-close:hover{background:#fff}
      .dsh-aw-loading{position:absolute;inset:var(--dsh-aw-top,0px) 0 0 0;z-index:2;display:grid;place-items:center;background:#f4f6f9;color:#667085;font:13px -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
      .dsh-aw-loading[hidden]{display:none}
      .dsh-aw-fab{position:fixed;right:22px;bottom:22px;z-index:40;width:46px;height:46px;border-radius:50%;border:1px solid rgba(0,0,0,.12);background:#fff;box-shadow:0 8px 22px -12px rgba(0,0,0,.5);display:grid;place-items:center;cursor:pointer;color:#0f2138}
    `
    function injectStyle() {
      if (document.getElementById(STYLE)) return
      const style = document.createElement('style')
      style.id = STYLE
      style.textContent = CSS
      document.head.appendChild(style)
    }
    function sidebarRoot() { return document.querySelector(SIDEBAR) }
    function newSessionButton(root) {
      const direct = root.querySelector('button[data-dsh-part="new-session"], button[class*="newSession"]')
      if (direct) return direct
      return Array.from(root.querySelectorAll('button')).find(b => {
        const n = `${b.getAttribute('aria-label') || ''} ${b.getAttribute('title') || ''} ${b.textContent || ''}`.toLowerCase().replace(/\s+/g, ' ')
        return ['new session','new chat','新会话','新建会话','新对话'].some(x => n.includes(x))
      })
    }
    function mountEntry() {
      const root = sidebarRoot()
      if (!root || root.querySelector(`[${ENTRY}]`)) return
      const entry = document.createElement('button')
      entry.type = 'button'
      entry.setAttribute(ENTRY, '')
      entry.className = 'dsh-aw-entry'
      entry.innerHTML = `<span class="dsh-aw-icon">${ICON}</span><span>智能排课</span>`
      entry.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); toggle() })
      const anchor = newSessionButton(root)
      if (anchor?.parentElement) anchor.insertAdjacentElement('afterend', entry)
      else root.insertBefore(entry, root.firstChild)
    }
    function applyClearance(panel, column) {
      try {
        const raw = getComputedStyle(document.documentElement).getPropertyValue('--dsh-frame-top-clearance')
        const fullscreen = document.documentElement.hasAttribute('data-fullscreen')
        const clearance = fullscreen ? 0 : Number.parseFloat(raw) || 0
        const top = column.getBoundingClientRect().top
        const need = Math.max(0, Math.round(clearance - top))
        panel.style.setProperty('--dsh-aw-top', need ? `${need}px` : '0px')
      } catch { /* keep 0 */ }
    }
    function ensurePanel() {
      const column = document.querySelector(CENTER)
      if (!column) return null
      let panel = document.querySelector(`[${PANEL}]`)
      if (panel && panel.parentElement === column) return panel
      panel?.remove()
      panel = document.createElement('div')
      panel.setAttribute(PANEL, '')
      panel.className = 'dsh-aw-panel'
      panel.dataset.open = 'false'
      const loading = document.createElement('div')
      loading.className = 'dsh-aw-loading'
      loading.textContent = '正在启动本地排课服务…'
      const frame = document.createElement('iframe')
      frame.src = APP_URL
      frame.title = 'AI-WISH 智能走班排课'
      frame.setAttribute('allow', 'clipboard-write')
      frame.addEventListener('load', () => { loading.hidden = true })
      const close = document.createElement('button')
      close.type = 'button'
      close.className = 'dsh-aw-close'
      close.textContent = '✕'
      close.title = '收起'
      close.addEventListener('click', () => toggle(false))
      panel.append(loading, frame, close)
      if (getComputedStyle(column).position === 'static') column.style.position = 'relative'
      column.appendChild(panel)
      applyClearance(panel, column)
      return panel
    }
    function mountFab() {
      if (document.querySelector('[data-dsh-aw-fab]')) return
      const fab = document.createElement('button')
      fab.type = 'button'
      fab.className = 'dsh-aw-fab'
      fab.setAttribute('data-dsh-aw-fab', '')
      fab.title = '智能排课'
      fab.innerHTML = ICON
      fab.addEventListener('click', () => toggle())
      document.body.appendChild(fab)
    }
    function isOpen() { return document.documentElement.hasAttribute(ACTIVE) }
    function toggle(force) {
      const panel = ensurePanel()
      if (!panel) { mountFab(); return }
      const column = panel.parentElement
      if (column) applyClearance(panel, column)
      const open = force ?? !isOpen()
      panel.dataset.open = open ? 'true' : 'false'
      if (open) document.documentElement.setAttribute(ACTIVE, '')
      else document.documentElement.removeAttribute(ACTIVE)
      document.querySelectorAll(`[${ENTRY}]`).forEach(el => el.setAttribute('data-active', open ? 'true' : 'false'))
    }
    function repair() {
      try {
        injectStyle()
        mountEntry()
        if (isOpen()) {
          const panel = ensurePanel()
          if (panel) panel.dataset.open = 'true'
          else mountFab()
        }
      } catch (error) {
        console.warn('[dsh-aiwish] mount failed:', error)
      }
    }
    let queued = false
    let observer
    function start() {
      if (typeof document === 'undefined') return
      injectStyle(); repair()
      observer = new MutationObserver(() => {
        if (queued) return
        queued = true
        requestAnimationFrame(() => { queued = false; repair() })
      })
      observer.observe(document.body, { childList: true, subtree: true })
      window.addEventListener('keydown', (event) => { if (event.key === 'Escape' && isOpen()) toggle(false) })
    }
    function apply(ctx) {
      try {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true })
        else start()
        ctx?.effect?.(() => () => {
          observer?.disconnect()
          document.querySelectorAll(`[${ENTRY}], [${PANEL}], [data-dsh-aw-fab]`).forEach(el => el.remove())
          document.documentElement.removeAttribute(ACTIVE)
        })
      } catch (error) {
        console.warn('[dsh-aiwish] client apply failed:', error)
      }
    }
    exports.apply = apply
    exports.inject = []
    exports.name = 'aiwish-timetable'
    return module.exports
  },
})

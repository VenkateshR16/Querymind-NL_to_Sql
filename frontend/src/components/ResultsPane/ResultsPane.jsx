import { useState, useEffect, useRef, useMemo } from "react"
import ChartView from "../Charts/ChartView"

// ─── CSS ──────────────────────────────────────────────────────────────────────
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Orbitron:wght@400;700;900&display=swap');

.qm-root *, .qm-root *::before, .qm-root *::after { box-sizing:border-box; margin:0; padding:0; }

.qm-root {
  width:100%; font-family:'Space Mono',monospace;
  background:#050810; border-radius:16px; overflow:hidden;
  position:relative; min-height:540px;
  border:1px solid rgba(0,255,200,0.15); color:#fff;
}

/* Background */
.qm-canvas { position:absolute; inset:0; pointer-events:none; z-index:0; }
.qm-grid-bg {
  position:absolute; inset:0; pointer-events:none; z-index:0;
  background-image:
    linear-gradient(rgba(0,255,180,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,255,180,0.04) 1px, transparent 1px);
  background-size:32px 32px;
  animation:qm-gridPulse 4s ease-in-out infinite;
}
@keyframes qm-gridPulse { 0%,100%{opacity:.4} 50%{opacity:1} }

.qm-scan-line {
  position:absolute; left:0; right:0; height:2px; pointer-events:none; z-index:2;
  background:linear-gradient(90deg,transparent,rgba(0,255,180,0.6),transparent);
  animation:qm-scanline 3s linear infinite;
}
@keyframes qm-scanline {
  0%{top:0;opacity:0} 5%{opacity:1} 95%{opacity:1} 100%{top:100%;opacity:0}
}

.qm-vignette {
  position:absolute; inset:0; pointer-events:none; z-index:1;
  background:radial-gradient(ellipse at 50% 50%,transparent 60%,rgba(0,0,0,0.5) 100%);
}

/* Inner */
.qm-inner { position:relative; z-index:3; display:flex; flex-direction:column; }

/* Toolbar */
.qm-toolbar {
  display:flex; align-items:center; gap:10px;
  padding:14px 16px; background:rgba(0,255,180,0.04);
  border-bottom:1px solid rgba(0,255,180,0.15);
  flex-wrap:wrap; backdrop-filter:blur(4px);
}
.qm-brand {
  font-family:'Orbitron',sans-serif; font-size:11px; font-weight:900;
  letter-spacing:3px; color:#00ffb4;
  text-shadow:0 0 12px rgba(0,255,180,0.8),0 0 30px rgba(0,255,180,0.4);
}

/* Tabs */
.qm-toggle {
  display:flex; gap:2px; background:rgba(0,0,0,0.4);
  border-radius:8px; padding:3px; border:1px solid rgba(0,255,180,0.15);
}
.qm-tab {
  padding:6px 14px; border-radius:6px; border:none; cursor:pointer;
  font-family:'Orbitron',sans-serif; font-size:9px; font-weight:700;
  letter-spacing:1px; background:transparent; color:rgba(0,255,180,0.4);
  transition:all 0.25s; display:flex; align-items:center; gap:6px;
}
.qm-tab.active {
  background:rgba(0,255,180,0.15); color:#00ffb4;
  box-shadow:0 0 16px rgba(0,255,180,0.2),inset 0 0 20px rgba(0,255,180,0.05);
}
.qm-tab-dot {
  width:6px; height:6px; border-radius:50%; background:currentColor; opacity:0.5;
}
.qm-tab.active .qm-tab-dot { opacity:1; animation:qm-pulse 1.5s infinite; }
@keyframes qm-pulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.4);opacity:0.6} }

/* Search */
.qm-search-wrap { position:relative; display:flex; align-items:center; }
.qm-search-icon { position:absolute; left:9px; font-size:11px; color:rgba(0,255,180,0.4); pointer-events:none; }
.qm-search {
  padding:7px 12px 7px 28px; background:rgba(0,0,0,0.5);
  border:1px solid rgba(0,255,180,0.2); border-radius:8px;
  color:#00ffb4; font-family:'Space Mono',monospace; font-size:10px;
  outline:none; transition:0.2s; min-width:180px;
}
.qm-search:focus { border-color:#00ffb4; box-shadow:0 0 12px rgba(0,255,180,0.2); }
.qm-search::placeholder { color:rgba(0,255,180,0.2); }

.qm-count { margin-left:auto; font-size:9px; color:#00ffb4; opacity:0.5; letter-spacing:2px; white-space:nowrap; }

/* Table */
.qm-table-wrap {
  overflow:auto; max-height:460px;
  scrollbar-width:thin; scrollbar-color:rgba(0,255,180,0.2) transparent;
}
.qm-table-wrap::-webkit-scrollbar { width:4px; height:4px; }
.qm-table-wrap::-webkit-scrollbar-thumb { background:rgba(0,255,180,0.2); border-radius:2px; }

.qm-table { width:100%; border-collapse:collapse; font-size:11px; }
.qm-table th {
  padding:11px 14px; text-align:left; background:rgba(0,18,26,0.95); color:#00ffb4;
  font-family:'Orbitron',sans-serif; font-size:9px; letter-spacing:1px;
  position:sticky; top:0; z-index:10; border-bottom:1px solid rgba(0,255,180,0.15);
  user-select:none; cursor:pointer; transition:background 0.2s; white-space:nowrap;
}
.qm-table th:hover { background:rgba(0,255,180,0.08); }
.qm-sort-icon { margin-left:5px; opacity:0.35; font-size:10px; }
.qm-table th.qm-sorted .qm-sort-icon { opacity:1; }

.qm-table td {
  padding:9px 14px; border-bottom:1px solid rgba(0,255,180,0.05);
  color:#c8e6dc; font-size:11px; max-width:220px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  transition:background 0.12s;
}
.qm-table tr:hover td { background:rgba(0,255,180,0.04); }
.qm-table tr:nth-child(even) td { background:rgba(0,255,180,0.015); }
.qm-table tr:nth-child(even):hover td { background:rgba(0,255,180,0.05); }

.qm-null {
  font-size:8px; color:rgba(255,100,100,0.5); letter-spacing:1px;
  background:rgba(255,0,0,0.06); border:1px solid rgba(255,0,0,0.1);
  border-radius:3px; padding:1px 5px;
}

/* Chart area */
.qm-chart-area { padding:16px; }

/* Empty */
.qm-empty {
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; height:300px; gap:14px;
}
.qm-empty-box {
  border:1px solid #00ffb4; padding:18px 36px; border-radius:4px;
  background:rgba(0,255,180,0.02); color:#00ffb4;
  font-family:'Orbitron',sans-serif; font-size:11px; letter-spacing:4px;
  animation:qm-flicker 2s infinite;
}
@keyframes qm-flicker { 0%,100%{opacity:1} 50%{opacity:0.5} }
.qm-empty-sub { font-size:8px; color:#1a3a2a; letter-spacing:3px; }

/* Status bar */
.qm-status {
  display:flex; align-items:center; gap:8px; padding:8px 16px;
  background:rgba(0,0,0,0.3); border-top:1px solid rgba(0,255,180,0.08);
  font-size:8px; color:rgba(0,255,180,0.3); letter-spacing:2px; flex-wrap:wrap;
}
.qm-status-dot {
  width:5px; height:5px; border-radius:50%; background:#00ffb4;
  animation:qm-pulse 2s infinite; flex-shrink:0;
}
.qm-status-pill {
  background:rgba(0,255,180,0.06); border:1px solid rgba(0,255,180,0.12);
  border-radius:4px; padding:2px 7px; color:rgba(0,255,180,0.4);
  font-size:7px; letter-spacing:1px;
}

/* Burst particle */
.qm-burst {
  position:fixed; width:4px; height:4px; border-radius:50%;
  pointer-events:none; z-index:9999;
  animation:qm-burst 0.6s ease-out forwards;
}
@keyframes qm-burst {
  0%{opacity:1;transform:scale(1)}
  100%{opacity:0;transform:translate(var(--bx),var(--by)) scale(0)}
}

/* Glitch */
.qm-glitch { animation:qm-glitchAnim 0.32s steps(2) forwards; }
@keyframes qm-glitchAnim {
  0%  {filter:hue-rotate(0deg)   brightness(1)}
  33% {filter:hue-rotate(90deg)  brightness(1.3) saturate(2)}
  66% {filter:hue-rotate(-90deg) brightness(0.8)}
  100%{filter:hue-rotate(0deg)   brightness(1)}
}
`

// ─── Particle Canvas ──────────────────────────────────────────────────────────
function ParticleCanvas() {
  const ref = useRef(null)
  useEffect(() => {
    const canvas = ref.current
    const ctx    = canvas.getContext("2d")
    const parent = canvas.parentElement
    const resize = () => { canvas.width = parent.offsetWidth; canvas.height = parent.offsetHeight }
    resize()
    const ro = new ResizeObserver(resize); ro.observe(parent)

    const pts = Array.from({ length:60 }, () => ({
      x:  Math.random() * 1000,
      y:  Math.random() * 1000,
      vx: (Math.random()-0.5)*0.35,
      vy: (Math.random()-0.5)*0.35,
      r:  Math.random()*1.2+0.4,
    }))

    let raf
    const draw = () => {
      ctx.clearRect(0,0,canvas.width,canvas.height)
      // dots
      ctx.fillStyle = "rgba(0,255,180,0.28)"
      pts.forEach(p => {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0 || p.x > canvas.width)  p.vx *= -1
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1
        ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fill()
      })
      // connection lines
      ctx.lineWidth = 0.5
      for (let i=0; i<pts.length; i++) {
        for (let j=i+1; j<pts.length; j++) {
          const d = Math.hypot(pts[i].x-pts[j].x, pts[i].y-pts[j].y)
          if (d < 110) {
            ctx.globalAlpha = (1-d/110)*0.25
            ctx.strokeStyle = "rgba(0,255,180,0.6)"
            ctx.beginPath()
            ctx.moveTo(pts[i].x,pts[i].y)
            ctx.lineTo(pts[j].x,pts[j].y)
            ctx.stroke()
          }
        }
      }
      ctx.globalAlpha = 1
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [])
  return <canvas ref={ref} className="qm-canvas"/>
}

// ─── ResultsPane ──────────────────────────────────────────────────────────────
export default function ResultsPane({ result, title="QUERYMIND" }) {
  const [view,      setView]      = useState("table")
  const [search,    setSearch]    = useState("")
  const [sortKey,   setSortKey]   = useState(null)
  const [sortDir,   setSortDir]   = useState("asc")
  const [glitching, setGlitching] = useState(false)
  const [clock,     setClock]     = useState("")
  const rootRef    = useRef(null)
  const prevResult = useRef(null)

  // Inject CSS once
  useEffect(() => {
    if (!document.getElementById("qm-styles")) {
      const el = document.createElement("style")
      el.id = "qm-styles"; el.textContent = CSS
      document.head.appendChild(el)
    }
  }, [])

  // Live clock
  useEffect(() => {
    const tick = () => setClock(new Date().toISOString().slice(11,19))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  // Glitch on new result
  useEffect(() => {
    if (result && result !== prevResult.current) {
      prevResult.current = result
      setGlitching(true)
      setTimeout(() => setGlitching(false), 360)
    }
  }, [result])

  const rows    = useMemo(() => result?.rows ?? result?.data ?? [], [result])
  const columns = useMemo(() =>
    result?.columns ?? (rows[0] ? Object.keys(rows[0]) : []), [rows, result])

  const filteredRows = useMemo(() => {
    let list = rows
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(r =>
        Object.values(r).some(v => String(v).toLowerCase().includes(q)))
    }
    if (sortKey) {
      list = [...list].sort((a,b) => {
        const av = a[sortKey], bv = b[sortKey]
        if (av == null) return 1
        if (bv == null) return -1
        const cmp = typeof av === "number" && typeof bv === "number"
          ? av - bv : String(av).localeCompare(String(bv))
        return sortDir === "asc" ? cmp : -cmp
      })
    }
    return list
  }, [rows, search, sortKey, sortDir])

  const handleSort = col => {
    if (sortKey === col) setSortDir(d => d === "asc" ? "desc" : "asc")
    else { setSortKey(col); setSortDir("asc") }
  }

  const spawnBurst = (e, color="#00ffb4") => {
    const root = rootRef.current; if (!root) return
    const rr = root.getBoundingClientRect()
    const er = e.currentTarget.getBoundingClientRect()
    const cx = er.left - rr.left + er.width/2
    const cy = er.top  - rr.top  + er.height/2
    for (let i=0; i<12; i++) {
      const b = document.createElement("div")
      b.className = "qm-burst"
      b.style.cssText = `left:${cx}px;top:${cy}px;background:${color};`
      const ang = (i/12)*Math.PI*2
      b.style.setProperty("--bx", `${Math.cos(ang)*65}px`)
      b.style.setProperty("--by", `${Math.sin(ang)*65}px`)
      root.appendChild(b)
      setTimeout(() => b.remove(), 650)
    }
  }

  const switchView = (v, e, color) => {
    spawnBurst(e, color); setView(v)
  }

  const isEmpty = !rows.length

  const sortIcon = col =>
    sortKey === col ? (sortDir === "asc" ? "↑" : "↓") : "⇅"

  return (
    <div className={`qm-root${glitching ? " qm-glitch" : ""}`} ref={rootRef}>
      <div className="qm-grid-bg"/>
      <div className="qm-scan-line"/>
      <div className="qm-vignette"/>
      <ParticleCanvas/>

      <div className="qm-inner">

        {/* ── Toolbar ── */}
        <div className="qm-toolbar">
          <div className="qm-brand">{title}</div>

          <div className="qm-toggle">
            <button
              className={`qm-tab${view==="table"?" active":""}`}
              onClick={e => switchView("table", e, "#00ffb4")}>
              <div className="qm-tab-dot"/> DATA_STREAM
            </button>
            <button
              className={`qm-tab${view==="chart"?" active":""}`}
              onClick={e => switchView("chart", e, "#7b8fff")}>
              <div className="qm-tab-dot"/> ANALYTICS
            </button>
          </div>

          <div className="qm-search-wrap">
            <span className="qm-search-icon">⌕</span>
            <input
              className="qm-search"
              placeholder="FILTER_BUFFER..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="qm-count">
            {filteredRows.length}/{rows.length} RECORDS
          </div>
        </div>

        {/* ── Table view ── */}
        {view === "table" && (
          isEmpty ? (
            <div className="qm-empty">
              <div className="qm-empty-box">NO_DATA_STREAM</div>
              <div className="qm-empty-sub">AWAITING INPUT SIGNAL</div>
            </div>
          ) : (
            <div className="qm-table-wrap">
              <table className="qm-table">
                <thead>
                  <tr>
                    {columns.map(c => (
                      <th key={c}
                        className={sortKey===c ? "qm-sorted" : ""}
                        onClick={() => handleSort(c)}>
                        {c.toUpperCase()}
                        <span className="qm-sort-icon">{sortIcon(c)}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.slice(0,500).map((row,i) => (
                    <tr key={i}>
                      {columns.map(c => (
                        <td key={c} title={String(row[c])}>
                          {row[c] == null
                            ? <span className="qm-null">NULL</span>
                            : String(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {/* ── Chart view ── */}
        {view === "chart" && (
          isEmpty ? (
            <div className="qm-empty">
              <div className="qm-empty-box">VISUAL_ENGINE_READY</div>
              <div className="qm-empty-sub">NO DATA TO VISUALIZE</div>
            </div>
          ) : (
            <div className="qm-chart-area">
              <ChartView
                rows={filteredRows}
                chartHint={result?.chartHint}
              />
            </div>
          )
        )}

        {/* ── Status bar ── */}
        <div className="qm-status">
          <div className="qm-status-dot"/>
          <span>SYSTEM ONLINE</span>
          <span className="qm-status-pill">{view.toUpperCase()}_MODE</span>
          {sortKey && (
            <span className="qm-status-pill">
              SORT: {sortKey.toUpperCase()} {sortDir.toUpperCase()}
            </span>
          )}
          {search && (
            <span className="qm-status-pill">FILTER: "{search}"</span>
          )}
          {filteredRows.length < rows.length && (
            <span className="qm-status-pill">
              {rows.length - filteredRows.length} HIDDEN
            </span>
          )}
          <span style={{ marginLeft:"auto" }}>{clock} UTC</span>
        </div>

      </div>
    </div>
  )
}
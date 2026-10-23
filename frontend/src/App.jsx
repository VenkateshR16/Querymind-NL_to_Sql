import { useEffect, useRef, useState, useCallback } from 'react'
import { Toaster } from 'react-hot-toast'
import { AppProvider, useApp } from './store/AppStore'
import Sidebar from './components/Sidebar/Sidebar'
import QueryPage from './pages/QueryPage'
import HistoryPage from './pages/HistoryPage'
import SchemaPage from './pages/SchemaPage'
import SettingsPage from './pages/SettingsPage'
import { listTables, getHistStats } from './api/client'

/* ─────────────────────────────────────────────
   CINEMATIC INTRO
───────────────────────────────────────────── */
function QueryMindIntro({ onComplete }) {
  const canvasRef = useRef(null)
  const rafRef    = useRef(null)
  const [exiting, setExiting] = useState(false)

  /* Canvas particle / grid engine */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const stage = canvas.parentElement

    const resize = () => {
      canvas.width  = stage.offsetWidth
      canvas.height = stage.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const W = () => canvas.width
    const H = () => canvas.height

    const STARS = Array.from({ length: 150 }, () => ({
      x: Math.random(), y: Math.random(),
      r: 0.4 + Math.random() * 1.4,
      a: Math.random(),
      da: 0.002 + Math.random() * 0.006,
      hue: Math.random() < 0.65 ? '0,212,255' : '123,47,255',
    }))

    const PARTICLES = Array.from({ length: 36 }, () => ({
      x: Math.random(), y: Math.random() * 0.5 + 0.5,
      vx: (Math.random() - 0.5) * 0.0003,
      vy: -0.0004 - Math.random() * 0.001,
      r: 0.6 + Math.random() * 1.4,
      a: 0.35 + Math.random() * 0.65,
      hue: ['0,212,255', '123,47,255', '255,107,26'][Math.floor(Math.random() * 3)],
    }))

    let frame = 0

    const draw = () => {
      ctx.clearRect(0, 0, W(), H())
      ctx.fillStyle = '#050508'
      ctx.fillRect(0, 0, W(), H())

      // Drifting grid
      const gw = 28
      const drift = frame * 0.3
      ctx.strokeStyle = 'rgba(0,212,255,0.03)'
      ctx.lineWidth = 0.5
      for (let x = 0; x < W() + gw; x += gw) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H()); ctx.stroke()
      }
      for (let y = (drift % gw) - gw; y < H() + gw; y += gw) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W(), y); ctx.stroke()
      }

      // Stars
      STARS.forEach(s => {
        s.a += s.da
        if (s.a > 1 || s.a < 0) s.da *= -1
        ctx.beginPath()
        ctx.arc(s.x * W(), s.y * H(), s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${s.hue},${s.a})`
        ctx.fill()
      })

      // Floating particles
      PARTICLES.forEach(p => {
        p.x += p.vx; p.y += p.vy
        if (p.y < -0.02) { p.y = 1.02; p.x = Math.random() }
        if (p.x < 0 || p.x > 1) p.vx *= -1
        ctx.beginPath()
        ctx.arc(p.x * W(), p.y * H(), p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${p.hue},${p.a})`
        ctx.fill()
      })

      // Radial bloom (delayed)
      if (frame > 80) {
        const bloom = Math.min((frame - 80) / 60, 1)
        const g = ctx.createRadialGradient(
          W() / 2, H() / 2 - 60, 0,
          W() / 2, H() / 2,      Math.min(W(), H()) * 0.7
        )
        g.addColorStop(0, `rgba(0,212,255,${0.13 * bloom})`)
        g.addColorStop(0.5, `rgba(123,47,255,${0.05 * bloom})`)
        g.addColorStop(1, 'transparent')
        ctx.fillStyle = g
        ctx.fillRect(0, 0, W(), H())
      }

      frame++
      rafRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => {
      cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [])

  /* Counter animation */
  const animCount = useCallback((id, target, delay, dur) => {
    setTimeout(() => {
      const el = document.getElementById(id)
      if (!el) return
      const start = Date.now()
      const tick = () => {
        const p = Math.min((Date.now() - start) / dur, 1)
        const ease = 1 - Math.pow(1 - p, 3)
        el.textContent = Math.round(ease * target)
        if (p < 1) requestAnimationFrame(tick)
      }
      tick()
    }, delay)
  }, [])

  useEffect(() => {
    animCount('qmi-queries', 248, 3400, 900)
    animCount('qmi-tables',   12, 3500, 700)
    animCount('qmi-ms',      142, 3600, 700)

    // Auto-exit after 5.5s
    const t = setTimeout(handleExit, 5500)
    return () => clearTimeout(t)
  }, [])

  function handleExit() {
    setExiting(true)
    setTimeout(onComplete, 900)
  }

  const S = {
    wrap: {
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column',
      opacity: exiting ? 0 : 1,
      transform: exiting ? 'scale(1.04)' : 'scale(1)',
      transition: 'opacity 0.9s ease, transform 0.9s ease',
      pointerEvents: exiting ? 'none' : 'all',
    },
    scan: {
      position: 'absolute', left: 0, right: 0, height: 2,
      background: 'linear-gradient(90deg,transparent,rgba(0,212,255,0.7),rgba(123,47,255,0.7),transparent)',
      zIndex: 8, pointerEvents: 'none',
      animation: 'qmi-scan 4s linear 2s infinite',
    },
    logo: {
      position: 'relative', zIndex: 10,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      opacity: 0,
      animation: 'qmi-rise 0.9s cubic-bezier(0.16,1,0.3,1) 1.8s forwards',
    },
    orbWrap: {
      position: 'relative', width: 108, height: 108,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      marginBottom: 30,
    },
    core: {
      width: 58, height: 58, borderRadius: 14,
      background: 'rgba(0,212,255,0.06)',
      border: '1px solid rgba(0,212,255,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      position: 'relative', zIndex: 2,
      animation: 'qmi-core-pulse 2.5s ease-in-out 2.6s infinite',
    },
    title: {
      fontFamily: "'Orbitron', monospace",
      fontSize: 38, fontWeight: 900, color: '#ffffff',
      letterSpacing: '7px', textAlign: 'center', lineHeight: 1,
      margin: 0,
      animation: 'qmi-text-glow 2.5s ease-in-out 2.6s infinite',
    },
    divider: {
      height: 1, margin: '14px auto',
      background: 'linear-gradient(90deg,transparent,#00d4ff,#7b2fff,transparent)',
      boxShadow: '0 0 10px rgba(0,212,255,0.4)',
      width: 0,
      animation: 'qmi-expand 0.7s cubic-bezier(0.16,1,0.3,1) 2.5s forwards',
    },
    sub: {
      fontFamily: "'Rajdhani', sans-serif",
      fontSize: 11, fontWeight: 500, color: 'rgba(0,212,255,0.6)',
      letterSpacing: '6px', textTransform: 'uppercase', textAlign: 'center',
      margin: 0, opacity: 0,
      animation: 'qmi-fade-up 0.6s ease 3.1s forwards',
    },
    statsRow: {
      display: 'flex', alignItems: 'center', gap: 24, marginTop: 38,
      opacity: 0, animation: 'qmi-fade-up 0.6s ease 3.4s forwards',
    },
    statVal: {
      fontFamily: "'Orbitron', monospace",
      fontSize: 20, fontWeight: 700, color: '#e8f4ff',
      textShadow: '0 0 14px rgba(0,212,255,0.5)',
      display: 'block', textAlign: 'center',
    },
    statLbl: {
      fontFamily: "'Rajdhani', sans-serif",
      fontSize: 9, color: '#5a7090',
      letterSpacing: '2.5px', textTransform: 'uppercase',
      display: 'block', textAlign: 'center', marginTop: 2,
    },
    statDiv: { width: 1, height: 32, background: 'rgba(0,212,255,0.15)' },
    btn: {
      marginTop: 34, padding: '11px 36px',
      border: '1px solid rgba(0,212,255,0.35)',
      background: 'rgba(0,212,255,0.06)', borderRadius: 10,
      cursor: 'pointer',
      fontFamily: "'Rajdhani', sans-serif",
      fontSize: 12, fontWeight: 700,
      color: 'rgba(0,212,255,0.8)',
      letterSpacing: '4px', textTransform: 'uppercase',
      transition: 'all 0.3s',
      opacity: 0, animation: 'qmi-fade-up 0.5s ease 3.7s forwards',
    },
  }

  const rings = [
    { sz: 78,  bw: '1px',   color: 'rgba(0,212,255,0.45) transparent rgba(0,212,255,0.45) transparent', dur: '3s' },
    { sz: 94,  bw: '0.5px', color: 'transparent rgba(123,47,255,0.5) transparent rgba(123,47,255,0.5)', dur: '5s', rev: true },
    { sz: 108, bw: '0.5px', color: 'rgba(0,212,255,0.12) transparent rgba(255,107,26,0.28) transparent', dur: '9s' },
  ]

  const corners = [
    { id: 'tl', style: { top: 18, left: 18 }, delay: '1.2s' },
    { id: 'tr', style: { top: 18, right: 18 }, delay: '1.35s' },
    { id: 'bl', style: { bottom: 18, left: 18 }, delay: '1.5s' },
    { id: 'br', style: { bottom: 18, right: 18 }, delay: '1.65s' },
  ]

  return (
    <div style={S.wrap}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap');
        @keyframes qmi-rise     { from{opacity:0;transform:translateY(22px) scale(0.93);} to{opacity:1;transform:translateY(0) scale(1);} }
        @keyframes qmi-fade-up  { from{opacity:0;transform:translateY(7px);} to{opacity:1;transform:translateY(0);} }
        @keyframes qmi-expand   { from{width:0;} to{width:250px;} }
        @keyframes qmi-spin     { from{transform:rotate(0deg);} to{transform:rotate(360deg);} }
        @keyframes qmi-corner-in{ from{opacity:0;} to{opacity:1;} }
        @keyframes qmi-scan {
          from{top:-2px;opacity:0;} 5%{opacity:1;} 90%{opacity:0.5;} to{top:100%;opacity:0;}
        }
        @keyframes qmi-core-pulse {
          0%,100%{box-shadow:0 0 22px rgba(0,212,255,0.3),inset 0 0 14px rgba(0,212,255,0.08);}
          50%{box-shadow:0 0 55px rgba(0,212,255,0.65),0 0 90px rgba(123,47,255,0.35),inset 0 0 24px rgba(0,212,255,0.18);}
        }
        @keyframes qmi-text-glow {
          0%,100%{text-shadow:0 0 40px rgba(0,212,255,0.55),0 0 80px rgba(123,47,255,0.15);}
          50%{text-shadow:0 0 70px rgba(0,212,255,0.95),0 0 120px rgba(123,47,255,0.55),0 0 160px rgba(0,212,255,0.2);}
        }
        .qmi-enter-btn:hover{
          border-color:rgba(0,212,255,0.75) !important;
          background:rgba(0,212,255,0.14) !important;
          box-shadow:0 0 28px rgba(0,212,255,0.28) !important;
          color:#00d4ff !important;
        }
      `}</style>

      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* Scan line */}
      <div style={S.scan} aria-hidden="true" />

      {/* Corners */}
      {corners.map(c => (
        <div key={c.id} aria-hidden="true" style={{
          position: 'absolute', width: 20, height: 20, zIndex: 5,
          opacity: 0, animation: `qmi-corner-in 0.4s ease ${c.delay} forwards`,
          ...c.style,
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: 20, height: 1.5, background: '#00d4ff', boxShadow: '0 0 8px #00d4ff' }} />
          <div style={{ position: 'absolute', top: 0, left: 0, width: 1.5, height: 20, background: '#00d4ff', boxShadow: '0 0 8px #00d4ff' }} />
        </div>
      ))}

      {/* Logo block */}
      <div style={S.logo}>
        {/* Spinning rings + core orb */}
        <div style={S.orbWrap}>
          {rings.map((r, i) => (
            <div key={i} aria-hidden="true" style={{
              position: 'absolute', borderRadius: '50%',
              width: r.sz, height: r.sz,
              border: `${r.bw} solid`, borderColor: r.color,
              animation: `qmi-spin ${r.dur} linear infinite${r.rev ? ' reverse' : ''}`,
            }} />
          ))}
          <div style={S.core}>
            <svg width="30" height="30" viewBox="0 0 28 28" fill="none" style={{ filter: 'drop-shadow(0 0 8px #00d4ff)' }}>
              <polygon points="14,3 24,8.5 24,19.5 14,25 4,19.5 4,8.5"
                stroke="#00d4ff" strokeWidth="1.5" fill="rgba(0,212,255,0.08)" strokeLinejoin="round"/>
              <line x1="14" y1="3"  x2="14" y2="25"  stroke="#7b2fff" strokeWidth="0.8" opacity="0.7"/>
              <line x1="4"  y1="8.5" x2="24" y2="19.5" stroke="#7b2fff" strokeWidth="0.8" opacity="0.7"/>
              <line x1="24" y1="8.5" x2="4"  y2="19.5" stroke="#7b2fff" strokeWidth="0.8" opacity="0.7"/>
              <circle cx="14" cy="14" r="3"   fill="#00d4ff"/>
              <circle cx="14" cy="14" r="1.5" fill="#ffffff"/>
            </svg>
          </div>
        </div>

        <h1 style={S.title}>QUERYMIND</h1>
        <div style={S.divider} aria-hidden="true" />
        <p style={S.sub}>Intelligent Analytics Platform</p>

        {/* Counters */}
        <div style={S.statsRow}>
          {[
            { id: 'qmi-queries', label: 'Queries' },
            { id: 'qmi-tables',  label: 'Tables'  },
            { id: 'qmi-ms',      label: 'Avg ms'  },
          ].map((s, i) => (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
              {i > 0 && <div style={S.statDiv} aria-hidden="true" />}
              <div>
                <span id={s.id} style={S.statVal}>0</span>
                <span style={S.statLbl}>{s.label}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Enter */}
        <button className="qmi-enter-btn" onClick={handleExit} style={S.btn}>
          ENTER SYSTEM →
        </button>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   MAIN SHELL
───────────────────────────────────────────── */
function Shell() {
  const { state, dispatch } = useApp()

  useEffect(() => {
    listTables().then(r => {
      const tables = r.data.tables || []
      dispatch({ type: 'SET_TABLES', payload: tables })
      if (tables.length > 0 && !state.activeTable) {
        dispatch({ type: 'SET_ACTIVE_TABLE', payload: tables[0] })
      }
    }).catch(() => {})

    getHistStats().then(r => {
      dispatch({ type: 'SET_HIST_STATS', payload: r.data })
    }).catch(() => {})
  }, [])

  const pages = {
    query:    <QueryPage />,
    history:  <HistoryPage />,
    schema:   <SchemaPage />,
    settings: <SettingsPage />,
  }

  return (
    <div className="flex h-full bg-surface dot-grid">
      <Sidebar />
      <main className="flex-1 overflow-y-auto transition-all duration-300">
        <div className="max-w-7xl mx-auto p-6 animate-fade-in">
          {pages[state.page] || <QueryPage />}
        </div>
      </main>
    </div>
  )
}

/* ─────────────────────────────────────────────
   ROOT
───────────────────────────────────────────── */
export default function App() {
  const [introComplete, setIntroComplete] = useState(false)
  const [shellVisible,  setShellVisible]  = useState(false)

  function handleIntroComplete() {
    setIntroComplete(true)
    // Slight delay so shell fades in after intro fully exits
    setTimeout(() => setShellVisible(true), 100)
  }

  return (
    <AppProvider>
      {/* Intro — unmounts after complete */}
      {!introComplete && <QueryMindIntro onComplete={handleIntroComplete} />}

      {/* Shell — fades in after intro */}
      <div style={{
        opacity:    shellVisible ? 1 : 0,
        transform:  shellVisible ? 'scale(1)' : 'scale(0.98)',
        transition: 'opacity 0.8s ease, transform 0.8s ease',
        height:     '100%',
      }}>
        <Shell />
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#0d1017',
            color: '#e8f4ff',
            border: '1px solid rgba(0,212,255,0.15)',
            borderRadius: '12px',
            fontSize: '13px',
            fontFamily: "'Rajdhani', sans-serif",
            letterSpacing: '0.5px',
            boxShadow: '0 0 20px rgba(0,212,255,0.08)',
          },
          success: { iconTheme: { primary: '#00d4ff', secondary: '#0d1017' } },
          error:   { iconTheme: { primary: '#ff4444', secondary: '#0d1017' } },
        }}
      />
    </AppProvider>
  )
}
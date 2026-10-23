import { useState, useEffect, useRef } from 'react'
import {
  Brain, Clock, Table2, Settings,
  ChevronLeft, ChevronRight, Upload, Database,
  Zap, Link2, CheckSquare, Square
} from 'lucide-react'
import { useApp } from '../../store/AppStore'
import { uploadCSV, listTables, getSchema } from '../../api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const NAV = [
  { id: 'query',    label: 'Query',    icon: Brain },
  { id: 'history',  label: 'History',  icon: Clock },
  { id: 'schema',   label: 'Schema',   icon: Table2 },
  { id: 'settings', label: 'Settings', icon: Settings },
]

const PARTICLES = Array.from({ length: 14 }, (_, i) => ({
  id: i,
  left: `${Math.random() * 100}%`,
  color: ['#00d4ff','#7b2fff','#ff6b1a'][i % 3],
  duration: `${4 + Math.random() * 8}s`,
  delay: `${Math.random() * 8}s`,
  opacity: 0.3 + Math.random() * 0.5,
}))

export default function Sidebar() {
  const { state, dispatch } = useApp()
  const [uploading, setUploading] = useState(false)
  const [selectedTables, setSelected] = useState([])
  const { sidebarOpen: open } = state

  function setPage(p)  { dispatch({ type: 'SET_PAGE', payload: p }) }
  function toggle()    { dispatch({ type: 'SET_SIDEBAR', payload: !open }) }

  function toggleTable(t) {
    setSelected(prev => {
      const next = prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]
      if (next.length === 0) return prev
      dispatch({ type: 'SET_ACTIVE_TABLE', payload: next[0] })
      dispatch({ type: 'SET_ACTIVE_TABLES', payload: next })
      return next
    })
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    const fd = new FormData()
    fd.append('file', file)
    setUploading(true)
    const tid = toast.loading(`Uploading ${file.name}…`)
    try {
      const r = await uploadCSV(fd)
      const d = r.data
      toast.success(`Loaded ${d.row_count.toLocaleString()} rows × ${d.col_count} cols`, { id: tid })
      const tables = await listTables()
      const tList = tables.data.tables || []
      dispatch({ type: 'SET_TABLES', payload: tList })
      const newSelected = [...new Set([...selectedTables, d.table_name])]
      setSelected(newSelected)
      dispatch({ type: 'SET_ACTIVE_TABLE', payload: d.table_name })
      dispatch({ type: 'SET_ACTIVE_TABLES', payload: newSelected })
      const sc = await getSchema(d.table_name)
      dispatch({ type: 'SET_SCHEMA', payload: sc.data.columns })
      dispatch({ type: 'SET_TABLE_INFO', payload: { [d.table_name]: d } })
    } catch (err) {
      toast.error(err.message, { id: tid })
    } finally { setUploading(false) }
  }

  const tables = state.tables || []
  const active = selectedTables.length > 0
    ? selectedTables
    : (state.activeTable ? [state.activeTable] : [])

  return (
    <aside
      className={clsx(
        'relative flex flex-col h-full flex-shrink-0',
        'transition-all duration-300 ease-in-out overflow-hidden',
        open ? 'w-64' : 'w-16'
      )}
      style={{
        background: '#080a0f',
        borderRight: '1px solid rgba(0,212,255,0.12)',
        fontFamily: "'Rajdhani', sans-serif",
      }}
    >
      {/* — Inlined font imports — */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600&display=swap');

        @keyframes qm-grid-drift {
          from { background-position: 0 0; }
          to   { background-position: 0 28px; }
        }
        @keyframes qm-scan {
          from { top: -2px; opacity: 0; }
          5%   { opacity: 1; }
          95%  { opacity: 0.4; }
          to   { top: 100%; opacity: 0; }
        }
        @keyframes qm-orb-pulse {
          0%, 100% { box-shadow: 0 0 12px rgba(0,212,255,0.3), inset 0 0 10px rgba(0,212,255,0.1); }
          50%      { box-shadow: 0 0 28px rgba(0,212,255,0.6), 0 0 50px rgba(123,47,255,0.3), inset 0 0 18px rgba(0,212,255,0.2); }
        }
        @keyframes qm-shimmer {
          0%       { transform: translateX(-100%); }
          50%, 100%{ transform: translateX(100%); }
        }
        @keyframes qm-beam {
          0%, 100% { opacity: 0.5; transform: translateX(-50%) scaleX(1); }
          50%      { opacity: 1;   transform: translateX(-50%) scaleX(1.2); }
        }
        @keyframes qm-particle {
          from { transform: translateY(680px) scale(1); opacity: 0.8; }
          to   { transform: translateY(-20px) scale(0); opacity: 0; }
        }
        @keyframes qm-dot {
          0%, 100% { box-shadow: 0 0 8px #00d4ff; opacity: 1; }
          50%      { box-shadow: 0 0 3px #00d4ff; opacity: 0.3; }
        }
        @keyframes qm-fade-in {
          from { opacity: 0; transform: translateX(-6px); }
          to   { opacity: 1; transform: translateX(0); }
        }

        .qm-upload-btn::before {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(90deg, transparent, rgba(0,212,255,0.07), transparent);
          transform: translateX(-100%);
          animation: qm-shimmer 3.5s ease-in-out infinite;
          pointer-events: none;
        }
        .qm-corner::before, .qm-corner::after {
          content: '';
          position: absolute;
          background: #00d4ff;
          box-shadow: 0 0 8px #00d4ff;
        }
        .qm-corner::before { width: 100%; height: 2px; top: 0; left: 0; }
        .qm-corner::after  { width: 2px; height: 100%; top: 0; left: 0; }
      `}</style>

      {/* Background grid */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: 'linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px)',
          backgroundSize: '28px 28px',
          animation: 'qm-grid-drift 20s linear infinite',
        }}
      />

      {/* Volumetric beam */}
      {open && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute', top: -60, left: '50%',
            transform: 'translateX(-50%)',
            width: 200, height: 320, pointerEvents: 'none',
            background: 'conic-gradient(from 170deg at 50% 0%, transparent 0%, rgba(0,212,255,0.05) 20%, rgba(123,47,255,0.04) 50%, transparent 80%)',
            animation: 'qm-beam 4s ease-in-out infinite',
          }}
        />
      )}

      {/* Scan line */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute', left: 0, right: 0, height: 2,
          background: 'linear-gradient(90deg, transparent, rgba(0,212,255,0.6), rgba(123,47,255,0.6), transparent)',
          animation: 'qm-scan 6s linear infinite',
          zIndex: 20, pointerEvents: 'none',
        }}
      />

      {/* Corner brackets (only when open) */}
      {open && ['tl','tr','bl','br'].map(pos => (
        <div
          key={pos}
          className="qm-corner"
          aria-hidden="true"
          style={{
            position: 'absolute',
            width: 16, height: 16, zIndex: 21, pointerEvents: 'none',
            ...(pos === 'tl' ? { top: 10, left: 10 } : {}),
            ...(pos === 'tr' ? { top: 10, right: 10, transform: 'scaleX(-1)' } : {}),
            ...(pos === 'bl' ? { bottom: 10, left: 10, transform: 'scaleY(-1)' } : {}),
            ...(pos === 'br' ? { bottom: 10, right: 10, transform: 'scale(-1)' } : {}),
          }}
        />
      ))}

      {/* Floating particles */}
      {PARTICLES.map(p => (
        <div
          key={p.id}
          aria-hidden="true"
          style={{
            position: 'absolute', width: 2, height: 2,
            borderRadius: '50%',
            left: p.left,
            background: p.color,
            boxShadow: `0 0 4px ${p.color}`,
            opacity: p.opacity,
            animation: `qm-particle ${p.duration} ${p.delay} linear infinite`,
            pointerEvents: 'none', zIndex: 1,
          }}
        />
      ))}

      {/* ─── LOGO ─── */}
      <div
        style={{
          position: 'relative', zIndex: 5,
          display: 'flex', alignItems: 'center', gap: 12,
          padding: open ? '18px 16px 14px' : '18px 12px 14px',
          borderBottom: '1px solid rgba(0,212,255,0.1)',
        }}
      >
        {/* Orb */}
        <div
          style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: 'linear-gradient(135deg, rgba(0,212,255,0.12), rgba(123,47,255,0.12))',
            border: '1px solid rgba(0,212,255,0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            animation: 'qm-orb-pulse 3s ease-in-out infinite',
          }}
        >
          <Zap size={16} style={{ color: '#00d4ff', filter: 'drop-shadow(0 0 6px #00d4ff)' }} />
        </div>

        {open && (
          <div style={{ flex: 1, minWidth: 0, animation: 'qm-fade-in 0.3s ease' }}>
            <p style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: 12, fontWeight: 700, color: '#e8f4ff',
              letterSpacing: '2px', margin: 0,
              textShadow: '0 0 20px rgba(0,212,255,0.5)',
            }}>QueryMind</p>
            <p style={{
              fontSize: 8, color: '#5a7090', letterSpacing: '3px',
              textTransform: 'uppercase', margin: '2px 0 0',
            }}>Intelligent Analytics</p>
          </div>
        )}

        <button
          onClick={toggle}
          style={{
            marginLeft: 'auto', width: 28, height: 28, borderRadius: 8,
            border: '1px solid rgba(0,212,255,0.15)',
            background: 'rgba(0,212,255,0.05)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: '#00d4ff', transition: 'all 0.25s',
            flexShrink: 0,
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = '#00d4ff'
            e.currentTarget.style.boxShadow = '0 0 14px rgba(0,212,255,0.35)'
            e.currentTarget.style.background = 'rgba(0,212,255,0.12)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'rgba(0,212,255,0.15)'
            e.currentTarget.style.boxShadow = 'none'
            e.currentTarget.style.background = 'rgba(0,212,255,0.05)'
          }}
          aria-label="Toggle sidebar"
        >
          {open ? <ChevronLeft size={13} /> : <ChevronRight size={13} />}
        </button>
      </div>

      {/* ─── UPLOAD ─── */}
      <div style={{ position: 'relative', zIndex: 5, padding: '10px 12px', borderBottom: '1px solid rgba(0,212,255,0.1)' }}>
        <label
          className="qm-upload-btn"
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '9px 12px', borderRadius: 12,
            border: '1px dashed rgba(0,212,255,0.28)',
            background: 'rgba(0,212,255,0.04)',
            cursor: uploading ? 'not-allowed' : 'pointer',
            opacity: uploading ? 0.5 : 1,
            position: 'relative', overflow: 'hidden',
            transition: 'all 0.3s',
          }}
          onMouseEnter={e => {
            if (!uploading) {
              e.currentTarget.style.borderColor = 'rgba(0,212,255,0.55)'
              e.currentTarget.style.background = 'rgba(0,212,255,0.1)'
              e.currentTarget.style.boxShadow = '0 0 18px rgba(0,212,255,0.15)'
            }
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'rgba(0,212,255,0.28)'
            e.currentTarget.style.background = 'rgba(0,212,255,0.04)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <Upload
            size={14}
            style={{ color: '#00d4ff', filter: 'drop-shadow(0 0 5px #00d4ff)', flexShrink: 0 }}
          />
          {open && (
            <span style={{
              fontSize: 10, fontWeight: 600, color: 'rgba(0,212,255,0.8)',
              letterSpacing: '1.5px', textTransform: 'uppercase',
              animation: 'qm-fade-in 0.3s ease',
            }}>
              {uploading ? 'Uploading…' : 'Upload CSV / TSV'}
            </span>
          )}
          <input
            type="file"
            accept=".csv,.tsv,.txt"
            className="hidden"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {/* ─── DATASETS ─── */}
      {tables.length > 0 && (
        <div style={{ position: 'relative', zIndex: 5, padding: '10px 12px', borderBottom: '1px solid rgba(0,212,255,0.1)' }}>
          {open && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, padding: '0 2px' }}>
              <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 7, fontWeight: 600, letterSpacing: '3px', textTransform: 'uppercase', color: '#2a3a50' }}>
                Datasets
              </span>
              {active.length > 1 && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '2px 8px', borderRadius: 20,
                  background: 'rgba(123,47,255,0.18)',
                  border: '1px solid rgba(123,47,255,0.4)',
                  boxShadow: '0 0 10px rgba(123,47,255,0.2)',
                }}>
                  <Link2 size={8} style={{ color: '#a78bff' }} />
                  <span style={{ fontSize: 8, color: '#a78bff', fontWeight: 600, letterSpacing: '0.5px' }}>
                    {active.length} joined
                  </span>
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {tables.map(t => {
              const isActive = active.includes(t)
              return (
                <button
                  key={t}
                  onClick={() => toggleTable(t)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: open ? '7px 12px' : '7px',
                    justifyContent: open ? 'flex-start' : 'center',
                    borderRadius: 10, cursor: 'pointer', width: '100%', textAlign: 'left',
                    transition: 'all 0.25s',
                    background: isActive ? 'rgba(0,212,255,0.07)' : 'transparent',
                    border: isActive ? '1px solid rgba(0,212,255,0.22)' : '1px solid transparent',
                    boxShadow: isActive ? '0 0 14px rgba(0,212,255,0.08), inset 0 0 10px rgba(0,212,255,0.04)' : 'none',
                    position: 'relative', overflow: 'hidden',
                  }}
                >
                  {/* Active left bar */}
                  {isActive && (
                    <div style={{
                      position: 'absolute', left: 0, top: 0, bottom: 0, width: 2,
                      background: 'linear-gradient(180deg, #00d4ff, #7b2fff)',
                      boxShadow: '0 0 8px #00d4ff',
                    }} />
                  )}
                  {open ? (
                    isActive
                      ? <CheckSquare size={13} style={{ color: '#00d4ff', filter: 'drop-shadow(0 0 4px #00d4ff)', flexShrink: 0 }} />
                      : <Square size={13} style={{ color: '#2a3a50', flexShrink: 0 }} />
                  ) : (
                    <Database size={13} style={{ color: isActive ? '#00d4ff' : '#2a3a50', filter: isActive ? 'drop-shadow(0 0 4px #00d4ff)' : 'none' }} />
                  )}
                  {open && (
                    <span style={{
                      fontSize: 10, fontWeight: 400, letterSpacing: '0.5px',
                      color: isActive ? '#00d4ff' : '#5a7090',
                      textShadow: isActive ? '0 0 10px rgba(0,212,255,0.4)' : 'none',
                      animation: 'qm-fade-in 0.3s ease',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {t}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {open && active.length > 1 && (
            <div style={{
              marginTop: 8, padding: '8px 10px', borderRadius: 10,
              background: 'rgba(123,47,255,0.07)',
              border: '1px solid rgba(123,47,255,0.2)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                <Link2 size={8} style={{ color: '#a78bff' }} />
                <span style={{ fontSize: 8, color: '#a78bff', fontWeight: 600, letterSpacing: '1px', fontFamily: "'Orbitron',monospace" }}>
                  JOIN MODE ACTIVE
                </span>
              </div>
              <p style={{ fontSize: 9, color: '#4a3070', lineHeight: 1.4 }}>
                Queries will auto-JOIN: {active.join(' + ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ─── NAV ─── */}
      <nav style={{ position: 'relative', zIndex: 5, flex: 1, padding: '10px 12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {open && (
          <p style={{ fontFamily: "'Orbitron',monospace", fontSize: 7, letterSpacing: '3px', color: '#2a3a50', padding: '0 2px', marginBottom: 6, textTransform: 'uppercase' }}>
            Navigation
          </p>
        )}
        {NAV.map(({ id, label, icon: Icon }) => {
          const isActive = state.page === id
          return (
            <button
              key={id}
              onClick={() => setPage(id)}
              style={{
                display: 'flex', alignItems: 'center',
                gap: open ? 12 : 0, justifyContent: open ? 'flex-start' : 'center',
                padding: open ? '9px 12px' : '9px',
                borderRadius: 10, cursor: 'pointer', width: '100%', textAlign: 'left',
                transition: 'all 0.25s',
                background: isActive ? 'rgba(0,212,255,0.07)' : 'transparent',
                border: isActive ? '1px solid rgba(0,212,255,0.18)' : '1px solid transparent',
                position: 'relative',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.025)' }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
            >
              <Icon
                size={15}
                style={{
                  flexShrink: 0,
                  color: isActive ? '#00d4ff' : '#5a7090',
                  filter: isActive ? 'drop-shadow(0 0 5px #00d4ff)' : 'none',
                }}
              />
              {open && (
                <span style={{
                  fontSize: 11, fontWeight: 600, letterSpacing: '1.5px',
                  textTransform: 'uppercase', color: isActive ? '#e8f4ff' : '#5a7090',
                  animation: 'qm-fade-in 0.3s ease',
                }}>
                  {label}
                </span>
              )}
              {/* Active pulse dot */}
              {isActive && open && (
                <div style={{
                  position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                  width: 4, height: 4, borderRadius: '50%',
                  background: '#00d4ff', animation: 'qm-dot 2s ease-in-out infinite',
                }} />
              )}
            </button>
          )
        })}
      </nav>

      {/* ─── STATS FOOTER ─── */}
      {open && state.histStats && (
        <div style={{
          position: 'relative', zIndex: 5, padding: '12px 14px',
          borderTop: '1px solid rgba(0,212,255,0.1)',
          animation: 'qm-fade-in 0.4s ease',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            {[
              { label: 'Queries', val: state.histStats.total },
              { label: 'Success', val: state.histStats.success },
              { label: 'Avg ms',  val: state.histStats.avg_ms },
            ].map(({ label, val }) => (
              <div
                key={label}
                style={{
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(0,212,255,0.1)',
                  borderRadius: 8, padding: '8px 4px', textAlign: 'center',
                  transition: 'all 0.3s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,212,255,0.3)'
                  e.currentTarget.style.boxShadow = '0 0 12px rgba(0,212,255,0.1)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,212,255,0.1)'
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <span style={{
                  display: 'block',
                  fontFamily: "'Orbitron', monospace",
                  fontSize: 14, fontWeight: 700, color: '#e8f4ff',
                  textShadow: '0 0 12px rgba(0,212,255,0.5)',
                }}>
                  {val}
                </span>
                <span style={{ display: 'block', fontSize: 7, color: '#5a7090', letterSpacing: '2px', textTransform: 'uppercase', marginTop: 2 }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
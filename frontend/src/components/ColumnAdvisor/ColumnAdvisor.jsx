import { useState, useEffect } from 'react'
import { Sparkles, TrendingUp, Database, Hash, Calendar, ToggleLeft, Type, Zap } from 'lucide-react'
import clsx from 'clsx'

// ── Type system ───────────────────────────────────────────────────────────────
const TYPE_CONFIG = {
  INTEGER: { color: '#4cc9f0', bg: 'rgba(76,201,240,0.08)', border: 'rgba(76,201,240,0.2)',  icon: Hash,       label: 'INT'  },
  BIGINT:  { color: '#4cc9f0', bg: 'rgba(76,201,240,0.08)', border: 'rgba(76,201,240,0.2)',  icon: Hash,       label: 'BIG'  },
  DOUBLE:  { color: '#bf00ff', bg: 'rgba(191,0,255,0.08)',  border: 'rgba(191,0,255,0.2)',   icon: TrendingUp, label: 'DBL'  },
  FLOAT:   { color: '#bf00ff', bg: 'rgba(191,0,255,0.08)',  border: 'rgba(191,0,255,0.2)',   icon: TrendingUp, label: 'FLT'  },
  VARCHAR: { color: '#ffbe0b', bg: 'rgba(255,190,11,0.08)', border: 'rgba(255,190,11,0.2)',  icon: Type,       label: 'STR'  },
  DATE:    { color: '#00ff94', bg: 'rgba(0,255,148,0.08)',  border: 'rgba(0,255,148,0.2)',   icon: Calendar,   label: 'DATE' },
  BOOLEAN: { color: '#ff006e', bg: 'rgba(255,0,110,0.08)',  border: 'rgba(255,0,110,0.2)',   icon: ToggleLeft, label: 'BOOL' },
  DEFAULT: { color: '#555',    bg: 'rgba(80,80,80,0.08)',   border: 'rgba(80,80,80,0.2)',    icon: Database,   label: 'COL'  },
}

function getTypeConfig(t) {
  const upper = t?.toUpperCase() || ''
  for (const [k, v] of Object.entries(TYPE_CONFIG)) {
    if (k !== 'DEFAULT' && upper.includes(k)) return v
  }
  return TYPE_CONFIG.DEFAULT
}

// ── Animated score bar ────────────────────────────────────────────────────────
function ScoreBar({ score, color, delay = 0 }) {
  const [width, setWidth] = useState(0)
  const pct = Math.min(100, Math.max(0, (score / 80) * 100))

  useEffect(() => {
    const t = setTimeout(() => setWidth(pct), delay + 100)
    return () => clearTimeout(t)
  }, [pct, delay])

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
      <div style={{
        flex: 1, height: 3,
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 99, overflow: 'hidden',
        position: 'relative',
      }}>
        {/* Track glow */}
        <div style={{
          position: 'absolute', inset: 0,
          background: `${color}15`,
          borderRadius: 99,
        }}/>
        {/* Fill bar */}
        <div style={{
          height: '100%',
          width: `${width}%`,
          borderRadius: 99,
          background: `linear-gradient(90deg, ${color}99, ${color})`,
          boxShadow: `0 0 8px ${color}`,
          transition: 'width 0.9s cubic-bezier(0.16, 1, 0.3, 1)',
          position: 'relative',
        }}>
          {/* Shimmer effect */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
            animation: 'shimmer 2s infinite',
            backgroundSize: '200% 100%',
          }}/>
        </div>
      </div>
      <span style={{
        fontSize: 9,
        color: color,
        fontFamily: "'Courier New', monospace",
        fontWeight: 700,
        minWidth: 28,
        textAlign: 'right',
        textShadow: `0 0 8px ${color}`,
      }}>
        {Math.round(pct)}%
      </span>
    </div>
  )
}

// ── Individual column card ────────────────────────────────────────────────────
function ColCard({ col, index }) {
  const [hovered, setHovered] = useState(false)
  const [mounted, setMounted] = useState(false)
  const cfg = getTypeConfig(col.type)
  const Icon = cfg.icon

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), index * 80)
    return () => clearTimeout(t)
  }, [index])

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        background: hovered ? cfg.bg : 'rgba(255,255,255,0.02)',
        border: `1px solid ${hovered ? cfg.border : 'rgba(255,255,255,0.05)'}`,
        borderRadius: 12,
        padding: '12px 14px',
        cursor: 'default',
        transition: 'all 0.25s ease',
        overflow: 'hidden',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0) scale(1)' : 'translateY(8px) scale(0.97)',
        boxShadow: hovered
          ? `0 0 20px ${cfg.color}15, inset 0 0 20px ${cfg.color}05`
          : '0 2px 8px rgba(0,0,0,0.3)',
      }}
    >
      {/* Corner accent */}
      <div style={{
        position: 'absolute', top: 0, right: 0,
        width: 0, height: 0,
        borderStyle: 'solid',
        borderWidth: '0 28px 28px 0',
        borderColor: `transparent ${cfg.color}20 transparent transparent`,
        transition: 'border-color 0.25s',
      }}/>

      {/* Top row: name + type badge */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <Icon size={12} style={{ color: cfg.color, flexShrink: 0,
            filter: hovered ? `drop-shadow(0 0 4px ${cfg.color})` : 'none',
            transition: 'filter 0.25s',
          }}/>
          <span style={{
            fontSize: 13, fontWeight: 600,
            color: hovered ? '#fff' : '#ccc',
            fontFamily: "'Courier New', monospace",
            letterSpacing: '-0.01em',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            transition: 'color 0.25s',
          }}>
            {col.name}
          </span>
        </div>

        {/* Type badge */}
        <div style={{
          flexShrink: 0,
          fontSize: 8, fontWeight: 800,
          letterSpacing: '0.1em',
          color: cfg.color,
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          borderRadius: 4,
          padding: '2px 6px',
          fontFamily: "'Courier New', monospace",
          textShadow: hovered ? `0 0 6px ${cfg.color}` : 'none',
          transition: 'text-shadow 0.25s',
        }}>
          {cfg.label}
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={col.score} color={cfg.color} delay={index * 80}/>

      {/* Reason text */}
      {col.reason && (
        <p style={{
          fontSize: 10,
          color: hovered ? '#777' : '#444',
          marginTop: 6,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          fontFamily: "'Courier New', monospace",
          transition: 'color 0.25s',
        }}>
          {col.reason}
        </p>
      )}

      {/* Hover glow sweep */}
      {hovered && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(ellipse at 50% 0%, ${cfg.color}08, transparent 70%)`,
          pointerEvents: 'none',
          borderRadius: 'inherit',
        }}/>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ColumnAdvisor({ recommendations }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50)
    return () => clearTimeout(t)
  }, [])

  if (!recommendations?.length) return null
  const top = recommendations.filter(r => r.score > 0).slice(0, 4)
  if (!top.length) return null

  const topScore = top[0]?.score || 0
  const topCfg   = getTypeConfig(top[0]?.type)

  return (
    <>
      {/* Shimmer keyframes */}
      <style>{`
        @keyframes shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(0.8); }
        }
        @keyframes header-glow {
          0%, 100% { text-shadow: 0 0 8px rgba(255,190,11,0.4); }
          50%       { text-shadow: 0 0 16px rgba(255,190,11,0.8), 0 0 32px rgba(255,190,11,0.2); }
        }
      `}</style>

      <div style={{
        position: 'relative',
        background: 'rgba(0,0,0,0.4)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 16,
        padding: 16,
        backdropFilter: 'blur(8px)',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(10px)',
        transition: 'opacity 0.4s ease, transform 0.4s ease',
        overflow: 'hidden',
      }}>

        {/* Background mesh */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: `radial-gradient(ellipse at 0% 0%, ${topCfg.color}06, transparent 60%),
                       radial-gradient(ellipse at 100% 100%, rgba(191,0,255,0.04), transparent 60%)`,
          borderRadius: 'inherit',
        }}/>

        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', marginBottom: 14,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Animated dot */}
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: '#ffbe0b',
              boxShadow: '0 0 8px #ffbe0b',
              animation: 'pulse-dot 2s ease-in-out infinite',
            }}/>
            <Sparkles size={13} style={{ color: '#ffbe0b' }}/>
            <span style={{
              fontSize: 10, fontWeight: 700,
              color: '#ffbe0b',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              fontFamily: "'Courier New', monospace",
              animation: 'header-glow 3s ease-in-out infinite',
            }}>
              Column Recommendations
            </span>
          </div>

          {/* Count badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 9, color: '#444',
            fontFamily: "'Courier New', monospace",
            letterSpacing: '0.06em',
          }}>
            <Zap size={9} style={{ color: '#333' }}/>
            {top.length} of {recommendations.length}
          </div>
        </div>

        {/* Cards grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 8,
        }}>
          {top.map((col, i) => (
            <ColCard key={col.name} col={col} index={i}/>
          ))}
        </div>

        {/* Bottom divider glow */}
        <div style={{
          height: 1, marginTop: 14,
          background: 'linear-gradient(90deg, transparent, rgba(255,190,11,0.15), rgba(191,0,255,0.15), transparent)',
        }}/>

        {/* Corner brackets */}
        {[
          { top: 0, left: 0,  borderTop: '1.5px solid rgba(255,190,11,0.3)', borderLeft: '1.5px solid rgba(255,190,11,0.3)' },
          { top: 0, right: 0, borderTop: '1.5px solid rgba(255,190,11,0.3)', borderRight: '1.5px solid rgba(255,190,11,0.3)' },
        ].map((s, i) => (
          <div key={i} style={{ position: 'absolute', width: 12, height: 12, pointerEvents: 'none', ...s }}/>
        ))}
      </div>
    </>
  )
}
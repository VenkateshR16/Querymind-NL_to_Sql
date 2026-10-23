import { useState, useRef, useEffect } from 'react'
import { Keyboard, Mic, Image, Code2, Send, Square, Loader2, Link2, Zap, ChevronRight } from 'lucide-react'
import { useApp } from '../../store/AppStore'
import { queryText, queryVoice, queryImage, queryDirect } from '../../api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const MODES = [
  { id: 'text',   label: 'Text',  icon: Keyboard, color: '#00f5ff' },
  { id: 'voice',  label: 'Voice', icon: Mic,       color: '#ff006e' },
  { id: 'image',  label: 'Image', icon: Image,     color: '#ffbe0b' },
  { id: 'direct', label: 'SQL',   icon: Code2,     color: '#00ff94' },
]

const SUGGESTIONS_SINGLE = [
  'Show me total sales by region',
  'Top 10 customers by revenue',
  'Count records grouped by category',
  'Average price per product type',
  'Records where value is greater than 1000',
]

const SUGGESTIONS_MULTI = [
  'Show total sales joined with customer details',
  'Count orders per customer from both tables',
  'Average order value by region',
  'Top 10 records by revenue across all tables',
  'Group by category and sum all amounts',
]

// ── Particle burst on submit ──────────────────────────────────────────────────
function ParticleBurst({ active }) {
  if (!active) return null
  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden', borderRadius: 'inherit' }}>
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: '50%', top: '50%',
          width: 4, height: 4,
          borderRadius: '50%',
          background: ['#00f5ff','#bf00ff','#ff006e','#00ff94','#ffbe0b'][i % 5],
          animation: `particle-${i} 0.6s ease-out forwards`,
          boxShadow: `0 0 6px currentColor`,
        }}/>
      ))}
    </div>
  )
}

// ── Waveform visualizer for voice ─────────────────────────────────────────────
function Waveform({ active, color = '#ff006e' }) {
  const bars = 20
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2, height: 36 }}>
      {Array.from({ length: bars }).map((_, i) => (
        <div key={i} style={{
          width: 3, borderRadius: 99,
          background: active ? color : 'rgba(255,255,255,0.06)',
          boxShadow: active ? `0 0 6px ${color}` : 'none',
          height: active
            ? `${Math.random() * 60 + 20}%`
            : `${10 + Math.sin(i * 0.5) * 8}%`,
          animation: active ? `wave ${0.4 + (i % 5) * 0.1}s ease-in-out infinite alternate` : 'none',
          animationDelay: `${i * 0.05}s`,
          transition: 'background 0.3s, box-shadow 0.3s',
        }}/>
      ))}
    </div>
  )
}

// ── Mode tab button ───────────────────────────────────────────────────────────
function ModeTab({ mode: m, active, onClick }) {
  const [hovered, setHovered] = useState(false)
  const Icon = m.icon
  return (
    <button
      onClick={() => onClick(m.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '8px 14px', borderRadius: 10,
        border: active
          ? `1px solid ${m.color}50`
          : hovered ? '1px solid rgba(255,255,255,0.08)' : '1px solid transparent',
        background: active
          ? `${m.color}12`
          : hovered ? 'rgba(255,255,255,0.03)' : 'transparent',
        color: active ? m.color : hovered ? '#aaa' : '#555',
        fontSize: 12, fontWeight: 600,
        letterSpacing: '0.04em',
        cursor: 'pointer',
        transition: 'all 0.2s',
        boxShadow: active ? `0 0 16px ${m.color}20` : 'none',
        fontFamily: "'Courier New', monospace",
        position: 'relative', overflow: 'hidden',
      }}
    >
      {active && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(ellipse at 50% 0%, ${m.color}15, transparent 70%)`,
          pointerEvents: 'none',
        }}/>
      )}
      <Icon size={13} style={{
        filter: active ? `drop-shadow(0 0 4px ${m.color})` : 'none',
        transition: 'filter 0.2s',
      }}/>
      {m.label}
    </button>
  )
}

// ── Suggestion pill ───────────────────────────────────────────────────────────
function SuggestionPill({ text, onClick }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={() => onClick(text)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '5px 10px', borderRadius: 99,
        border: hovered ? '1px solid rgba(0,245,255,0.25)' : '1px solid rgba(255,255,255,0.06)',
        background: hovered ? 'rgba(0,245,255,0.06)' : 'rgba(255,255,255,0.02)',
        color: hovered ? '#00f5ff' : '#555',
        fontSize: 11, cursor: 'pointer',
        transition: 'all 0.2s',
        fontFamily: "'Courier New', monospace",
        whiteSpace: 'nowrap',
        boxShadow: hovered ? '0 0 10px rgba(0,245,255,0.1)' : 'none',
      }}
    >
      <ChevronRight size={9} style={{ opacity: hovered ? 1 : 0.3 }}/>
      {text}
    </button>
  )
}

// ── Submit button ─────────────────────────────────────────────────────────────
function SubmitBtn({ loading, disabled, onClick, label, color = '#00f5ff' }) {
  const [hovered, setHovered] = useState(false)
  const [burst,   setBurst]   = useState(false)

  function handleClick() {
    if (disabled || loading) return
    setBurst(true)
    setTimeout(() => setBurst(false), 700)
    onClick()
  }

  return (
    <button
      onClick={handleClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      disabled={disabled || loading}
      style={{
        position: 'relative', overflow: 'hidden',
        width: '100%', padding: '12px 20px',
        borderRadius: 12, border: `1px solid ${disabled ? 'rgba(255,255,255,0.06)' : `${color}40`}`,
        background: disabled
          ? 'rgba(255,255,255,0.03)'
          : hovered
            ? `${color}20`
            : `${color}10`,
        color: disabled ? '#333' : hovered ? color : `${color}cc`,
        fontSize: 13, fontWeight: 700,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        fontFamily: "'Courier New', monospace",
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s',
        boxShadow: !disabled && hovered ? `0 0 24px ${color}25, inset 0 0 24px ${color}08` : 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      }}
    >
      {/* Shimmer on hover */}
      {hovered && !disabled && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `linear-gradient(90deg, transparent, ${color}15, transparent)`,
          animation: 'shimmer-btn 1s ease-in-out infinite',
          pointerEvents: 'none',
        }}/>
      )}
      <ParticleBurst active={burst}/>
      {loading
        ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }}/>
        : <Zap size={15} style={{ filter: !disabled ? `drop-shadow(0 0 4px ${color})` : 'none' }}/>
      }
      {loading ? 'Processing…' : label}
    </button>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function QueryInput({ onResult, activeTables = [] }) {
  const { state, dispatch } = useApp()
  const [question, setQuestion]   = useState('')
  const [loading,  setLoading]    = useState(false)
  const [recording, setRecording] = useState(false)
  const [recSecs,  setRecSecs]    = useState(0)
  const [dragOver, setDragOver]   = useState(false)
  const [focused,  setFocused]    = useState(false)
  const [mounted,  setMounted]    = useState(false)

  const mediaRef    = useRef(null)
  const streamRef   = useRef(null)
  const chunksRef   = useRef([])
  const timerRef    = useRef(null)
  const textAreaRef = useRef(null)

  useEffect(() => { setTimeout(() => setMounted(true), 60) }, [])

  const mode      = state.inputMode
  const setMode   = m => dispatch({ type: 'SET_INPUT_MODE', payload: m })
  const isMulti   = activeTables.length > 1
  const table     = activeTables[0] || state.activeTable
  const SUGGESTIONS = isMulti ? SUGGESTIONS_MULTI : SUGGESTIONS_SINGLE
  const activeMode = MODES.find(m => m.id === mode) || MODES[0]

  function buildPayload(q) {
    return isMulti
      ? { question: q, tables: activeTables }
      : { question: q, table_name: table }
  }

  async function handleTextSubmit() {
    if (!question.trim()) return
    if (!table && mode !== 'direct') { toast.error('Upload a dataset first'); return }
    setLoading(true)
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      let r
      if (mode === 'direct') {
        r = await queryDirect({ sql: question, table_name: table || 'direct' })
      } else {
        r = await queryText(buildPayload(question))
      }
      dispatch({ type: 'SET_RESULT', payload: r.data })
      dispatch({ type: 'SET_QUERY',  payload: question })
      onResult(r.data)
      toast.success(`${r.data.result?.row_count ?? 0} rows · ${r.data.result?.elapsed_ms ?? 0}ms`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }

  async function startRecording() {
    if (!table) { toast.error('Upload a dataset first'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = e => { if (e.data?.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        clearInterval(timerRef.current); setRecSecs(0)
        streamRef.current?.getTracks().forEach(t => t.stop())
        if (!chunksRef.current.length) { toast.error('No audio captured'); setLoading(false); return }
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const fd = new FormData()
        fd.append('audio', blob, 'recording.webm')
        isMulti ? fd.append('tables', activeTables.join(',')) : fd.append('table_name', table)
        setLoading(true)
        const tid = toast.loading('Transcribing…')
        try {
          const r = await queryVoice(fd)
          const q = r.data.question || r.data.transcription || ''
          setQuestion(q)
          dispatch({ type: 'SET_RESULT', payload: r.data })
          dispatch({ type: 'SET_QUERY',  payload: q })
          onResult(r.data)
          toast.success('Voice query complete', { id: tid })
        } catch (err) { toast.error(err.message, { id: tid }) }
        finally { setLoading(false) }
      }
      recorder.start(100); mediaRef.current = recorder
      setRecording(true); setRecSecs(0)
      timerRef.current = setInterval(() => setRecSecs(s => s + 1), 1000)
    } catch (err) {
      toast.error(err.name === 'NotAllowedError'
        ? 'Microphone denied — allow it in browser settings'
        : 'Mic error: ' + err.message)
    }
  }

  function stopRecording() {
    clearInterval(timerRef.current)
    try { if (mediaRef.current?.state === 'recording') mediaRef.current.stop() } catch {}
    try { streamRef.current?.getTracks().forEach(t => t.stop()) } catch {}
    setRecording(false)
  }

  async function handleImageFile(file) {
    if (!file || !table) { toast.error('Upload a dataset first'); return }
    const fd = new FormData()
    fd.append('image', file)
    isMulti ? fd.append('tables', activeTables.join(',')) : fd.append('table_name', table)
    setLoading(true)
    const tid = toast.loading('Extracting text…')
    try {
      const r = await queryImage(fd)
      setQuestion(r.data.extracted_text || r.data.question || '')
      dispatch({ type: 'SET_RESULT', payload: r.data })
      onResult(r.data)
      toast.success('Image query complete', { id: tid })
    } catch (err) { toast.error(err.message, { id: tid }) }
    finally { setLoading(false) }
  }

  const fmtSecs = s => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,'0')}`

  return (
    <>
      <style>{`
        @keyframes wave {
          from { transform: scaleY(0.4); }
          to   { transform: scaleY(1); }
        }
        @keyframes shimmer-btn {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes rec-pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255,0,110,0.4); }
          50%       { opacity: 0.7; box-shadow: 0 0 0 8px rgba(255,0,110,0); }
        }
        @keyframes border-glow {
          0%, 100% { opacity: 0.4; }
          50%       { opacity: 1; }
        }
        @keyframes scan {
          0%   { transform: translateY(-100%); }
          100% { transform: translateY(100vh); }
        }
      `}</style>

      <div style={{
        position: 'relative',
        background: 'rgba(0,0,0,0.55)',
        border: `1px solid ${focused ? `${activeMode.color}30` : 'rgba(255,255,255,0.06)'}`,
        borderRadius: 18,
        backdropFilter: 'blur(12px)',
        overflow: 'hidden',
        transition: 'all 0.3s ease',
        boxShadow: focused
          ? `0 0 0 1px ${activeMode.color}15, 0 8px 40px rgba(0,0,0,0.5), inset 0 0 40px ${activeMode.color}04`
          : '0 4px 24px rgba(0,0,0,0.4)',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(12px)',
      }}>

        {/* Scanline effect */}
        <div style={{
          position: 'absolute', left: 0, right: 0, height: 60,
          background: `linear-gradient(180deg, transparent, ${activeMode.color}06, transparent)`,
          animation: 'scan 4s linear infinite',
          pointerEvents: 'none', zIndex: 0,
        }}/>

        {/* Top accent line */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 1,
          background: `linear-gradient(90deg, transparent, ${activeMode.color}60, transparent)`,
          animation: 'border-glow 2s ease-in-out infinite',
        }}/>

        {/* Corner brackets */}
        {[
          { top: 0, left: 0, borderTop: `1.5px solid ${activeMode.color}40`, borderLeft: `1.5px solid ${activeMode.color}40` },
          { top: 0, right: 0, borderTop: `1.5px solid ${activeMode.color}40`, borderRight: `1.5px solid ${activeMode.color}40` },
          { bottom: 0, left: 0, borderBottom: `1.5px solid ${activeMode.color}40`, borderLeft: `1.5px solid ${activeMode.color}40` },
          { bottom: 0, right: 0, borderBottom: `1.5px solid ${activeMode.color}40`, borderRight: `1.5px solid ${activeMode.color}40` },
        ].map((s, i) => (
          <div key={i} style={{ position: 'absolute', width: 14, height: 14, pointerEvents: 'none', zIndex: 2, ...s }}/>
        ))}

        {/* ── Mode tabs ─────────────────────────────────────────────────────── */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          padding: '10px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
          position: 'relative', zIndex: 1,
        }}>
          {MODES.map(m => (
            <ModeTab key={m.id} mode={m} active={mode === m.id} onClick={setMode}/>
          ))}

          {/* Active table badge */}
          {activeTables.length > 0 && (
            <div style={{
              marginLeft: 'auto',
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 10px', borderRadius: 8,
              border: isMulti ? '1px solid rgba(0,245,255,0.2)' : '1px solid rgba(0,255,148,0.15)',
              background: isMulti ? 'rgba(0,245,255,0.06)' : 'rgba(0,255,148,0.05)',
              fontSize: 10,
              color: isMulti ? '#00f5ff' : '#00ff94',
              fontFamily: "'Courier New', monospace",
              letterSpacing: '0.05em',
            }}>
              {isMulti ? (
                <>
                  <Link2 size={10} style={{ filter: 'drop-shadow(0 0 4px #00f5ff)' }}/>
                  {activeTables.length} tables linked
                </>
              ) : (
                <>
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: '#00ff94',
                    boxShadow: '0 0 6px #00ff94',
                    animation: 'rec-pulse 2s ease-in-out infinite',
                  }}/>
                  {table}
                </>
              )}
            </div>
          )}
        </div>

        {/* ── Body ──────────────────────────────────────────────────────────── */}
        <div style={{ padding: '14px 14px 16px', position: 'relative', zIndex: 1 }}>

          {/* TEXT / SQL mode */}
          {(mode === 'text' || mode === 'direct') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ position: 'relative' }}>
                <textarea
                  ref={textAreaRef}
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleTextSubmit() }}
                  placeholder={
                    mode === 'direct'
                      ? 'SELECT * FROM table1 JOIN table2 ON table1.id = table2.id'
                      : isMulti
                        ? `Ask anything across ${activeTables.join(' + ')}…`
                        : 'Ask anything about your data in plain English…'
                  }
                  rows={3}
                  style={{
                    width: '100%', resize: 'none', boxSizing: 'border-box',
                    borderRadius: 12, padding: '12px 14px',
                    fontSize: 13,
                    fontFamily: mode === 'direct' ? "'Courier New', monospace" : 'inherit',
                    color: mode === 'direct' ? '#00ff94' : '#ddd',
                    background: 'rgba(255,255,255,0.03)',
                    border: `1px solid ${focused ? `${activeMode.color}35` : 'rgba(255,255,255,0.07)'}`,
                    outline: 'none',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                    boxShadow: focused
                      ? `0 0 0 3px ${activeMode.color}10, inset 0 0 20px ${activeMode.color}04`
                      : 'none',
                    lineHeight: 1.6,
                  }}
                />
                <div style={{
                  position: 'absolute', bottom: 10, right: 12,
                  fontSize: 9, color: 'rgba(255,255,255,0.12)',
                  fontFamily: "'Courier New', monospace",
                  letterSpacing: '0.06em',
                }}>
                  CTRL+ENTER
                </div>
              </div>

              {/* Suggestions */}
              {mode === 'text' && !question && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {SUGGESTIONS.map(s => (
                    <SuggestionPill key={s} text={s} onClick={setQuestion}/>
                  ))}
                </div>
              )}

              <SubmitBtn
                loading={loading}
                disabled={!question.trim()}
                onClick={handleTextSubmit}
                label={mode === 'direct' ? 'Execute SQL' : isMulti ? 'Run JOIN Query' : 'Run Query'}
                color={activeMode.color}
              />
            </div>
          )}

          {/* VOICE mode */}
          {mode === 'voice' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, paddingTop: 8 }}>

              {/* Status text */}
              <div style={{ textAlign: 'center' }}>
                {loading ? (
                  <p style={{ fontSize: 13, color: '#00f5ff', fontFamily: "'Courier New', monospace",
                    letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                    Transcribing voice…
                  </p>
                ) : recording ? (
                  <p style={{ fontSize: 13, color: '#ff006e', fontFamily: "'Courier New', monospace",
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    textShadow: '0 0 10px #ff006e' }}>
                    ● REC {fmtSecs(recSecs)}
                  </p>
                ) : (
                  <p style={{ fontSize: 12, color: '#555', fontFamily: "'Courier New', monospace" }}>
                    {table
                      ? isMulti ? `Querying: ${activeTables.join(' + ')}` : `Active: ${table}`
                      : 'Upload a dataset first'}
                  </p>
                )}
              </div>

              {/* Waveform */}
              <Waveform active={recording} color="#ff006e"/>

              {/* Buttons row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                {/* Start */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <button onClick={startRecording}
                    disabled={recording || loading || !table}
                    style={{
                      width: 72, height: 72, borderRadius: '50%',
                      border: recording || !table ? '2px solid rgba(255,255,255,0.06)' : '2px solid #00f5ff40',
                      background: recording || !table ? 'rgba(255,255,255,0.03)' : 'rgba(0,245,255,0.08)',
                      color: recording || !table ? '#333' : '#00f5ff',
                      cursor: recording || !table ? 'not-allowed' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all 0.2s',
                      boxShadow: !recording && table ? '0 0 20px rgba(0,245,255,0.15)' : 'none',
                    }}>
                    <Mic size={28} style={{
                      filter: !recording && table ? 'drop-shadow(0 0 6px #00f5ff)' : 'none'
                    }}/>
                  </button>
                  <span style={{ fontSize: 9, color: '#444', letterSpacing: '0.1em',
                    fontFamily: "'Courier New', monospace" }}>START</span>
                </div>

                {/* Stop */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <button onClick={stopRecording}
                    disabled={!recording || loading}
                    style={{
                      width: 72, height: 72, borderRadius: '50%',
                      border: recording ? '2px solid #ff006e60' : '2px solid rgba(255,255,255,0.06)',
                      background: recording ? 'rgba(255,0,110,0.12)' : 'rgba(255,255,255,0.03)',
                      color: recording ? '#ff006e' : '#333',
                      cursor: recording ? 'pointer' : 'not-allowed',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all 0.2s',
                      boxShadow: recording
                        ? '0 0 24px rgba(255,0,110,0.2), 0 0 0 0 rgba(255,0,110,0.4)'
                        : 'none',
                      animation: recording ? 'rec-pulse 1.5s ease-in-out infinite' : 'none',
                    }}>
                    <Square size={24} fill={recording ? '#ff006e' : '#333'}/>
                  </button>
                  <span style={{ fontSize: 9, color: recording ? '#ff006e' : '#444',
                    letterSpacing: '0.1em', fontFamily: "'Courier New', monospace",
                    textShadow: recording ? '0 0 8px #ff006e' : 'none',
                    transition: 'all 0.3s' }}>STOP</span>
                </div>
              </div>

              {/* Detected text */}
              {question && !recording && (
                <div style={{
                  width: '100%', borderRadius: 12, padding: '10px 14px',
                  background: 'rgba(0,245,255,0.04)',
                  border: '1px solid rgba(0,245,255,0.12)',
                }}>
                  <p style={{ fontSize: 9, color: '#00f5ff55', letterSpacing: '0.12em',
                    textTransform: 'uppercase', marginBottom: 4,
                    fontFamily: "'Courier New', monospace" }}>Detected</p>
                  <p style={{ fontSize: 13, color: '#ccc' }}>{question}</p>
                </div>
              )}

              {/* Instructions */}
              {!recording && !loading && !question && (
                <div style={{
                  width: '100%', borderRadius: 12, padding: '10px 14px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.04)',
                  fontSize: 11, color: '#444',
                  fontFamily: "'Courier New', monospace",
                  lineHeight: 2,
                }}>
                  {['1. Click START and allow microphone',
                    '2. Speak your query clearly',
                    '3. Click STOP when done',
                    '4. Results appear automatically',
                  ].map((t, i) => (
                    <div key={i}>{t}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* IMAGE mode */}
          {mode === 'image' && (
            <div
              onDrop={e => { e.preventDefault(); setDragOver(false); handleImageFile(e.dataTransfer.files?.[0]) }}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              style={{
                border: `2px dashed ${dragOver ? '#ffbe0b60' : 'rgba(255,255,255,0.07)'}`,
                borderRadius: 14, padding: '36px 20px',
                textAlign: 'center',
                background: dragOver ? 'rgba(255,190,11,0.05)' : 'rgba(255,255,255,0.01)',
                transition: 'all 0.2s',
                boxShadow: dragOver ? '0 0 30px rgba(255,190,11,0.1), inset 0 0 30px rgba(255,190,11,0.04)' : 'none',
              }}
            >
              <label style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 16,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: dragOver ? 'rgba(255,190,11,0.12)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${dragOver ? 'rgba(255,190,11,0.3)' : 'rgba(255,255,255,0.08)'}`,
                  transition: 'all 0.2s',
                }}>
                  {loading
                    ? <Loader2 size={22} style={{ color: '#ffbe0b', animation: 'spin 1s linear infinite' }}/>
                    : <Image size={22} style={{
                        color: dragOver ? '#ffbe0b' : '#555',
                        filter: dragOver ? 'drop-shadow(0 0 8px #ffbe0b)' : 'none',
                        transition: 'all 0.2s',
                      }}/>
                  }
                </div>
                <div>
                  <p style={{ fontSize: 13, color: dragOver ? '#ffbe0b' : '#888',
                    fontWeight: 600, marginBottom: 4,
                    textShadow: dragOver ? '0 0 10px #ffbe0b' : 'none',
                    transition: 'all 0.2s' }}>
                    {dragOver ? 'Drop image here' : 'Upload or drag an image'}
                  </p>
                  <p style={{ fontSize: 11, color: '#444',
                    fontFamily: "'Courier New', monospace" }}>
                    PNG · JPG — containing your query as text
                  </p>
                </div>
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={e => handleImageFile(e.target.files?.[0])}/>
              </label>
            </div>
          )}

        </div>
      </div>
    </>
  )
}
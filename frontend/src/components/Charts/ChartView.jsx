import { useState, useEffect, useMemo } from "react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, RadialLinearScale,
  BarElement, LineElement, PointElement, ArcElement,
  Filler, Title, Tooltip, Legend,
} from "chart.js"
import { Bar, Line, Pie, Doughnut, Radar, PolarArea, Bubble, Scatter } from "react-chartjs-2"

ChartJS.register(
  CategoryScale, LinearScale, RadialLinearScale,
  BarElement, LineElement, PointElement, ArcElement,
  Filler, Title, Tooltip, Legend
)

// ── Palette ───────────────────────────────────────────────────────────────────
const P = [
  "#00f5ff","#bf00ff","#ff006e","#ffbe0b","#00ff94",
  "#ff4d6d","#4cc9f0","#f72585","#7209b7","#3ddc97",
]

const TYPES = [
  { id:"bar",     label:"Bar",     icon:"▊" },
  { id:"line",    label:"Line",    icon:"∿" },
  { id:"area",    label:"Area",    icon:"◿" },
  { id:"pie",     label:"Pie",     icon:"◕" },
  { id:"donut",   label:"Donut",   icon:"⊙" },
  { id:"radar",   label:"Radar",   icon:"⬡" },
  { id:"polar",   label:"Polar",   icon:"◎" },
  { id:"bubble",  label:"Bubble",  icon:"⊚" },
  { id:"scatter", label:"Scatter", icon:"⁙" },
  { id:"heatmap", label:"Heatmap", icon:"▦" },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt = v =>
  typeof v !== "number" ? v
  : v >= 1e9 ? `${(v/1e9).toFixed(1)}B`
  : v >= 1e6 ? `${(v/1e6).toFixed(1)}M`
  : v >= 1e3 ? `${(v/1e3).toFixed(1)}K`
  : Number.isInteger(v) ? v.toLocaleString()
  : v.toFixed(2)

const fv = (r, k) => parseFloat(r[k]) || 0

function getKeys(rows) {
  if (!rows?.length) return { strK:[], numK:[] }
  const keys = Object.keys(rows[0])
  const numK = keys.filter(k =>
    rows[0][k] !== null && rows[0][k] !== "" && !isNaN(parseFloat(rows[0][k]))
  )
  const strK = keys.filter(k => !numK.includes(k))
  return { strK, numK }
}

function autoDetect(rows, hint) {
  if (hint?.type && !["none","table"].includes(hint.type)) return hint.type
  if (!rows?.length) return "bar"
  const { numK } = getKeys(rows)
  if (rows.length <= 7 && numK.length >= 3) return "radar"
  if (rows.length > 30) return "area"
  return "bar"
}

function computeStats(rows, numK) {
  if (!numK.length) return []
  const k = numK[0]
  const nums = rows.map(r => fv(r, k))
  const sum  = nums.reduce((a,b) => a+b, 0)
  return [
    { label:"Total",   value:sum,              color:"#00f5ff" },
    { label:"Average", value:sum/nums.length,  color:"#bf00ff" },
    { label:"Max",     value:Math.max(...nums), color:"#00ff94" },
    { label:"Min",     value:Math.min(...nums), color:"#ff006e" },
    { label:"Rows",    value:rows.length,       color:"#ffbe0b" },
  ]
}

// ── Chart.js base options ─────────────────────────────────────────────────────
const baseOpts = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration:700 },
  plugins: {
    legend: { labels:{ color:"#666", font:{ family:"monospace", size:10 }, boxWidth:10, padding:10 } },
    tooltip: {
      backgroundColor:"rgba(0,0,0,0.88)", borderColor:"rgba(0,245,255,0.3)",
      borderWidth:1, titleColor:"#00f5ff", bodyColor:"#ccc",
      titleFont:{ family:"monospace", size:10 }, bodyFont:{ family:"monospace", size:11 }, padding:10,
    },
  },
  scales: {
    x: { ticks:{ color:"#555", font:{ family:"monospace", size:10 }, maxRotation:35 }, grid:{ color:"rgba(255,255,255,0.05)" } },
    y: { ticks:{ color:"#555", font:{ family:"monospace", size:10 }, callback:fmt },   grid:{ color:"rgba(255,255,255,0.05)" } },
  },
}

const noScaleOpts = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration:700 },
  plugins: {
    legend: { labels:{ color:"#666", font:{ family:"monospace", size:10 }, boxWidth:10, padding:10 } },
    tooltip: {
      backgroundColor:"rgba(0,0,0,0.88)", borderColor:"rgba(0,245,255,0.3)",
      borderWidth:1, titleColor:"#00f5ff", bodyColor:"#ccc",
      titleFont:{ family:"monospace", size:10 }, bodyFont:{ family:"monospace", size:11 }, padding:10,
    },
  },
}

const radarOpts = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration:700 },
  plugins: {
    legend: { labels:{ color:"#666", font:{ family:"monospace", size:10 }, boxWidth:10, padding:10 } },
    tooltip: {
      backgroundColor:"rgba(0,0,0,0.88)", borderColor:"rgba(0,245,255,0.3)",
      borderWidth:1, titleColor:"#00f5ff", bodyColor:"#ccc",
    },
  },
  scales: {
    r: {
      ticks:{ color:"#444", backdropColor:"transparent", font:{ family:"monospace", size:9 } },
      grid:{ color:"rgba(255,255,255,0.07)" },
      pointLabels:{ color:"#555", font:{ family:"monospace", size:10 } },
    },
  },
}

// ── Chart renderer ────────────────────────────────────────────────────────────
function RenderChart({ type, data, strK, numK }) {
  const labelKey = strK[0] || Object.keys(data[0] || {})[0]
  const labels   = data.map(r => String(r[labelKey] ?? "").slice(0, 14))

  if (type === "bar") return (
    <Bar options={baseOpts} data={{
      labels,
      datasets:[{
        label: numK[0],
        data:  data.map(r => fv(r, numK[0])),
        backgroundColor: data.map((_,i) => P[i%P.length] + "99"),
        borderColor:     data.map((_,i) => P[i%P.length]),
        borderWidth:1, borderRadius:5,
      }],
    }}/>
  )

  if (type === "line") return (
    <Line options={baseOpts} data={{
      labels,
      datasets: numK.slice(0,4).map((k,i) => ({
        label: k,
        data:  data.map(r => fv(r, k)),
        borderColor: P[i], backgroundColor: P[i] + "22",
        borderWidth:2, pointRadius:3, tension:0.3,
      })),
    }}/>
  )

  if (type === "area") return (
    <Line options={baseOpts} data={{
      labels,
      datasets: numK.slice(0,4).map((k,i) => ({
        label: k,
        data:  data.map(r => fv(r, k)),
        borderColor: P[i], backgroundColor: P[i] + "33",
        borderWidth:2, fill:true, tension:0.4, pointRadius:2,
      })),
    }}/>
  )

  if (type === "pie") return (
    <Pie options={noScaleOpts} data={{
      labels,
      datasets:[{
        data: data.map(r => fv(r, numK[0])),
        backgroundColor: data.map((_,i) => P[i%P.length] + "bb"),
        borderColor:     data.map((_,i) => P[i%P.length]),
        borderWidth:1, hoverOffset:8,
      }],
    }}/>
  )

  if (type === "donut") return (
    <Doughnut options={noScaleOpts} data={{
      labels,
      datasets:[{
        data: data.map(r => fv(r, numK[0])),
        backgroundColor: data.map((_,i) => P[i%P.length] + "bb"),
        borderColor:     data.map((_,i) => P[i%P.length]),
        borderWidth:1, hoverOffset:10,
      }],
    }}/>
  )

  if (type === "radar") return (
    <Radar options={radarOpts} data={{
      labels,
      datasets: numK.slice(0,4).map((k,i) => ({
        label: k,
        data:  data.map(r => fv(r, k)),
        borderColor: P[i], backgroundColor: P[i] + "22",
        borderWidth:2, pointRadius:3, pointBackgroundColor: P[i],
      })),
    }}/>
  )

  if (type === "polar") return (
    <PolarArea
      options={{
        ...noScaleOpts,
        scales:{ r:{ ticks:{ color:"#444", backdropColor:"transparent" }, grid:{ color:"rgba(255,255,255,0.07)" } } },
      }}
      data={{
        labels,
        datasets:[{
          data: data.map(r => fv(r, numK[0])),
          backgroundColor: data.map((_,i) => P[i%P.length] + "99"),
          borderColor:     data.map((_,i) => P[i%P.length]),
          borderWidth:1,
        }],
      }}
    />
  )

  if (type === "bubble") {
    const rMax = Math.max(...data.map(r => fv(r, numK[2] || numK[0]))) || 1
    return (
      <Bubble options={baseOpts} data={{
        datasets:[{
          label: "data",
          data: data.map(r => ({
            x: fv(r, numK[0]),
            y: fv(r, numK[1] || numK[0]),
            r: Math.max(4, fv(r, numK[2] || numK[0]) / rMax * 28),
          })),
          backgroundColor: data.map((_,i) => P[i%P.length] + "99"),
          borderColor:     data.map((_,i) => P[i%P.length]),
          borderWidth:1,
        }],
      }}/>
    )
  }

  if (type === "scatter") return (
    <Scatter options={baseOpts} data={{
      datasets:[{
        label: `${numK[0]} vs ${numK[1] || numK[0]}`,
        data: data.map(r => ({ x: fv(r, numK[0]), y: fv(r, numK[1] || numK[0]) })),
        backgroundColor: data.map((_,i) => P[i%P.length] + "cc"),
        borderColor:     data.map((_,i) => P[i%P.length]),
        pointRadius:5, pointHoverRadius:8,
      }],
    }}/>
  )

  return null
}

// ── Heatmap ───────────────────────────────────────────────────────────────────
function HeatmapChart({ data, strK, numK }) {
  const xKey = strK[0] || Object.keys(data[0] || {})[0]
  const keys = numK.slice(0, 7)
  if (!data.length || !keys.length) return null
  const all  = data.flatMap(r => keys.map(k => fv(r, k)))
  const minV = Math.min(...all), maxV = Math.max(...all)
  const norm = v => maxV === minV ? 0.5 : (v - minV) / (maxV - minV)
  const hc   = t =>
    t < 0.25 ? `rgba(50,0,255,${0.3+t*2})`
    : t < 0.5  ? `rgba(0,245,255,${0.5+t*0.6})`
    : t < 0.75 ? `rgba(0,255,148,${0.6+t*0.4})`
    : `rgba(255,0,110,${0.6+t*0.4})`
  return (
    <div style={{ overflowX:"auto", padding:"2px 0" }}>
      <div style={{ display:"flex", gap:2, marginBottom:3, paddingLeft:82 }}>
        {keys.map(k => (
          <div key={k} style={{ flex:1, minWidth:44, fontSize:8, color:"#444",
            textAlign:"center", textTransform:"uppercase",
            overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{k}</div>
        ))}
      </div>
      {data.slice(0,14).map((row,ri) => (
        <div key={ri} style={{ display:"flex", gap:2, marginBottom:2, alignItems:"center" }}>
          <div style={{ width:78, fontSize:9, color:"#555", textAlign:"right",
            paddingRight:5, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
            {String(row[xKey]).slice(0,11)}
          </div>
          {keys.map(k => {
            const v = fv(row, k), t = norm(v)
            return (
              <div key={k} title={`${row[xKey]} · ${k}: ${fmt(v)}`} style={{
                flex:1, minWidth:44, height:30, borderRadius:3, background:hc(t),
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:8, color:"rgba(255,255,255,0.9)", fontWeight:700,
              }}>{fmt(v)}</div>
            )
          })}
        </div>
      ))}
      <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:8, paddingLeft:82 }}>
        <span style={{ fontSize:8, color:"#333" }}>LOW</span>
        <div style={{ flex:1, height:5, borderRadius:3,
          background:"linear-gradient(90deg,rgba(50,0,255,0.6),rgba(0,245,255,0.8),rgba(0,255,148,0.8),rgba(255,0,110,0.9))" }}/>
        <span style={{ fontSize:8, color:"#333" }}>HIGH</span>
      </div>
    </div>
  )
}

// ── Animated stat ─────────────────────────────────────────────────────────────
function AnimatedStat({ value, label, color }) {
  const [d, setD] = useState(0)
  const isNum = typeof value === "number"
  useEffect(() => {
    if (!isNum) return
    let v = 0
    const inc = (value / 1200) * 16
    const t = setInterval(() => {
      v += inc
      if (v >= value) { setD(value); clearInterval(t) } else setD(v)
    }, 16)
    return () => clearInterval(t)
  }, [value, isNum])
  return (
    <div style={{ background:"rgba(255,255,255,0.03)", border:`1px solid ${color}33`,
      borderRadius:10, padding:"11px 14px", textAlign:"center",
      position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", inset:0,
        background:`radial-gradient(ellipse at 50% 0%,${color}12,transparent 70%)` }}/>
      <div style={{ fontSize:20, fontWeight:800, color, fontFamily:"monospace",
        textShadow:`0 0 10px ${color}` }}>{isNum ? fmt(d) : value}</div>
      <div style={{ fontSize:9, color:"#555", marginTop:3,
        textTransform:"uppercase", letterSpacing:"0.08em" }}>{label}</div>
    </div>
  )
}

// ── Corner deco ───────────────────────────────────────────────────────────────
const Corners = ({ c="#00f5ff" }) => (
  <>
    {[
      { top:0,    left:0,  borderTop:`1px solid ${c}`,    borderLeft:`1px solid ${c}` },
      { top:0,    right:0, borderTop:`1px solid ${c}`,    borderRight:`1px solid ${c}` },
      { bottom:0, left:0,  borderBottom:`1px solid ${c}`, borderLeft:`1px solid ${c}` },
      { bottom:0, right:0, borderBottom:`1px solid ${c}`, borderRight:`1px solid ${c}` },
    ].map((s,i) => (
      <div key={i} style={{ position:"absolute", width:13, height:13,
        pointerEvents:"none", zIndex:5, ...s }}/>
    ))}
  </>
)

const Scanline = () => (
  <div style={{ position:"absolute", inset:0, pointerEvents:"none", zIndex:4,
    backgroundImage:"repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.025) 2px,rgba(0,0,0,0.025) 4px)" }}/>
)

// ── Type button ───────────────────────────────────────────────────────────────
function TypeBtn({ chart, active, onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <button onClick={() => onClick(chart.id)}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display:"flex", flexDirection:"column", alignItems:"center", gap:3,
        padding:"6px 10px", borderRadius:7, cursor:"pointer",
        border: active ? "1px solid rgba(0,245,255,0.6)"
          : hov   ? "1px solid rgba(0,245,255,0.2)"
          : "1px solid rgba(255,255,255,0.06)",
        background: active ? "rgba(0,245,255,0.08)"
          : hov ? "rgba(255,255,255,0.03)" : "transparent",
        color: active ? "#00f5ff" : hov ? "#999" : "#444",
        transition:"all 0.18s",
        boxShadow: active ? "0 0 12px rgba(0,245,255,0.15)" : "none",
      }}>
      <span style={{ fontSize:15, lineHeight:1 }}>{chart.icon}</span>
      <span style={{ fontSize:8, letterSpacing:"0.07em",
        textTransform:"uppercase", fontWeight:600 }}>{chart.label}</span>
    </button>
  )
}

// ── View toggle ───────────────────────────────────────────────────────────────
function ViewToggle({ mode, onChange }) {
  return (
    <div style={{ display:"flex", gap:3, background:"rgba(0,0,0,0.4)",
      border:"1px solid rgba(255,255,255,0.06)", borderRadius:8, padding:3 }}>
      {[{ id:"single", label:"Single" }, { id:"all", label:"All 10" }].map(m => (
        <button key={m.id} onClick={() => onChange(m.id)} style={{
          padding:"5px 12px", borderRadius:6, border:"none", cursor:"pointer",
          fontFamily:"monospace", fontSize:9, letterSpacing:"0.06em",
          textTransform:"uppercase",
          background: mode===m.id ? "rgba(0,245,255,0.1)" : "transparent",
          color: mode===m.id ? "#00f5ff" : "#444",
          transition:"all 0.18s",
        }}>{m.label}</button>
      ))}
    </div>
  )
}

// ── Panel ─────────────────────────────────────────────────────────────────────
function Panel({ type, data, strK, numK, accent="#00f5ff", height=290 }) {
  const [mounted, setMounted] = useState(false)
  const [glitch,  setGlitch]  = useState(false)
  const def = TYPES.find(t => t.id === type)

  useEffect(() => {
    setMounted(false)
    const t = setTimeout(() => setMounted(true), 60)
    return () => clearTimeout(t)
  }, [type])

  useEffect(() => {
    setGlitch(true)
    const t = setTimeout(() => setGlitch(false), 350)
    return () => clearTimeout(t)
  }, [data])

  return (
    <div style={{
      position:"relative", background:"rgba(0,0,0,0.55)",
      border:"1px solid rgba(255,255,255,0.06)", borderRadius:13,
      padding:"20px 8px 8px",
      boxShadow:"0 4px 36px rgba(0,0,0,0.5),inset 0 0 40px rgba(0,245,255,0.015)",
      opacity: mounted ? 1 : 0,
      transform: mounted ? "translateY(0)" : "translateY(5px)",
      transition:"opacity 0.28s ease,transform 0.28s ease",
      filter: glitch ? "hue-rotate(12deg) brightness(1.08)" : "none",
    }}>
      <Scanline/>
      <Corners c={accent}/>
      <div style={{ position:"absolute", top:7, left:12, fontSize:8,
        color:`${accent}66`, letterSpacing:"0.14em", textTransform:"uppercase" }}>
        {def?.icon} {def?.label}
      </div>

      <div style={{ height }}>
        {type === "heatmap" ? (
          <div style={{ height:"100%", overflowY:"auto", paddingTop:2 }}>
            <HeatmapChart data={data} strK={strK} numK={numK}/>
          </div>
        ) : (
          <RenderChart type={type} data={data} strK={strK} numK={numK}/>
        )}
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function ChartView({ rows, chartHint }) {
  const suggested = autoDetect(rows, chartHint)
  const [type,     setType]     = useState(suggested)
  const [viewMode, setViewMode] = useState("single")

  const data            = useMemo(() => rows?.slice(0, 60) || [], [rows])
  const { strK, numK }  = useMemo(() => getKeys(data), [data])
  const stats           = useMemo(() => computeStats(data, numK), [data, numK])

  if (!rows?.length) return null

  const shared = { data, strK, numK }

  return (
    <div style={{ width:"100%", fontFamily:"monospace" }}>

      {/* Stats */}
      <div style={{ display:"grid",
        gridTemplateColumns:`repeat(${stats.length},1fr)`, gap:7, marginBottom:14 }}>
        {stats.map((s,i) => <AnimatedStat key={i} {...s}/>)}
      </div>

      {/* Controls */}
      <div style={{ display:"flex", gap:6, marginBottom:11,
        flexWrap:"wrap", alignItems:"center" }}>
        <span style={{ fontSize:8, color:"#333", letterSpacing:"0.1em",
          textTransform:"uppercase", marginRight:2 }}>View as</span>
        {TYPES.map(ct => (
          <TypeBtn key={ct.id} chart={ct}
            active={type===ct.id && viewMode==="single"}
            onClick={id => { setType(id); setViewMode("single") }}/>
        ))}
        <div style={{ marginLeft:"auto", display:"flex", gap:8, alignItems:"center" }}>
          <span style={{ fontSize:8, color:"#2a2a2a" }}>
            {data.length}r · {Object.keys(data[0]||{}).length}c
          </span>
          <ViewToggle mode={viewMode} onChange={setViewMode}/>
        </div>
      </div>

      {/* Single view */}
      {viewMode === "single" && (
        <Panel type={type} {...shared} accent="#00f5ff" height={300}/>
      )}

      {/* All 10 simultaneous */}
      {viewMode === "all" && (
        <div style={{ display:"grid",
          gridTemplateColumns:"repeat(auto-fit,minmax(320px,1fr))", gap:10 }}>
          {TYPES.map((ct,i) => (
            <Panel key={ct.id} type={ct.id} {...shared}
              accent={P[i%P.length]} height={230}/>
          ))}
        </div>
      )}

      <div style={{ height:1, marginTop:14,
        background:"linear-gradient(90deg,transparent,rgba(0,245,255,0.18),rgba(191,0,255,0.18),transparent)" }}/>
    </div>
  )
}
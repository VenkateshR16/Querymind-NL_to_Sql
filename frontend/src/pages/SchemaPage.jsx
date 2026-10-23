import { useEffect, useState } from 'react'
import { Table2, BarChart3, Hash, Type, Calendar, ToggleLeft, RefreshCw } from 'lucide-react'
import { useApp } from '../store/AppStore'
import { getSchema } from '../api/client'
import clsx from 'clsx'

const TYPE_META = {
  INTEGER: { icon: Hash,       color: 'text-blue-400',    bg: 'bg-blue-500/10'   },
  BIGINT:  { icon: Hash,       color: 'text-blue-400',    bg: 'bg-blue-500/10'   },
  DOUBLE:  { icon: BarChart3,  color: 'text-purple-400',  bg: 'bg-purple-500/10' },
  FLOAT:   { icon: BarChart3,  color: 'text-purple-400',  bg: 'bg-purple-500/10' },
  DECIMAL: { icon: BarChart3,  color: 'text-purple-400',  bg: 'bg-purple-500/10' },
  VARCHAR: { icon: Type,       color: 'text-amber-400',   bg: 'bg-amber-500/10'  },
  DATE:    { icon: Calendar,   color: 'text-emerald-400', bg: 'bg-emerald-500/10'},
  BOOLEAN: { icon: ToggleLeft, color: 'text-pink-400',    bg: 'bg-pink-500/10'   },
}

function getTypeMeta(type = '') {
  const key = Object.keys(TYPE_META).find(k => type.toUpperCase().includes(k))
  return key ? TYPE_META[key] : { icon: Type, color: 'text-zinc-400', bg: 'bg-zinc-500/10' }
}

function StatBadge({ label, val }) {
  if (val == null) return null
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-zinc-600 text-xs">{label}</span>
      <span className="text-xs text-zinc-300 font-medium font-mono">{
        typeof val === 'number' ? val.toLocaleString(undefined, { maximumFractionDigits: 2 }) : val
      }</span>
    </div>
  )
}

export default function SchemaPage() {
  const { state } = useApp()
  const [schemaData, setSchemaData] = useState({ columns: [], stats: [], preview: [] })
  const [loading, setLoading]       = useState(false)
  const [activeTab, setActiveTab]   = useState('schema')
  const table = state.activeTable

  useEffect(() => {
    if (!table) return
    setLoading(true)
    getSchema(table).then(r => {
      const stats = r.data.stats || []
      const columns = r.data.columns || []
      // Merge stats into columns
      const merged = columns.map(c => {
        const s = stats.find(s => s.column === c.name) || {}
        return { ...c, ...s }
      })
      setSchemaData({ columns: merged, preview: r.data.preview || [] })
    }).catch(() => {}).finally(() => setLoading(false))
  }, [table])

  if (!table) return (
    <div className="card p-12 text-center">
      <Table2 size={32} className="text-zinc-700 mx-auto mb-3" />
      <p className="text-zinc-400 font-medium">No dataset loaded</p>
      <p className="text-zinc-600 text-sm mt-1">Upload a CSV to view its schema</p>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-white">Schema Explorer</h1>
          <p className="text-zinc-500 text-sm mt-0.5">Column types, stats, and data preview</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-1.5 bg-surface-2 rounded-xl text-xs text-zinc-400 font-mono">{table}</span>
          {state.tableInfo[table] && (
            <span className="px-3 py-1.5 bg-brand-600/10 border border-brand-500/20 rounded-xl text-xs text-brand-400">
              {state.tableInfo[table].row_count?.toLocaleString()} rows × {state.tableInfo[table].col_count} cols
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/[0.06] pb-0">
        {['schema', 'preview'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium capitalize border-b-2 transition-all -mb-px',
              activeTab === tab
                ? 'border-brand-500 text-brand-300'
                : 'border-transparent text-zinc-500 hover:text-zinc-300'
            )}>
            {tab}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1,2,3,4].map(i => <div key={i} className="card h-24 shimmer" />)}
        </div>
      ) : activeTab === 'schema' ? (
        <div className="space-y-2">
          {schemaData.columns.map((col, idx) => {
            const meta = getTypeMeta(col.type)
            const Icon = meta.icon
            return (
              <div key={col.name}
                className="card p-4 flex items-start gap-4 hover:border-white/10 transition-all animate-slide-up"
                style={{ animationDelay: `${idx * 0.03}s` }}>
                <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', meta.bg)}>
                  <Icon size={18} className={meta.color} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-white font-medium font-mono text-sm">{col.name}</span>
                    <span className={clsx('tag text-[10px]', meta.bg, meta.color)}>{col.type}</span>
                  </div>
                  <div className="flex items-center gap-4 mt-2 flex-wrap">
                    <StatBadge label="min"      val={col.min} />
                    <StatBadge label="max"      val={col.max} />
                    <StatBadge label="avg"      val={col.avg} />
                    <StatBadge label="distinct" val={col.distinct} />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* Data preview */
        <div className="card overflow-auto">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {schemaData.columns.map(c => <th key={c.name}>{c.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {schemaData.preview.map((row, i) => (
                  <tr key={i}>
                    {schemaData.columns.map(c => (
                      <td key={c.name} title={String(row[c.name] ?? '')}>
                        {row[c.name] == null
                          ? <span className="text-zinc-700 italic text-xs">null</span>
                          : String(row[c.name])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

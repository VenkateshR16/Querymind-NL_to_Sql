import { useState, useEffect } from 'react'
import { Clock, Trash2, RotateCcw, Keyboard, Mic, Image, Code2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useApp } from '../store/AppStore'
import { getHistory, getHistStats, deleteHist, clearHistory } from '../api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const MODE_ICON = { text: Keyboard, voice: Mic, image: Image, direct: Code2 }
const MODE_COLOR = { text: 'text-brand-400', voice: 'text-red-400', image: 'text-amber-400', direct: 'text-emerald-400' }

export default function HistoryPage() {
  const { state, dispatch } = useApp()
  const [items, setItems]   = useState([])
  const [stats, setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const [h, s] = await Promise.all([getHistory({ limit: 100 }), getHistStats()])
      setItems(h.data.items || [])
      setStats(s.data)
      dispatch({ type: 'SET_HIST_STATS', payload: s.data })
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function remove(id) {
    await deleteHist(id)
    setItems(prev => prev.filter(i => i.id !== id))
    toast.success('Deleted')
  }

  async function clearAll() {
    if (!confirm('Clear all query history?')) return
    await clearHistory()
    setItems([])
    toast.success('History cleared')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-white">Query History</h1>
          <p className="text-zinc-500 text-sm mt-0.5">All past queries and their results</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-ghost text-sm">
            <RotateCcw size={14} /> Refresh
          </button>
          {items.length > 0 && (
            <button onClick={clearAll} className="btn-ghost text-sm text-red-400 hover:text-red-300">
              <Trash2 size={14} /> Clear All
            </button>
          )}
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total Queries', val: stats.total },
            { label: 'Successful',    val: stats.success,  accent: 'emerald' },
            { label: 'Failed',        val: stats.failed,   accent: 'red' },
            { label: 'Avg Speed',     val: `${stats.avg_ms}ms`, accent: 'brand' },
          ].map(({ label, val, accent }) => (
            <div key={label} className="card p-4">
              <p className={clsx(
                'text-2xl font-bold font-display',
                accent === 'emerald' ? 'text-emerald-400'
                : accent === 'red'   ? 'text-red-400'
                : accent === 'brand' ? 'text-brand-400'
                : 'text-white'
              )}>{val}</p>
              <p className="text-zinc-500 text-xs mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="card h-20 shimmer" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="card p-12 text-center">
          <Clock size={32} className="text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-400 font-medium">No query history yet</p>
          <p className="text-zinc-600 text-sm mt-1">Run some queries to see them here</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(item => {
            const ModeIcon = MODE_ICON[item.input_mode] || Keyboard
            const isOpen = expanded === item.id
            return (
              <div key={item.id} className={clsx(
                'card overflow-hidden transition-all hover:border-white/10',
                item.status === 'failed' && 'border-red-500/20'
              )}>
                <div
                  className="flex items-start gap-4 px-4 py-3.5 cursor-pointer"
                  onClick={() => setExpanded(isOpen ? null : item.id)}
                >
                  {/* Status + Mode */}
                  <div className="flex flex-col items-center gap-1.5 flex-shrink-0 mt-0.5">
                    {item.status === 'success'
                      ? <CheckCircle2 size={15} className="text-emerald-400" />
                      : <AlertCircle  size={15} className="text-red-400" />
                    }
                    <ModeIcon size={11} className={MODE_COLOR[item.input_mode] || 'text-zinc-500'} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium truncate">{item.question}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-zinc-600">{item.table_name}</span>
                      {item.row_count > 0 && (
                        <span className="text-xs text-zinc-600">{item.row_count.toLocaleString()} rows</span>
                      )}
                      {item.elapsed_ms > 0 && (
                        <span className="text-xs text-zinc-600">{item.elapsed_ms}ms</span>
                      )}
                    </div>
                  </div>

                  {/* Right side */}
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-xs text-zinc-600">{item.created_at?.split(' ')[1] || ''}</span>
                    <button onClick={e => { e.stopPropagation(); remove(item.id) }}
                      className="p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition-all">
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>

                {/* Expanded SQL */}
                {isOpen && (
                  <div className="border-t border-white/[0.06] px-4 py-3 bg-surface-2/50 animate-slide-up">
                    <p className="text-[10px] text-zinc-600 mb-2 font-semibold uppercase tracking-wider">SQL</p>
                    <pre className="text-xs text-emerald-300 font-mono whitespace-pre-wrap overflow-x-auto">
                      {item.sql_query}
                    </pre>
                    {item.error && (
                      <p className="text-xs text-red-400 mt-2 font-mono">{item.error}</p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

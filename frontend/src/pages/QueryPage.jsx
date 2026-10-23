import { useState } from 'react'
import { Brain, Upload, Link2 } from 'lucide-react'
import { useApp } from '../store/AppStore'
import QueryInput from '../components/QueryInput/QueryInput'
import ResultsPane from '../components/ResultsPane/ResultsPane'
import SQLViewer from '../components/SQLViewer/SQLViewer'
import ColumnAdvisor from '../components/ColumnAdvisor/ColumnAdvisor'

export default function QueryPage() {
  const { state } = useApp()
  const [result, setResult] = useState(null)
  const [query, setQuery]   = useState('')
  const [sql, setSql]       = useState('')

  function onResult(data) {
    setResult(data?.result || null)
    setQuery(data?.question || '')
    setSql(data?.sql || '')
  }

  const activeTables = state.activeTables?.length > 0
    ? state.activeTables
    : state.activeTable ? [state.activeTable] : []

  const isMultiTable = activeTables.length > 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold text-white">Query Interface</h1>
          <p className="text-zinc-500 text-sm mt-0.5">
            Ask questions in natural language, voice, or image
          </p>
        </div>

        {/* Active tables badge */}
        {activeTables.length > 0 && (
          <div className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-medium',
            isMultiTable
              ? 'bg-brand-600/10 border-brand-500/30 text-brand-300'
              : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
          )}>
            {isMultiTable
              ? <Link2 size={14} className="text-brand-400" />
              : <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            }
            {isMultiTable
              ? `JOIN: ${activeTables.join(' + ')}`
              : activeTables[0]
            }
            {state.tableInfo[activeTables[0]] && !isMultiTable && (
              <span className="text-emerald-600 text-xs">
                {state.tableInfo[activeTables[0]]?.row_count?.toLocaleString()} rows
              </span>
            )}
          </div>
        )}
      </div>

      {/* Multi-table JOIN info banner */}
      {isMultiTable && (
        <div className="flex items-start gap-3 px-4 py-3 bg-brand-600/10 border border-brand-500/20 rounded-xl animate-fade-in">
          <Link2 size={16} className="text-brand-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-brand-300">Multi-table JOIN mode</p>
            <p className="text-xs text-zinc-500 mt-0.5">
              Queries will automatically JOIN <span className="text-brand-400">{activeTables.join(', ')}</span> using
              common columns. Ask questions spanning both datasets.
            </p>
          </div>
        </div>
      )}

      {/* No table uploaded yet */}
      {activeTables.length === 0 && (
        <div className="card p-10 text-center border-dashed border-white/[0.1] flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-brand-600/10 border border-brand-500/20 flex items-center justify-center">
            <Upload size={28} className="text-brand-400" />
          </div>
          <div>
            <p className="text-zinc-300 font-medium">No dataset loaded</p>
            <p className="text-zinc-600 text-sm mt-1">Upload CSV files using the sidebar to get started</p>
          </div>
        </div>
      )}

      {/* Query input */}
      {activeTables.length > 0 && <QueryInput onResult={onResult} activeTables={activeTables} />}

      {/* SQL viewer */}
      {sql && (
        <div className="animate-slide-up">
          <SQLViewer sql={sql} elapsed={result?.elapsed_ms} rowCount={result?.row_count} />
        </div>
      )}

      {/* Column advisor */}
      {state.lastResult?.recommendations && (
        <div className="animate-slide-up" style={{ animationDelay: '0.05s' }}>
          <ColumnAdvisor recommendations={state.lastResult.recommendations} />
        </div>
      )}

      {/* Results */}
      <div className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
        <ResultsPane result={result} question={query} sql={sql} />
      </div>
    </div>
  )
}

function clsx(...classes) {
  return classes.filter(Boolean).join(' ')
}

import { useState } from 'react'
import { Copy, Check, ChevronDown, ChevronUp, Code2 } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function SQLViewer({ sql, elapsed, rowCount }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied]     = useState(false)

  if (!sql) return null

  async function copy() {
    await navigator.clipboard.writeText(sql)
    setCopied(true)
    toast.success('SQL copied')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-surface-2/50">
        <div className="flex items-center gap-2">
          <Code2 size={14} className="text-brand-400" />
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Generated SQL</span>
          {elapsed != null && (
            <span className="tag bg-emerald-500/10 text-emerald-400">{elapsed}ms</span>
          )}
          {rowCount != null && (
            <span className="tag bg-brand-500/10 text-brand-400">{rowCount.toLocaleString()} rows</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={copy}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-all">
            {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-all">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="sql-viewer overflow-x-auto" style={{ maxHeight: '200px' }}>
          <SyntaxHighlighter
            language="sql"
            style={vscDarkPlus}
            customStyle={{
              margin: 0, padding: '16px',
              background: 'transparent',
              fontSize: '13px',
              lineHeight: '1.7',
            }}
          >
            {sql}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  )
}

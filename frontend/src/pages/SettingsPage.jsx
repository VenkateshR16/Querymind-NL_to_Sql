import { useState } from 'react'
import { Settings, Brain, Mic, Eye, Database, Info, CheckCircle2 } from 'lucide-react'

const Section = ({ icon: Icon, title, children }) => (
  <div className="card p-5 space-y-4">
    <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.06]">
      <Icon size={16} className="text-brand-400" />
      <h2 className="text-sm font-semibold text-white">{title}</h2>
    </div>
    {children}
  </div>
)

const Toggle = ({ label, desc, defaultVal = false }) => {
  const [on, setOn] = useState(defaultVal)
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm text-zinc-300">{label}</p>
        {desc && <p className="text-xs text-zinc-600 mt-0.5">{desc}</p>}
      </div>
      <button onClick={() => setOn(!on)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 focus:outline-none mt-0.5 ${on ? 'bg-brand-600' : 'bg-surface-4'}`}>
        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 mt-0.5 ${on ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )
}

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="font-display text-2xl font-bold text-white">Settings</h1>
        <p className="text-zinc-500 text-sm mt-0.5">Configure QueryMind behaviour and AI models</p>
      </div>

      <Section icon={Brain} title="AI Model">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500 mb-1.5 block uppercase tracking-wider">SQL Generation Model</label>
            <select className="input-base text-sm">
              <option>google/flan-t5-large (default)</option>
              <option>google/flan-t5-xl</option>
              <option>google/flan-t5-xxl</option>
            </select>
          </div>
          <Toggle label="Beam search decoding" desc="Higher quality SQL, slightly slower" defaultVal={true} />
          <Toggle label="Auto-correct SQL syntax" desc="Fix minor errors automatically" defaultVal={true} />
        </div>
      </Section>

      <Section icon={Mic} title="Voice Input">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500 mb-1.5 block uppercase tracking-wider">Whisper Model Size</label>
            <select className="input-base text-sm">
              <option>base (faster, less accurate)</option>
              <option>small</option>
              <option>medium (recommended)</option>
              <option>large-v3 (most accurate)</option>
            </select>
          </div>
          <Toggle label="Auto-submit after transcription" desc="Run query immediately after voice input" />
          <Toggle label="Show confidence score" desc="Display transcription confidence" />
        </div>
      </Section>

      <Section icon={Eye} title="Display">
        <div className="space-y-3">
          <Toggle label="Auto-show chart" desc="Switch to chart view when results are charted" defaultVal={true} />
          <Toggle label="Transparent SQL display" desc="Show generated SQL by default" defaultVal={true} />
          <Toggle label="Animated transitions" desc="Enable UI animations and transitions" defaultVal={true} />
          <div>
            <label className="text-xs text-zinc-500 mb-1.5 block uppercase tracking-wider">Max rows in table</label>
            <select className="input-base text-sm">
              <option>500</option>
              <option>1000</option>
              <option>2500</option>
              <option>5000</option>
            </select>
          </div>
        </div>
      </Section>

      <Section icon={Database} title="Data & Privacy">
        <div className="space-y-3">
          <Toggle label="Fully offline mode" desc="Never send data to external services" defaultVal={true} />
          <Toggle label="Keep query history" desc="Persist queries to local database" defaultVal={true} />
          <Toggle label="Auto-clear on exit" desc="Delete uploaded datasets when app closes" />
        </div>
      </Section>

      <Section icon={Info} title="About">
        <div className="space-y-2 text-sm text-zinc-500">
          {[
            ['Version', '1.0.0'],
            ['Build', 'Production'],
            ['AI Model', 'FLAN-T5 Large'],
            ['ASR', 'OpenAI Whisper Base'],
            ['OCR', 'Tesseract 5.x'],
            ['Query Engine', 'DuckDB 0.10'],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span>{k}</span>
              <span className="text-zinc-300 font-mono text-xs">{v}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

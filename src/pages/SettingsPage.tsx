import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { clearJob } from '../api/endpoints'
import { useSettingsStore } from '../store/settings'

function Slider(props: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div className="panel2 rounded-xl p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">{props.label}</div>
        <div className="mono text-xs text-[rgba(255,255,255,0.65)]">{props.value}</div>
      </div>
      <input
        className="mt-3 w-full"
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        onChange={(e) => props.onChange(Number(e.target.value))}
      />
    </div>
  )
}

export function SettingsPage() {
  const [key, setKey] = useState(localStorage.getItem('openai_api_key') ?? '')
  const jobId = useSettingsStore((s) => s.jobId)
  const setJobId = useSettingsStore((s) => s.setJobId)

  const chunkSize = useSettingsStore((s) => s.chunkSize)
  const chunkOverlap = useSettingsStore((s) => s.chunkOverlap)
  const hops = useSettingsStore((s) => s.hops)
  const setChunkSize = useSettingsStore((s) => s.setChunkSize)
  const setChunkOverlap = useSettingsStore((s) => s.setChunkOverlap)
  const setHops = useSettingsStore((s) => s.setHops)

  const masked = useMemo(() => (key ? `${key.slice(0, 6)}…${key.slice(-4)}` : '—'), [key])

  return (
    <div className="flex flex-col gap-4">
      <div className="panel rounded-xl p-5">
        <div className="text-lg font-semibold">Settings</div>
        <div className="mt-1 text-sm text-[rgba(255,255,255,0.65)]">
          Your API key is stored in <span className="mono">localStorage</span> and sent only via <span className="mono">X-OpenAI-Key</span>.
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="panel2 rounded-xl p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">OpenAI API Key</div>
              <div className="mono text-xs text-[rgba(255,255,255,0.65)]">{masked}</div>
            </div>
            <input
              className="input mt-3"
              value={key}
              placeholder="sk-..."
              onChange={(e) => setKey(e.target.value)}
            />
            <div className="mt-3 flex gap-2">
              <button
                className="btn"
                onClick={() => {
                  localStorage.setItem('openai_api_key', key)
                  toast.success('Saved key locally.')
                }}
              >
                Save
              </button>
              <button
                className="btn"
                onClick={() => {
                  localStorage.removeItem('openai_api_key')
                  setKey('')
                  toast.success('Cleared key.')
                }}
              >
                Clear
              </button>
            </div>
          </div>

          <div className="panel2 rounded-xl p-4">
            <div className="text-sm font-semibold">Active Job</div>
            <div className="mono mt-2 text-xs text-[rgba(255,255,255,0.65)]">job_id</div>
            <div className="mono text-sm">{jobId || '—'}</div>
            <div className="mt-3 flex gap-2">
              <button
                className="btn"
                disabled={!jobId}
                onClick={async () => {
                  await clearJob(jobId)
                  setJobId('')
                  toast.success('Cleared job data.')
                }}
              >
                Clear Data
              </button>
              <button className="btn" onClick={() => setJobId('')}>
                Unset Job
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Slider label="Chunk size" value={chunkSize} min={200} max={1200} step={50} onChange={setChunkSize} />
        <Slider label="Chunk overlap" value={chunkOverlap} min={0} max={300} step={10} onChange={setChunkOverlap} />
        <Slider label="Graph hops (local search)" value={hops} min={1} max={2} step={1} onChange={setHops} />
      </div>
      <div className="text-xs text-[rgba(255,255,255,0.60)]">
        Note: sliders are wired in the UI; backend currently uses defaults (can be extended to accept per-job settings).
      </div>
    </div>
  )
}


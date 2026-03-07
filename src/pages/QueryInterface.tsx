import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runQuery } from '../api/endpoints'
import { QueryResultCard } from '../components/QueryResultCard'
import { useSettingsStore } from '../store/settings'

const systemOrder = ['direct_llm', 'vector_rag', 'summary_rag', 'graph_global', 'graph_local'] as const

export function QueryInterface() {
  const jobId = useSettingsStore((s) => s.jobId)
  const [question, setQuestion] = useState('')
  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    direct_llm: false,
    vector_rag: true,
    summary_rag: true,
    graph_global: true,
    graph_local: true,
  })

  const q = useMutation({
    mutationFn: () => runQuery({ job_id: jobId, question, mode: 'all' }),
  })

  const filteredResults = useMemo(() => {
    const r = q.data?.results ?? []
    const by = new Map(r.map((x) => [x.mode, x]))
    return systemOrder
      .filter((m) => enabled[m])
      .map((m) => by.get(m))
      .filter(Boolean)
  }, [q.data, enabled])

  return (
    <div className="flex flex-col gap-4">
      <div className="panel rounded-xl p-5">
        <div className="text-lg font-semibold">Query Interface</div>
        <div className="mt-1 text-sm text-[rgba(255,255,255,0.65)]">
          Run the same question across multiple pipelines and compare answers, latency, and sources side-by-side.
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_360px]">
          <div>
            <textarea
              className="input min-h-[120px]"
              placeholder="Ask a global question that requires multi-document reasoning…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div className="mt-3 flex gap-2">
              <button className="btn" disabled={!jobId || !question || q.isPending} onClick={() => q.mutate()}>
                Run Query
              </button>
              <button className="btn" disabled={q.isPending} onClick={() => setQuestion('')}>
                Clear
              </button>
            </div>
            {!jobId ? (
              <div className="mt-2 text-xs text-[rgba(255,255,255,0.65)]">Upload + index a job first.</div>
            ) : null}
          </div>

          <div className="panel2 rounded-xl p-4">
            <div className="text-sm font-semibold">Pipelines</div>
            <div className="mt-3 flex flex-col gap-2 text-sm">
              {systemOrder.map((k) => (
                <label key={k} className="flex cursor-pointer items-center justify-between gap-2">
                  <span className="mono text-xs">{k}</span>
                  <input
                    type="checkbox"
                    checked={enabled[k]}
                    onChange={(e) => setEnabled((p) => ({ ...p, [k]: e.target.checked }))}
                  />
                </label>
              ))}
            </div>
            <div className="mt-3 text-xs text-[rgba(255,255,255,0.65)]">
              Note: <span className="mono">direct_llm</span> is optional baseline (no retrieval).
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {filteredResults.map((r) => (r ? <QueryResultCard key={r.mode} result={r} /> : null))}
      </div>
    </div>
  )
}


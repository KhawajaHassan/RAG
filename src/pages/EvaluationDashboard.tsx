import { useMemo } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'
import {
  estimateEvaluation,
  generateEvaluationQuestions,
  getEvaluationResults,
  getIndexStatus,
  runEvaluation,
} from '../api/endpoints'
import { useSettingsStore } from '../store/settings'

const criteria = ['Comprehensiveness', 'Diversity', 'Empowerment', 'Directness'] as const

function Heatmap(props: { systems: string[]; matrix: Record<string, Record<string, number>> }) {
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="mono sticky left-0 bg-[rgba(0,0,0,0.18)] p-2 text-left">system</th>
            {props.systems.map((s) => (
              <th key={s} className="mono p-2 text-left">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.systems.map((r) => (
            <tr key={r}>
              <td className="mono sticky left-0 bg-[rgba(0,0,0,0.18)] p-2">{r}</td>
              {props.systems.map((c) => {
                const v = props.matrix?.[r]?.[c] ?? 0
                const bg = `rgba(52,214,255,${Math.max(0.06, Math.min(0.55, v))})`
                return (
                  <td key={c} className="mono p-2" style={{ background: bg, border: '1px solid rgba(255,255,255,0.08)' }}>
                    {v.toFixed(2)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function EvaluationDashboard() {
  const jobId = useSettingsStore((s) => s.jobId)

  const statusQ = useQuery({
    queryKey: ['status', jobId],
    queryFn: () => getIndexStatus(jobId),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const step = q.state.data?.current_step ?? ''
      const status = q.state.data?.status ?? ''
      return status === 'running' && step.toLowerCase().includes('evaluation') ? 1500 : false
    },
  })

  const estimateQ = useQuery({
    queryKey: ['eval-estimate', jobId],
    queryFn: () =>
      estimateEvaluation(jobId, { question_count: 125, systems: 5, runs: 5, price_per_unit_usd: 0.002 }),
    enabled: !!jobId,
  })

  const genMut = useMutation({
    mutationFn: () => generateEvaluationQuestions(jobId),
    onSuccess: (d) => toast.success(`Generated ${d.question_count} questions.`),
  })

  const runMut = useMutation({
    mutationFn: () => runEvaluation(jobId),
    onSuccess: () => {
      toast.success('Evaluation started.')
      statusQ.refetch()
    },
  })

  const resultsQ = useQuery({
    queryKey: ['eval-results', jobId],
    queryFn: () => getEvaluationResults(jobId),
    enabled: !!jobId,
    retry: false,
  })

  const parsed = useMemo(() => {
    const r: any = resultsQ.data?.results ?? {}
    return {
      systems: (r.systems as string[]) ?? [],
      win_rates: (r.win_rates as any) ?? {},
      claim_stats: (r.claim_stats as any) ?? {},
    }
  }, [resultsQ.data])

  const radarData = useMemo(() => {
    const systems = parsed.systems
    if (!systems.length) return []
    // average win rate per criterion vs others
    return systems.map((s) => {
      const row: any = { system: s }
      for (const c of criteria) {
        const m = parsed.win_rates?.[c]?.[s] ?? {}
        const vals = systems.filter((x) => x !== s).map((x) => Number(m[x] ?? 0.5))
        row[c] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0.5
      }
      return row
    })
  }, [parsed])

  return (
    <div className="flex flex-col gap-4">
      <div className="panel rounded-xl p-5">
        <div className="text-lg font-semibold">Evaluation Dashboard</div>
        <div className="mt-1 text-sm text-[rgba(255,255,255,0.65)]">
          Generate 125 global questions, run all 5 systems, then judge pairwise on 4 criteria (5 repeats) + claim metrics.
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="panel2 rounded-xl p-4">
            <div className="text-sm font-semibold">Cost estimate</div>
            <div className="mono mt-2 text-xs text-[rgba(255,255,255,0.65)]">~$0.002 × 125 × 5 systems × 5 runs</div>
            <div className="mono mt-3 text-2xl">
              ${estimateQ.data?.estimated_cost_usd?.toFixed(2) ?? '—'}
            </div>
          </div>

          <div className="panel2 rounded-xl p-4">
            <div className="text-sm font-semibold">Actions</div>
            <div className="mt-3 flex flex-col gap-2">
              <button className="btn" disabled={!jobId || genMut.isPending} onClick={() => genMut.mutate()}>
                Generate Questions
              </button>
              <button className="btn" disabled={!jobId || runMut.isPending} onClick={() => runMut.mutate()}>
                Run Evaluation
              </button>
              <button className="btn" disabled={!jobId} onClick={() => resultsQ.refetch()}>
                Refresh Results
              </button>
            </div>
            <div className="mono mt-3 text-xs text-[rgba(255,255,255,0.65)]">
              {statusQ.data ? `${statusQ.data.current_step} • ${Math.round((statusQ.data.progress ?? 0) * 100)}%` : '—'}
            </div>
          </div>

          <div className="panel2 rounded-xl p-4">
            <div className="text-sm font-semibold">Claim metrics (avg)</div>
            <div className="mt-3 flex flex-col gap-2">
              {parsed.systems.length ? (
                parsed.systems.map((s) => (
                  <div key={s} className="flex items-center justify-between gap-2 text-xs">
                    <div className="mono">{s}</div>
                    <div className="mono text-[rgba(255,255,255,0.70)]">
                      claims {(Number(parsed.claim_stats?.[s]?.avg_unique_claims) ?? 0).toFixed(1)} • clusters{' '}
                      {(Number(parsed.claim_stats?.[s]?.avg_clusters) ?? 0).toFixed(1)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-[rgba(255,255,255,0.65)]">Run evaluation to populate metrics.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {parsed.systems.length ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="panel rounded-xl p-4">
            <div className="text-sm font-semibold">Win-rate heatmap (Comprehensiveness)</div>
            <div className="mt-3">
              <Heatmap systems={parsed.systems} matrix={parsed.win_rates?.Comprehensiveness ?? {}} />
            </div>
          </div>

          <div className="panel rounded-xl p-4">
            <div className="text-sm font-semibold">Radar (avg win rate vs others)</div>
            <div className="mt-3 h-[340px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.12)" />
                  <PolarAngleAxis dataKey="system" tick={{ fill: 'rgba(255,255,255,0.65)', fontSize: 11 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10 }} />
                  <Radar dataKey="Comprehensiveness" stroke="#34d6ff" fill="rgba(52,214,255,0.18)" fillOpacity={0.8} />
                  <Radar dataKey="Diversity" stroke="#a78bfa" fill="rgba(167,139,250,0.16)" fillOpacity={0.7} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}


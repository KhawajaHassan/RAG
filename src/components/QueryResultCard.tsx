import type { QueryResult } from '../api/types'

export function QueryResultCard(props: { result: QueryResult }) {
  return (
    <div className="panel rounded-xl p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">{props.result.mode}</div>
        <div className="mono text-xs text-[rgba(255,255,255,0.65)]">{props.result.latency_ms}ms</div>
      </div>
      <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-[rgba(255,255,255,0.82)]">
        {props.result.answer || '—'}
      </div>
      {props.result.sources?.length ? (
        <details className="mt-3">
          <summary className="mono cursor-pointer text-xs text-[rgba(255,255,255,0.65)]">sources</summary>
          <pre className="mono mt-2 overflow-auto rounded-lg bg-[rgba(0,0,0,0.25)] p-3 text-[11px] text-[rgba(255,255,255,0.75)]">
            {JSON.stringify(props.result.sources, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  )
}


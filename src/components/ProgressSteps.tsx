const steps = ['Chunking', 'Embedding', 'Extracting', 'Building Graph', 'Communities', 'Summarizing', 'Done'] as const

function stepIndex(stepName: string) {
  const i = steps.findIndex((s) => stepName?.toLowerCase().includes(s.toLowerCase()))
  return i === -1 ? 0 : i
}

export function ProgressSteps(props: { currentStep: string; progress: number }) {
  const idx = stepIndex(props.currentStep)

  return (
    <div className="panel rounded-xl p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold">Indexing Progress</div>
        <div className="mono text-xs text-[rgba(255,255,255,0.65)]">{Math.round(props.progress * 100)}%</div>
      </div>

      <div className="mb-3 h-2 w-full overflow-hidden rounded bg-[rgba(255,255,255,0.08)]">
        <div
          className="h-full"
          style={{
            width: `${Math.max(2, Math.round(props.progress * 100))}%`,
            background: 'linear-gradient(90deg, rgba(52,214,255,0.75), rgba(167,139,250,0.65))',
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        {steps.map((s, i) => {
          const state = i < idx ? 'done' : i === idx ? 'active' : 'todo'
          return (
            <div
              key={s}
              className={[
                'rounded-lg px-3 py-2 text-xs',
                state === 'done' ? 'bg-[rgba(52,214,255,0.08)]' : '',
                state === 'active' ? 'bg-[rgba(167,139,250,0.10)] border border-[rgba(167,139,250,0.25)]' : '',
                state === 'todo' ? 'bg-[rgba(255,255,255,0.03)] text-[rgba(255,255,255,0.65)]' : '',
              ].join(' ')}
            >
              <div className="mono text-[10px] text-[rgba(255,255,255,0.6)]">{state.toUpperCase()}</div>
              <div className="font-medium">{s}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


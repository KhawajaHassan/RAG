import type { NodeProps } from 'reactflow'

const typeStyle: Record<string, { label: string; color: string }> = {
  PERSON: { label: 'PERSON', color: 'rgba(52,214,255,0.85)' },
  ORG: { label: 'ORG', color: 'rgba(167,139,250,0.85)' },
  LOCATION: { label: 'LOC', color: 'rgba(56,189,248,0.75)' },
  CONCEPT: { label: 'CON', color: 'rgba(255,255,255,0.70)' },
  EVENT: { label: 'EVT', color: 'rgba(251,191,36,0.80)' },
}

export function EntityNode(props: NodeProps<{ label: string; type: string; degree: number }>) {
  const t = typeStyle[props.data.type] ?? typeStyle.CONCEPT
  return (
    <div
      className="panel rounded-lg px-3 py-2"
      style={{
        borderColor: t.color,
        boxShadow: props.selected ? `0 0 0 1px ${t.color}, 0 0 30px rgba(52,214,255,0.08)` : undefined,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="truncate text-sm font-semibold">{props.data.label}</div>
        <div className="mono text-[10px]" style={{ color: t.color }}>
          {t.label}
        </div>
      </div>
      <div className="mono mt-1 text-[10px] text-[rgba(255,255,255,0.60)]">deg {props.data.degree.toFixed(3)}</div>
    </div>
  )
}


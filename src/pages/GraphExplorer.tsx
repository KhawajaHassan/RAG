import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'
import { getCommunity, getGraphEdges, getGraphNodes } from '../api/endpoints'
import { useSettingsStore } from '../store/settings'
import { EntityNode } from '../components/graph/EntityNode'

export function GraphExplorer() {
  const jobId = useSettingsStore((s) => s.jobId)
  const [level, setLevel] = useState(0)
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'PERSON' | 'ORG' | 'LOCATION' | 'CONCEPT' | 'EVENT'>('ALL')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<{ nodeId: string; communityId?: string | null } | null>(null)

  const nodesQ = useQuery({
    queryKey: ['graph-nodes', jobId, level],
    queryFn: () => getGraphNodes(jobId, level),
    enabled: !!jobId,
  })

  const edgesQ = useQuery({
    queryKey: ['graph-edges', jobId],
    queryFn: () => getGraphEdges(jobId),
    enabled: !!jobId,
  })

  const communityQ = useQuery({
    queryKey: ['community', jobId, level, selected?.communityId],
    queryFn: () => getCommunity(jobId, level, selected?.communityId ?? ''),
    enabled: !!jobId && !!selected?.communityId,
  })

  const rf = useMemo(() => {
    const nodesRaw = nodesQ.data ?? []
    const edgesRaw = edgesQ.data ?? []

    const filtered = nodesRaw
      .filter((n) => (typeFilter === 'ALL' ? true : n.type === typeFilter))
      .filter((n) => (search ? n.label.toLowerCase().includes(search.toLowerCase()) : true))

    const nodeSet = new Set(filtered.map((n) => n.id))
    const edgesFiltered = edgesRaw.filter((e) => nodeSet.has(e.source) && nodeSet.has(e.target))

    const rfNodes: Node[] = filtered.map((n, idx) => {
      const size = 50 + Math.min(70, Math.round(n.degree * 220))
      return {
        id: n.id,
        type: 'entity',
        position: { x: (idx % 10) * 120, y: Math.floor(idx / 10) * 90 },
        data: { label: n.label, type: n.type, degree: n.degree },
        style: {
          width: size * 2.2,
        },
      }
    })

    const rfEdges: Edge[] = edgesFiltered.map((e) => {
      const w = Math.max(1, Math.min(8, e.weight / 2))
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: false,
        style: { strokeWidth: w, stroke: 'rgba(255,255,255,0.18)' },
      }
    })

    return { rfNodes, rfEdges }
  }, [nodesQ.data, edgesQ.data, typeFilter, search])

  return (
    <div className="grid h-[calc(100vh-32px)] grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
      <div className="panel h-full min-h-[640px] rounded-xl">
        <div className="flex items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.10)] p-3">
          <div className="text-sm font-semibold">Graph Explorer</div>
          <div className="flex items-center gap-2">
            <select className="input w-[110px]" value={level} onChange={(e) => setLevel(Number(e.target.value))}>
              <option value={0}>C0</option>
              <option value={1}>C1</option>
              <option value={2}>C2</option>
              <option value={3}>C3</option>
            </select>
            <select
              className="input w-[140px]"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as any)}
            >
              <option value="ALL">All types</option>
              <option value="PERSON">PERSON</option>
              <option value="ORG">ORG</option>
              <option value="LOCATION">LOCATION</option>
              <option value="CONCEPT">CONCEPT</option>
              <option value="EVENT">EVENT</option>
            </select>
            <input className="input w-[220px]" value={search} placeholder="Search name…" onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>

        <div className="h-[calc(100%-52px)]">
          <ReactFlow
            nodes={rf.rfNodes}
            edges={rf.rfEdges}
            nodeTypes={{ entity: EntityNode }}
            fitView
            onNodeClick={(_, n) => setSelected({ nodeId: n.id, communityId: (nodesQ.data ?? []).find((x) => x.id === n.id)?.community_id })}
          >
            <MiniMap style={{ background: 'rgba(0,0,0,0.25)' }} />
            <Controls />
            <Background gap={20} size={1} color="rgba(255,255,255,0.08)" />
          </ReactFlow>
        </div>
      </div>

      <div className="flex h-full flex-col gap-4">
        <div className="panel rounded-xl p-4">
          <div className="text-sm font-semibold">Node Details</div>
          <div className="mono mt-2 text-xs text-[rgba(255,255,255,0.65)]">Selected</div>
          <div className="mono text-sm">{selected?.nodeId ?? '—'}</div>
          {selected?.nodeId ? (
            <div className="mt-3 text-xs text-[rgba(255,255,255,0.70)]">
              {(nodesQ.data ?? []).find((n) => n.id === selected.nodeId)?.description?.slice(0, 900) ?? ''}
            </div>
          ) : null}
        </div>

        <div className="panel rounded-xl p-4">
          <div className="text-sm font-semibold">Community Summary</div>
          <div className="mono mt-2 text-xs text-[rgba(255,255,255,0.65)]">
            {selected?.communityId ? `${selected.communityId} @ C${level}` : '—'}
          </div>
          {communityQ.data ? (
            <>
              <div className="mt-2 text-sm font-semibold">{communityQ.data.title}</div>
              <div className="mt-2 text-xs text-[rgba(255,255,255,0.70)]">{communityQ.data.executive_summary}</div>
              <div className="mono mt-3 text-xs text-[rgba(255,255,255,0.65)]">
                severity {communityQ.data.impact_severity.toFixed(1)} / 10
              </div>
              <ul className="mt-2 list-disc pl-5 text-xs text-[rgba(255,255,255,0.72)]">
                {communityQ.data.findings.slice(0, 8).map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </>
          ) : (
            <div className="mt-2 text-xs text-[rgba(255,255,255,0.65)]">Select a node to load its community.</div>
          )}
        </div>
      </div>
    </div>
  )
}


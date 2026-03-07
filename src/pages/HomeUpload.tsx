import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { getIndexStatus, startIndexing, uploadDocument } from '../api/endpoints'
import { useSettingsStore } from '../store/settings'
import { ProgressSteps } from '../components/ProgressSteps'

function StatPill(props: { label: string; value: number | string }) {
  return (
    <div className="panel2 rounded-xl p-3">
      <div className="mono text-[10px] text-[rgba(255,255,255,0.6)]">{props.label}</div>
      <div className="mono text-lg">{props.value}</div>
    </div>
  )
}

export function HomeUpload() {
  const jobId = useSettingsStore((s) => s.jobId)
  const setJobId = useSettingsStore((s) => s.setJobId)

  const [file, setFile] = useState<File | null>(null)

  const statusQuery = useQuery({
    queryKey: ['status', jobId],
    queryFn: () => getIndexStatus(jobId),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'running' || s === 'queued' ? 1500 : false
    },
  })

  const uploadMut = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (d) => {
      setJobId(d.job_id)
      toast.success('Uploaded. You can start indexing now.')
    },
  })

  const indexMut = useMutation({
    mutationFn: () => startIndexing(jobId),
    onSuccess: (d) => {
      if (d.started) toast.success('Indexing started.')
      else toast('Indexing already running.')
      statusQuery.refetch()
    },
  })

  const stats = statusQuery.data?.stats ?? {}
  const progress = statusQuery.data?.progress ?? 0
  const currentStep = statusQuery.data?.current_step ?? 'Uploaded'

  const canStart = Boolean(jobId) && !indexMut.isPending

  const onPick = (f: File) => {
    setFile(f)
    uploadMut.mutate(f)
  }

  const dropProps = useMemo(() => {
    const onDrop: React.DragEventHandler<HTMLDivElement> = (e) => {
      e.preventDefault()
      const f = e.dataTransfer.files?.[0]
      if (f) onPick(f)
    }
    const onDragOver: React.DragEventHandler<HTMLDivElement> = (e) => e.preventDefault()
    return { onDrop, onDragOver }
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <div className="panel rounded-xl p-5">
        <div className="mb-1 text-lg font-semibold">Upload Documents</div>
        <div className="text-sm text-[rgba(255,255,255,0.65)]">
          Drag-and-drop a text file for demo (PDF parsing can be added later). Then run offline indexing to build
          embeddings + graph communities.
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div
            className="panel2 flex min-h-[160px] flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(255,255,255,0.18)] p-4 text-center"
            {...dropProps}
          >
            <div className="mono text-xs text-[rgba(255,255,255,0.6)]">DROP FILE</div>
            <div className="mt-2 text-sm">Drop a .txt file here or choose one.</div>
            <label className="btn mt-3 cursor-pointer">
              <input
                type="file"
                className="hidden"
                accept=".txt,.md,.text"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) onPick(f)
                }}
              />
              Choose file
            </label>
            <div className="mt-2 mono text-xs text-[rgba(255,255,255,0.65)]">{file?.name ?? ''}</div>
          </div>

          <div className="flex flex-col gap-3">
            <div className="panel2 rounded-xl p-4">
              <div className="mono text-xs text-[rgba(255,255,255,0.65)]">CURRENT STATUS</div>
              <div className="mt-1 text-sm font-semibold">{statusQuery.data?.status ?? (jobId ? 'unknown' : '—')}</div>
              <div className="mono mt-1 text-xs text-[rgba(255,255,255,0.65)]">{currentStep}</div>
              {statusQuery.data?.error ? (
                <div className="mt-2 text-xs text-red-300">{statusQuery.data.error}</div>
              ) : null}
              <div className="mt-3 flex gap-2">
                <button className="btn" disabled={!canStart} onClick={() => indexMut.mutate()}>
                  Start Indexing
                </button>
                <button className="btn" disabled={!jobId} onClick={() => statusQuery.refetch()}>
                  Refresh
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <StatPill label="ENTITIES" value={stats.entity_count ?? 0} />
              <StatPill label="EDGES" value={stats.edge_count ?? 0} />
              <StatPill label="COMMUNITIES" value={stats.community_count ?? 0} />
            </div>
          </div>
        </div>
      </div>

      <ProgressSteps currentStep={currentStep} progress={progress} />
    </div>
  )
}


import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type SettingsState = {
  jobId: string
  setJobId: (jobId: string) => void

  chunkSize: number
  chunkOverlap: number
  hops: number
  setChunkSize: (v: number) => void
  setChunkOverlap: (v: number) => void
  setHops: (v: number) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      jobId: '',
      setJobId: (jobId) => set({ jobId }),

      chunkSize: 600,
      chunkOverlap: 100,
      hops: 2,
      setChunkSize: (chunkSize) => set({ chunkSize }),
      setChunkOverlap: (chunkOverlap) => set({ chunkOverlap }),
      setHops: (hops) => set({ hops }),
    }),
    { name: 'rag_settings' },
  ),
)


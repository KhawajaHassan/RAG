export type JobId = string

export type UploadResponse = { job_id: JobId }

export type IndexStartResponse = { job_id: JobId; started: boolean }

export type StatusResponse = {
  job_id: JobId
  status: string
  current_step: string
  progress: number
  error?: string | null
  stats: {
    entity_count?: number
    edge_count?: number
    community_count?: number
  }
}

export type QueryMode = 'vector_rag' | 'summary_rag' | 'graph_global' | 'graph_local' | 'all'

export type QueryRequest = {
  job_id: JobId
  question: string
  mode: QueryMode
}

export type QueryResult = {
  mode: string
  answer: string
  latency_ms: number
  sources: Record<string, unknown>[]
}

export type QueryResponse = {
  job_id: JobId
  question: string
  results: QueryResult[]
}

export type EntityType = 'PERSON' | 'ORG' | 'LOCATION' | 'CONCEPT' | 'EVENT'

export type GraphNode = {
  id: string
  label: string
  type: EntityType
  description: string
  degree: number
  community_level: number
  community_id?: string | null
}

export type GraphEdge = {
  id: string
  source: string
  target: string
  description: string
  weight: number
}

export type GraphStats = {
  entity_count: number
  edge_count: number
  community_count: number
}

export type CommunityResponse = {
  job_id: JobId
  level: number
  community_id: string
  title: string
  executive_summary: string
  impact_severity: number
  impact_explanation: string
  findings: string[]
  members: string[]
}

export type EvaluationEstimateRequest = {
  question_count: number
  systems: number
  runs: number
  price_per_unit_usd: number
}

export type EvaluationEstimateResponse = {
  estimated_cost_usd: number
}

export type EvaluationGenerateResponse = {
  job_id: JobId
  question_count: number
}

export type EvaluationRunResponse = {
  job_id: JobId
  started: boolean
}

export type EvaluationResultsResponse = {
  job_id: JobId
  results: Record<string, unknown>
}


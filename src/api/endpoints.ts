import { api } from './client'
import type {
  CommunityResponse,
  EvaluationEstimateRequest,
  EvaluationEstimateResponse,
  EvaluationGenerateResponse,
  EvaluationResultsResponse,
  EvaluationRunResponse,
  GraphEdge,
  GraphNode,
  GraphStats,
  IndexStartResponse,
  QueryRequest,
  QueryResponse,
  StatusResponse,
  UploadResponse,
} from './types'

export async function uploadDocument(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post<UploadResponse>('/api/upload', fd)
  return data
}

export async function startIndexing(jobId: string) {
  const { data } = await api.post<IndexStartResponse>(`/api/index/${jobId}`)
  return data
}

export async function getIndexStatus(jobId: string) {
  const { data } = await api.get<StatusResponse>(`/api/index/${jobId}/status`)
  return data
}

export async function runQuery(payload: QueryRequest) {
  const { data } = await api.post<QueryResponse>('/api/query', payload)
  return data
}

export async function getGraphStats(jobId: string) {
  const { data } = await api.get<GraphStats>(`/api/graph/${jobId}/stats`)
  return data
}

export async function getGraphNodes(jobId: string, level: number) {
  const { data } = await api.get<GraphNode[]>(`/api/graph/${jobId}/nodes`, { params: { level } })
  return data
}

export async function getGraphEdges(jobId: string) {
  const { data } = await api.get<GraphEdge[]>(`/api/graph/${jobId}/edges`)
  return data
}

export async function getCommunity(jobId: string, level: number, communityId: string) {
  const { data } = await api.get<CommunityResponse>(`/api/graph/${jobId}/community/${level}/${communityId}`)
  return data
}

export async function estimateEvaluation(jobId: string, req: EvaluationEstimateRequest) {
  const { data } = await api.post<EvaluationEstimateResponse>(`/api/evaluation/${jobId}/estimate`, req)
  return data
}

export async function generateEvaluationQuestions(jobId: string) {
  const { data } = await api.post<EvaluationGenerateResponse>(`/api/evaluation/${jobId}/generate-questions`)
  return data
}

export async function runEvaluation(jobId: string) {
  const { data } = await api.post<EvaluationRunResponse>(`/api/evaluation/${jobId}/run`)
  return data
}

export async function getEvaluationResults(jobId: string) {
  const { data } = await api.get<EvaluationResultsResponse>(`/api/evaluation/${jobId}/results`)
  return data
}

export async function clearJob(jobId: string) {
  const { data } = await api.delete(`/api/clear/${jobId}`)
  return data as { deleted: boolean; job_id: string }
}


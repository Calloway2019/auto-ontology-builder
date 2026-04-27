import request from './request'

export function buildOntology(projectId: string) {
  return request.post(`/v1/projects/${projectId}/ontology/build`)
}

export function getBuildStatus(projectId: string) {
  return request.get(`/v1/projects/${projectId}/ontology/build/status`)
}

export function getOntology(projectId: string) {
  return request.get(`/v1/projects/${projectId}/ontology`)
}

export function getOntologyVersions(projectId: string) {
  return request.get(`/v1/projects/${projectId}/ontology/versions`)
}

export function getOntologyVersionDetail(projectId: string, versionId: string) {
  return request.get(`/v1/projects/${projectId}/ontology/versions/${versionId}`)
}

// Graph
export function loadGraphData(projectId: string) {
  return request.post(`/v1/projects/${projectId}/graph/load`)
}

export function getLoadStatus(projectId: string) {
  return request.get(`/v1/projects/${projectId}/graph/load/status`)
}

export function getGraphStats(projectId: string) {
  return request.get(`/v1/projects/${projectId}/graph/stats`)
}

export function getGraphVisualization(projectId: string, limit = 500) {
  return request.get(`/v1/projects/${projectId}/graph/visualize`, { params: { limit } })
}

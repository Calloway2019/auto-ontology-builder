import request from './request'

export function listProjects() {
  return request.get('/v1/projects')
}

export function createProject(data: { name: string; description?: string }) {
  return request.post('/v1/projects', data)
}

export function getProject(id: string) {
  return request.get(`/v1/projects/${id}`)
}

export function deleteProject(id: string) {
  return request.delete(`/v1/projects/${id}`)
}

// Datasources
export function uploadFiles(projectId: string, files: File[]) {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  return request.post(`/v1/projects/${projectId}/datasources/upload`, formData)
}

export function listDatasources(projectId: string) {
  return request.get(`/v1/projects/${projectId}/datasources`)
}

export function previewDatasource(projectId: string, dsId: string) {
  return request.get(`/v1/projects/${projectId}/datasources/${dsId}/preview`)
}

export function deleteDatasource(projectId: string, dsId: string) {
  return request.delete(`/v1/projects/${projectId}/datasources/${dsId}`)
}

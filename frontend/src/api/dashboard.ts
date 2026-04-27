import request from './request'

export function listModules(projectId: string) {
  return request.get('/v1/dashboard/modules', { params: { project_id: projectId } })
}

export function createModule(data: {
  project_id: string
  title: string
  question: string
  display_type?: string
  size?: string
  refresh_interval?: number
}) {
  return request.post('/v1/dashboard/modules', data)
}

export function updateModule(moduleId: string, data: Record<string, any>) {
  return request.put(`/v1/dashboard/modules/${moduleId}`, data)
}

export function deleteModule(moduleId: string) {
  return request.delete(`/v1/dashboard/modules/${moduleId}`)
}

export function refreshModule(moduleId: string) {
  return request.post(`/v1/dashboard/modules/${moduleId}/refresh`)
}

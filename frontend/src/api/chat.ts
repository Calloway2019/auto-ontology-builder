import request from './request'

export function askQuestion(projectId: string, question: string, context = '') {
  return request.post(`/v1/projects/${projectId}/qa/ask`, { question, context })
}

export function getQAHistory(projectId: string, page = 1, pageSize = 20) {
  return request.get(`/v1/projects/${projectId}/qa/history`, {
    params: { page, page_size: pageSize },
  })
}

export function submitFeedback(projectId: string, qaId: string, feedback: number) {
  return request.post(`/v1/projects/${projectId}/qa/${qaId}/feedback`, { feedback })
}

import request from './request'

export function getSystemConfig() {
  return request.get('/v1/system/config')
}

export function updateLLMConfig(config: {
  api_key: string
  base_url: string
  model_name: string
  temperature?: number
  max_tokens?: number
}) {
  return request.put('/v1/system/config/llm', config)
}

export function testLLMConnection() {
  return request.post('/v1/system/config/llm/test')
}

export function healthCheck() {
  return request.get('/v1/system/health')
}

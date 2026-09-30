import axios, { AxiosError } from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
})

/** 统一从响应包装 {success,data,message} 中取出 data。 */
export function unwrap<T>(payload: unknown): T {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    const envelope = payload as { data: T; success?: boolean; message?: string | null }
    if (envelope.success === false) throw new Error(envelope.message || '请求失败')
    return envelope.data
  }
  return payload as T
}

/** 把任何请求异常归一化为用户可读文案。 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    if (!error.response) return '无法连接后端服务，请确认 FastAPI 已启动（localhost:8000）'
    const detail = (error.response.data as { detail?: unknown; message?: string | null })?.detail
    const message = (error.response.data as { message?: string | null })?.message
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined
      if (first?.msg) return `参数校验失败：${first.msg}`
    }
    if (message) return message
    return `请求失败（HTTP ${error.response.status}）`
  }
  if (error instanceof Error) return error.message
  return '未知错误'
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => Promise.reject(error),
)

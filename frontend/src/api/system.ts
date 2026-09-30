import { apiClient } from './client'
import type { HealthStatus, SystemInfo } from '../types'

function unwrap<T>(payload: any): T {
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data as T
  return payload as T
}

export async function getHealth() {
  const res = await apiClient.get('/health')
  return unwrap<HealthStatus>(res.data)
}

export async function getSystemInfo() {
  const res = await apiClient.get('/system/info')
  return unwrap<SystemInfo>(res.data)
}

// WebSocket job-progress client for eterzion_upscale_api (api/eterzion_upscale_api).
// Extracted from services/api.ts (formerly apiClient.ts) — socket lifecycle
// (open/onmessage/onerror/close) is a genuinely separable responsibility from the
// request/response HTTP functions there (research.md Audit c/d).

import { BASE_URL, type JobStatus } from './api'

/** Subscribes to live progress for a job over the API's WebSocket. Returns an
 *  unsubscribe function. Falls back silently if the socket errors — callers should
 *  still poll getJob() once as a fallback if they need a guaranteed final state. */
export function subscribeJobProgress(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  onError?: (error: Event) => void
): () => void {
  const wsUrl = `${BASE_URL.replace('http', 'ws')}/ws/jobs/${jobId}`
  const ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      onUpdate(JSON.parse(event.data))
    } catch {
      // ignore malformed frame
    }
  }
  if (onError) ws.onerror = onError
  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) ws.close()
  }
}

import { useEffect, useRef, useState } from 'react'

export function useWebSocket(projectId: string | undefined) {
  const wsRef = useRef<WebSocket | null>(null)
  const [progress, setProgress] = useState<any>(null)

  useEffect(() => {
    if (!projectId) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/projects/${projectId}/ws`)
    ws.onmessage = (e) => {
      try { setProgress(JSON.parse(e.data)) } catch { /* ignore parse errors */ }
    }
    wsRef.current = ws
    return () => { ws.close() }
  }, [projectId])

  return { progress }
}

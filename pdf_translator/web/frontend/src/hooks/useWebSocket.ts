import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(projectId: string | undefined) {
  const wsRef = useRef<WebSocket | null>(null)
  const [progress, setProgress] = useState<any>(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!projectId || !mountedRef.current) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/projects/${projectId}/ws`)

    ws.onopen = () => { if (mountedRef.current) setConnected(true) }
    ws.onmessage = (e) => {
      try { if (mountedRef.current) setProgress(JSON.parse(e.data)) } catch { /* ignore parse errors */ }
    }
    ws.onclose = () => {
      if (mountedRef.current) {
        setConnected(false)
        reconnectTimer.current = setTimeout(connect, 3000)
      }
    }
    ws.onerror = () => { ws.close() }
    wsRef.current = ws
  }, [projectId])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { progress, connected }
}

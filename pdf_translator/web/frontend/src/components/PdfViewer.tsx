import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

// Configure worker
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url,
).toString()

interface Props {
  projectId: string
  currentPage: number
  onPageChange: (page: number) => void
  totalPages: number
  onTotalPages: (total: number) => void
}

export function PdfViewer({ projectId, currentPage, onPageChange, totalPages, onTotalPages }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Load PDF document
  useEffect(() => {
    setLoading(true)
    setError(null)
    const url = `/api/projects/${projectId}/pdf`
    pdfjsLib.getDocument(url).promise
      .then((doc) => {
        setPdf(doc)
        onTotalPages(doc.numPages)
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load PDF')
        setLoading(false)
      })
  }, [projectId])

  // Render current page
  useEffect(() => {
    if (!pdf || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    pdf.getPage(currentPage).then((page) => {
      const containerWidth = containerRef.current?.clientWidth || 600
      const unscaledViewport = page.getViewport({ scale: 1 })
      const scale = (containerWidth - 32) / unscaledViewport.width
      const viewport = page.getViewport({ scale })

      canvas.height = viewport.height
      canvas.width = viewport.width

      page.render({ canvas, viewport }).promise
    })
  }, [pdf, currentPage])

  if (loading) {
    return <div className="flex items-center justify-center h-full text-gray-500">Loading PDF...</div>
  }

  if (error) {
    return <div className="flex items-center justify-center h-full text-red-400">{error}</div>
  }

  return (
    <div ref={containerRef} className="h-full flex flex-col">
      {/* Page navigation */}
      <div className="flex items-center justify-center gap-2 py-2 border-b border-gray-800 text-xs">
        <button onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
          &larr;
        </button>
        <span className="text-gray-400">
          Page {currentPage} / {totalPages}
        </span>
        <button onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage >= totalPages}
          className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
          &rarr;
        </button>
      </div>
      {/* Canvas */}
      <div className="flex-1 overflow-auto p-4 flex justify-center bg-gray-900/50">
        <canvas ref={canvasRef} className="shadow-lg" />
      </div>
    </div>
  )
}

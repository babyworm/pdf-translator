import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getProject, getDraft, startTranslation } from '../api'
import { TranslatedPanel } from '../components/TranslatedPanel'
import { GlossaryPanel } from '../components/GlossaryPanel'
import { StatusBar } from '../components/StatusBar'
import { PdfViewer } from '../components/PdfViewer'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Project, Draft } from '../types'

export function TranslationView() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [showGlossary, setShowGlossary] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const { progress, connected } = useWebSocket(id)

  useEffect(() => {
    if (!id) return
    getProject(id).then(setProject)
    getDraft(id).then(setDraft)
  }, [id])

  useEffect(() => {
    if (progress?.status === 'done' && id) {
      getProject(id).then(setProject)
      getDraft(id).then(setDraft)
    }
  }, [progress, id])

  const handleStartTranslation = async () => {
    if (!id) return
    await startTranslation(id, { target_lang: 'ko', backend: 'auto' })
    setProject((p) => p ? { ...p, status: 'translating' } : p)
  }

  if (!project) return <div className="p-6 text-gray-500">Loading...</div>

  // Filter elements for the current page on the right panel
  const pageElements = draft ? draft.elements.filter(el => el.page === currentPage) : []

  return (
    <div className="flex flex-col h-[calc(100vh-49px)]">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800 text-sm">
        <span className="font-medium">{project.filename}</span>
        <div className="flex gap-2">
          {project.status === 'uploaded' && (
            <button onClick={handleStartTranslation}
              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 rounded text-xs">
              Start Translation
            </button>
          )}
          <button onClick={() => setShowGlossary(!showGlossary)}
            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs">
            {showGlossary ? 'Hide' : 'Show'} Glossary
          </button>
        </div>
      </div>

      {/* Error state */}
      {project.status === 'error' && (
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 mx-4 mt-4">
          <p className="text-red-400 font-medium">Translation failed</p>
          <p className="text-red-400/70 text-sm mt-1">Check backend availability and try again.</p>
          <button onClick={handleStartTranslation}
            className="mt-2 px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Original PDF */}
        <div className="flex-1 border-r border-gray-800 flex flex-col">
          <div className="px-3 py-2 bg-gray-900/50 text-xs text-gray-500 border-b border-gray-800">
            Original ({project.source_lang || 'auto'})
          </div>
          {project.status !== 'uploaded' ? (
            <PdfViewer
              projectId={id!}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
              totalPages={totalPages}
              onTotalPages={setTotalPages}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
              Click "Start Translation" to begin
            </div>
          )}
        </div>

        {/* Right: Translated */}
        <div className="flex-1 flex flex-col">
          <div className="px-3 py-2 bg-gray-900/50 text-xs text-gray-500 border-b border-gray-800">
            Translated ({project.target_lang || 'ko'}) -- Click to edit
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {draft ? (
              <TranslatedPanel projectId={id!} elements={pageElements} onUpdate={() => getDraft(id!).then(setDraft)} />
            ) : null}
          </div>
        </div>
      </div>

      {/* Bottom panels */}
      {showGlossary && (
        <div className="h-48 border-t border-gray-800">
          <GlossaryPanel />
        </div>
      )}

      <StatusBar project={project} draft={draft} connected={connected} />
    </div>
  )
}

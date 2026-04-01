import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getProject, getDraft, startTranslation } from '../api'
import { TranslatedPanel } from '../components/TranslatedPanel'
import { GlossaryPanel } from '../components/GlossaryPanel'
import { StatusBar } from '../components/StatusBar'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Project, Draft } from '../types'

export function TranslationView() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [showGlossary, setShowGlossary] = useState(false)
  const { progress } = useWebSocket(id)

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

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Original */}
        <div className="flex-1 border-r border-gray-800 flex flex-col">
          <div className="px-3 py-2 bg-gray-900/50 text-xs text-gray-500 border-b border-gray-800">
            Original ({project.source_lang || 'auto'})
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {draft ? draft.elements.map((el) => (
              <div key={el.index} className="mb-3 p-2 rounded hover:bg-gray-900/50">
                {el.type === 'heading' ? (
                  <h3 className="font-bold text-lg">{el.original}</h3>
                ) : (
                  <p className="text-sm text-gray-300 leading-relaxed">{el.original}</p>
                )}
              </div>
            )) : (
              <p className="text-gray-500 text-sm">
                {project.status === 'uploaded' ? 'Click "Start Translation" to begin' :
                 project.status === 'translating' ? 'Translating...' : 'No content'}
              </p>
            )}
          </div>
        </div>

        {/* Right: Translated */}
        <div className="flex-1 flex flex-col">
          <div className="px-3 py-2 bg-gray-900/50 text-xs text-gray-500 border-b border-gray-800">
            Translated ({project.target_lang || 'ko'}) -- Click to edit
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {draft ? (
              <TranslatedPanel projectId={id!} elements={draft.elements} onUpdate={() => getDraft(id!).then(setDraft)} />
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

      <StatusBar project={project} draft={draft} />
    </div>
  )
}

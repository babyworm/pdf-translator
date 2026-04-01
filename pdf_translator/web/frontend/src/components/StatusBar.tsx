import { exportPdf, exportMd } from '../api'
import type { Project, Draft } from '../types'

interface Props {
  project: Project
  draft: Draft | null
}

export function StatusBar({ project, draft }: Props) {
  const elements = draft?.elements || []
  const accepted = elements.filter((e) => e.status === 'accepted').length
  const modified = elements.filter((e) => e.status === 'modified').length
  const pending = elements.filter((e) => e.status === 'pending').length
  const total = elements.length
  const pct = total > 0 ? Math.round(((accepted + modified) / total) * 100) : 0

  const handleExport = async (type: 'pdf' | 'md') => {
    const blob = type === 'pdf' ? await exportPdf(project.id) : await exportMd(project.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.filename.replace('.pdf', '')}_translated.${type}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-t border-gray-800 text-xs">
      <div className="flex items-center gap-4">
        <span>Status: <span className="font-medium">{project.status}</span></span>
        {total > 0 && (
          <>
            <span className="text-green-400">Accepted: {accepted}</span>
            <span className="text-yellow-400">Modified: {modified}</span>
            <span className="text-gray-400">Pending: {pending}</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-2">
        {total > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full" style={{ width: `${pct}%` }} />
            </div>
            <span>{pct}%</span>
          </div>
        )}
        {project.status === 'done' && (
          <>
            <button onClick={() => handleExport('pdf')}
              className="px-2 py-1 bg-green-600 hover:bg-green-500 rounded">Export PDF</button>
            <button onClick={() => handleExport('md')}
              className="px-2 py-1 bg-indigo-600 hover:bg-indigo-500 rounded">Export MD</button>
          </>
        )}
      </div>
    </div>
  )
}

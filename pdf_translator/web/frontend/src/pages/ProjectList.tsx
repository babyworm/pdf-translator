import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, createProject } from '../api'
import type { Project } from '../types'

export function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([])
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => { listProjects().then(setProjects) }, [])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const result = await createProject(file)
      navigate(`/project/${result.id}`)
    } finally { setUploading(false) }
  }

  const statusColor: Record<string, string> = {
    uploaded: 'bg-gray-600', translating: 'bg-yellow-600',
    done: 'bg-green-600', error: 'bg-red-600',
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button onClick={() => fileRef.current?.click()}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium"
          disabled={uploading}>
          {uploading ? 'Uploading...' : 'Upload PDF'}
        </button>
        <input ref={fileRef} type="file" accept=".pdf" className="hidden"
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">No projects yet</p>
          <p className="text-sm mt-2">Upload a PDF to get started</p>
        </div>
      ) : (
        <div className="space-y-2">
          {projects.map((p) => (
            <div key={p.id} onClick={() => navigate(`/project/${p.id}`)}
              className="flex items-center justify-between p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 cursor-pointer">
              <div>
                <div className="font-medium">{p.filename}</div>
                <div className="text-sm text-gray-500 mt-1">
                  {p.segments_translated}/{p.segments_total} segments
                </div>
              </div>
              <span className={`px-2 py-1 rounded text-xs font-medium ${statusColor[p.status] || 'bg-gray-600'}`}>
                {p.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

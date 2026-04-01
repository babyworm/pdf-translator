import { useState } from 'react'
import { updateSegment } from '../api'
import type { DraftElement } from '../types'

interface Props {
  projectId: string
  element: DraftElement
  onSave: () => void
  onCancel: () => void
}

export function SegmentEditor({ projectId, element, onSave, onCancel }: Props) {
  const [text, setText] = useState(element.user_edit || element.translated || '')

  const handleSave = async () => {
    await updateSegment(projectId, element.index, { user_edit: text, status: 'modified' })
    onSave()
  }

  return (
    <div className="mb-3 p-3 rounded border border-indigo-600 bg-gray-900">
      <div className="text-xs text-gray-500 mb-2">Original: {element.original}</div>
      <textarea value={text} onChange={(e) => setText(e.target.value)}
        className="w-full bg-gray-800 text-gray-100 rounded p-2 text-sm border border-gray-700 focus:border-indigo-500 focus:outline-none"
        rows={3} />
      <div className="flex gap-2 mt-2 justify-end">
        <button onClick={onCancel} className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded">Cancel</button>
        <button onClick={handleSave} className="px-3 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 rounded">Save</button>
      </div>
    </div>
  )
}

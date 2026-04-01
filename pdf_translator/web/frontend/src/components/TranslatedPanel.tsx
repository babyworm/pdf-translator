import { useState } from 'react'
import { SegmentEditor } from './SegmentEditor'
import type { DraftElement } from '../types'

interface Props {
  projectId: string
  elements: DraftElement[]
  onUpdate: () => void
}

export function TranslatedPanel({ projectId, elements, onUpdate }: Props) {
  const [editingIdx, setEditingIdx] = useState<number | null>(null)

  const statusIcon: Record<string, string> = {
    accepted: 'V', modified: 'E', rejected: 'X', pending: '...',
  }
  const statusColor: Record<string, string> = {
    accepted: 'border-transparent', modified: 'border-yellow-600 bg-yellow-950/30',
    rejected: 'border-red-600', pending: 'border-gray-600',
  }

  return (
    <div>
      {elements.map((el) => (
        <div key={el.index}>
          {editingIdx === el.index ? (
            <SegmentEditor projectId={projectId} element={el}
              onSave={() => { setEditingIdx(null); onUpdate() }}
              onCancel={() => setEditingIdx(null)} />
          ) : (
            <div onClick={() => setEditingIdx(el.index)}
              className={`mb-3 p-2 rounded border cursor-pointer hover:border-gray-500 ${statusColor[el.status] || ''}`}>
              {el.type === 'heading' ? (
                <h3 className="font-bold text-lg">{el.user_edit || el.translated || el.original}</h3>
              ) : (
                <p className="text-sm text-gray-300 leading-relaxed">{el.user_edit || el.translated || el.original}</p>
              )}
              <span className="float-right text-xs text-gray-600">{statusIcon[el.status]} {el.status}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { listGlossaries, createGlossary, importGlossaryCsv } from '../api'
import type { Glossary } from '../types'

export function GlossaryPanel() {
  const [glossaries, setGlossaries] = useState<Glossary[]>([])
  const [selected, setSelected] = useState<Glossary | null>(null)
  const [newSource, setNewSource] = useState('')
  const [newTarget, setNewTarget] = useState('')

  useEffect(() => { listGlossaries().then(setGlossaries) }, [])

  const handleAddTerm = async () => {
    if (!newSource.trim()) return
    if (selected) {
      const updated = { ...selected.entries, [newSource]: newTarget || newSource }
      await fetch(`/api/glossaries/${selected.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries: updated }),
      })
      setSelected({ ...selected, entries: updated })
    } else {
      const g = await createGlossary('Custom', { [newSource]: newTarget || newSource })
      setGlossaries([g, ...glossaries])
      setSelected(g)
    }
    setNewSource(''); setNewTarget('')
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const g = await importGlossaryCsv(file)
    setGlossaries([g, ...glossaries])
    setSelected(g)
  }

  return (
    <div className="flex h-full text-sm">
      {/* Left: glossary list */}
      <div className="w-48 border-r border-gray-800 p-2 overflow-y-auto">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-500">Glossaries</span>
          <label className="text-xs text-indigo-400 cursor-pointer hover:text-indigo-300">
            Import
            <input type="file" accept=".csv" className="hidden" onChange={handleImport} />
          </label>
        </div>
        {glossaries.map((g) => (
          <div key={g.id} onClick={() => setSelected(g)}
            className={`p-2 rounded cursor-pointer text-xs ${selected?.id === g.id ? 'bg-gray-800' : 'hover:bg-gray-900'}`}>
            {g.name} ({Object.keys(g.entries).length})
          </div>
        ))}
      </div>

      {/* Right: entries */}
      <div className="flex-1 p-2 overflow-y-auto">
        {selected ? (
          <>
            <div className="grid grid-cols-3 gap-px bg-gray-800 mb-2 text-xs">
              <div className="bg-gray-900 p-1.5 text-gray-500">Source</div>
              <div className="bg-gray-900 p-1.5 text-gray-500">Target</div>
              <div className="bg-gray-900 p-1.5 text-gray-500">Rule</div>
              {Object.entries(selected.entries).map(([s, t]) => (
                <div key={s} className="contents">
                  <div className="bg-gray-950 p-1.5">{s}</div>
                  <div className="bg-gray-950 p-1.5 text-green-400">{t}</div>
                  <div className="bg-gray-950 p-1.5 text-yellow-500">
                    {s.toLowerCase() === t.toLowerCase() ? 'keep' : 'translate'}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-1">
              <input value={newSource} onChange={(e) => setNewSource(e.target.value)}
                placeholder="Source" className="flex-1 bg-gray-800 rounded px-2 py-1 text-xs border border-gray-700" />
              <input value={newTarget} onChange={(e) => setNewTarget(e.target.value)}
                placeholder="Target" className="flex-1 bg-gray-800 rounded px-2 py-1 text-xs border border-gray-700" />
              <button onClick={handleAddTerm} className="px-2 py-1 bg-indigo-600 rounded text-xs">Add</button>
            </div>
          </>
        ) : (
          <div className="text-gray-500 text-xs p-4">Select or import a glossary</div>
        )}
      </div>
    </div>
  )
}

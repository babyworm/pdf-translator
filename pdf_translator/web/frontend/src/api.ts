const BASE = '/api'

export async function listProjects(): Promise<any[]> {
  const res = await fetch(`${BASE}/projects`)
  return res.json()
}

export async function createProject(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/projects`, { method: 'POST', body: form })
  return res.json()
}

export async function getProject(id: string) {
  const res = await fetch(`${BASE}/projects/${id}`)
  return res.json()
}

export async function startTranslation(id: string, opts: { target_lang: string; backend: string; glossary_id?: string }) {
  const res = await fetch(`${BASE}/projects/${id}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  return res.json()
}

export async function getDraft(id: string) {
  const res = await fetch(`${BASE}/projects/${id}/draft`)
  if (!res.ok) return null
  return res.json()
}

export async function updateSegment(projectId: string, idx: number, data: { user_edit?: string; status?: string }) {
  const res = await fetch(`${BASE}/projects/${projectId}/draft/${idx}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return res.json()
}

export async function exportPdf(id: string) {
  const res = await fetch(`${BASE}/projects/${id}/export/pdf`, { method: 'POST' })
  return res.blob()
}

export async function exportMd(id: string) {
  const res = await fetch(`${BASE}/projects/${id}/export/md`, { method: 'POST' })
  return res.blob()
}

export async function listGlossaries() {
  const res = await fetch(`${BASE}/glossaries`)
  return res.json()
}

export async function createGlossary(name: string, entries: Record<string, string>) {
  const res = await fetch(`${BASE}/glossaries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, entries }),
  })
  return res.json()
}

export async function importGlossaryCsv(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/glossaries/import`, { method: 'POST', body: form })
  return res.json()
}

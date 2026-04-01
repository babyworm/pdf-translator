export interface Project {
  id: string
  filename: string
  status: 'uploaded' | 'extracting' | 'translating' | 'done' | 'error'
  segments_total: number
  segments_translated: number
  created_at: string
  source_lang?: string
  target_lang?: string
  backend?: string
}

export interface DraftElement {
  index: number
  type: string
  original: string
  translated: string | null
  status: 'accepted' | 'modified' | 'rejected' | 'pending'
  user_edit: string | null
  page: number
  bbox: number[]
  confidence?: number
}

export interface Draft {
  source_file: string
  source_lang: string
  target_lang: string
  backend: string
  created_at: string
  elements: DraftElement[]
  glossary_applied: string[]
}

export interface GlossaryEntry {
  source: string
  target: string
}

export interface Glossary {
  id: string
  name: string
  entries: Record<string, string>
  created_at: string
}

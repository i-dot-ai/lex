/**
 * Projects - localStorage utilities
 * Data layer for managing research projects and documents
 */

// ============================================================================
// Types
// ============================================================================

export interface Project {
  id: string
  name: string
  description: string
  created: Date
  updated: Date
  color?: string
  documents: ProjectDocument[]
  queries: SavedQuery[]
  researchGoal?: string
  tags: string[]
  status: 'active' | 'archived' | 'completed'
}

export interface ProjectDocument {
  id: string
  documentId: string
  type: 'legislation' | 'caselaw'
  addedAt: Date
  addedBy: 'user' | 'agent'
  notes: string
  tags: string[]
  agentSummary?: string
  relevanceScore?: number
  metadata: {
    title: string
    year: number
    legislationType?: string
    court?: string
    citation?: string
  }
}

export interface SavedQuery {
  id: string
  query: string
  filters: Record<string, unknown>
  executedAt: Date
  executedBy: 'user' | 'agent'
  documentsAdded: string[]
}

export interface ProjectsStorage {
  version: '1.0'
  projects: Project[]
  lastUpdated: Date
}

// ============================================================================
// Constants
// ============================================================================

const STORAGE_KEY = 'lex_projects'
const STORAGE_VERSION = '1.0'

// ============================================================================
// Storage Utilities
// ============================================================================

function getStorage(): ProjectsStorage {
  if (typeof window === 'undefined') {
    return {
      version: STORAGE_VERSION,
      projects: [],
      lastUpdated: new Date()
    }
  }

  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) {
    return {
      version: STORAGE_VERSION,
      projects: [],
      lastUpdated: new Date()
    }
  }

  try {
    const parsed = JSON.parse(stored) as ProjectsStorage

    // Parse dates
    parsed.projects = parsed.projects.map(p => ({
      ...p,
      created: new Date(p.created),
      updated: new Date(p.updated),
      documents: p.documents.map(d => ({
        ...d,
        addedAt: new Date(d.addedAt)
      })),
      queries: p.queries.map(q => ({
        ...q,
        executedAt: new Date(q.executedAt)
      }))
    }))

    return parsed
  } catch (error) {
    console.error('Error parsing projects from localStorage:', error)
    return {
      version: STORAGE_VERSION,
      projects: [],
      lastUpdated: new Date()
    }
  }
}

function setStorage(data: ProjectsStorage): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  try {
    const serialized = JSON.stringify(data)
    localStorage.setItem(STORAGE_KEY, serialized)
    return true
  } catch (error) {
    if (error instanceof Error && error.name === 'QuotaExceededError') {
      console.error('localStorage quota exceeded. Consider archiving old projects.')
      return false
    }
    console.error('Error saving projects to localStorage:', error)
    return false
  }
}

// ============================================================================
// Project CRUD
// ============================================================================

export function getAllProjects(): Project[] {
  const storage = getStorage()
  return storage.projects.sort((a, b) => b.updated.getTime() - a.updated.getTime())
}

export function getProject(id: string): Project | null {
  const storage = getStorage()
  return storage.projects.find(p => p.id === id) || null
}

export function createProject(data: {
  name: string
  description?: string
  color?: string
  researchGoal?: string
}): Project {
  const project: Project = {
    id: crypto.randomUUID(),
    name: data.name,
    description: data.description || '',
    created: new Date(),
    updated: new Date(),
    color: data.color,
    documents: [],
    queries: [],
    researchGoal: data.researchGoal,
    tags: [],
    status: 'active'
  }

  const storage = getStorage()
  storage.projects.push(project)
  storage.lastUpdated = new Date()
  setStorage(storage)

  return project
}

export function updateProject(
  id: string,
  updates: Partial<Omit<Project, 'id' | 'created'>>
): Project | null {
  const storage = getStorage()
  const index = storage.projects.findIndex(p => p.id === id)

  if (index === -1) {
    return null
  }

  const existingProject = storage.projects[index]
  if (!existingProject) {
    return null
  }

  storage.projects[index] = {
    ...existingProject,
    ...updates,
    updated: new Date()
  }

  storage.lastUpdated = new Date()
  setStorage(storage)

  return storage.projects[index] ?? null
}

export function deleteProject(id: string): boolean {
  const storage = getStorage()
  const index = storage.projects.findIndex(p => p.id === id)

  if (index === -1) {
    return false
  }

  storage.projects.splice(index, 1)
  storage.lastUpdated = new Date()
  setStorage(storage)

  return true
}

// ============================================================================
// Document Management
// ============================================================================

export function addDocumentToProject(
  projectId: string,
  document: Omit<ProjectDocument, 'id' | 'addedAt'>
): ProjectDocument | null {
  const storage = getStorage()
  const project = storage.projects.find(p => p.id === projectId)

  if (!project) {
    return null
  }

  // Check for duplicates
  const exists = project.documents.some(d => d.documentId === document.documentId)
  if (exists) {
    return null
  }

  const newDocument: ProjectDocument = {
    ...document,
    id: crypto.randomUUID(),
    addedAt: new Date()
  }

  project.documents.push(newDocument)
  project.updated = new Date()
  storage.lastUpdated = new Date()
  setStorage(storage)

  return newDocument
}

export function removeDocumentFromProject(
  projectId: string,
  documentId: string
): boolean {
  const storage = getStorage()
  const project = storage.projects.find(p => p.id === projectId)

  if (!project) {
    return false
  }

  const index = project.documents.findIndex(d => d.id === documentId)
  if (index === -1) {
    return false
  }

  project.documents.splice(index, 1)
  project.updated = new Date()
  storage.lastUpdated = new Date()
  setStorage(storage)

  return true
}

export function updateDocumentNotes(
  projectId: string,
  documentId: string,
  notes: string
): boolean {
  const storage = getStorage()
  const project = storage.projects.find(p => p.id === projectId)

  if (!project) {
    return false
  }

  const document = project.documents.find(d => d.id === documentId)
  if (!document) {
    return false
  }

  document.notes = notes
  project.updated = new Date()
  storage.lastUpdated = new Date()
  setStorage(storage)

  return true
}

export function updateDocumentTags(
  projectId: string,
  documentId: string,
  tags: string[]
): boolean {
  const storage = getStorage()
  const project = storage.projects.find(p => p.id === projectId)

  if (!project) {
    return false
  }

  const document = project.documents.find(d => d.id === documentId)
  if (!document) {
    return false
  }

  document.tags = tags
  project.updated = new Date()
  storage.lastUpdated = new Date()
  setStorage(storage)

  return true
}

// ============================================================================
// Query Management
// ============================================================================

export function addQueryToProject(
  projectId: string,
  query: Omit<SavedQuery, 'id' | 'executedAt'>
): SavedQuery | null {
  const storage = getStorage()
  const project = storage.projects.find(p => p.id === projectId)

  if (!project) {
    return null
  }

  const newQuery: SavedQuery = {
    ...query,
    id: crypto.randomUUID(),
    executedAt: new Date()
  }

  project.queries.push(newQuery)
  project.updated = new Date()
  storage.lastUpdated = new Date()
  setStorage(storage)

  return newQuery
}

// ============================================================================
// Utilities
// ============================================================================

export function isDocumentInProject(
  projectId: string,
  documentId: string
): boolean {
  const project = getProject(projectId)
  if (!project) {
    return false
  }

  return project.documents.some(d => d.documentId === documentId)
}

export function getProjectsContainingDocument(documentId: string): Project[] {
  const storage = getStorage()
  return storage.projects.filter(p =>
    p.documents.some(d => d.documentId === documentId)
  )
}

export function getDocumentCount(projectId: string): number {
  const project = getProject(projectId)
  return project?.documents.length || 0
}

// ============================================================================
// Export / Import
// ============================================================================

export interface ExportData {
  version: string
  exportedAt: string
  projects: Project[]
}

export function exportProjects(projectIds?: string[]): ExportData {
  const storage = getStorage()
  const projects = projectIds
    ? storage.projects.filter(p => projectIds.includes(p.id))
    : storage.projects

  return {
    version: STORAGE_VERSION,
    exportedAt: new Date().toISOString(),
    projects
  }
}

export function exportProjectAsJSON(projectId: string): string {
  const project = getProject(projectId)
  if (!project) {
    throw new Error('Project not found')
  }

  const data: ExportData = {
    version: STORAGE_VERSION,
    exportedAt: new Date().toISOString(),
    projects: [project]
  }

  return JSON.stringify(data, null, 2)
}

export function downloadProjectJSON(projectId: string): void {
  if (typeof window === 'undefined') {
    return
  }

  const json = exportProjectAsJSON(projectId)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `lex-project-${projectId}-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export function importProjects(data: ExportData): boolean {
  try {
    const storage = getStorage()

    // Merge projects (skip duplicates by ID)
    const existingIds = new Set(storage.projects.map(p => p.id))
    const newProjects = data.projects.filter(p => !existingIds.has(p.id))

    storage.projects.push(...newProjects)
    storage.lastUpdated = new Date()

    return setStorage(storage)
  } catch (error) {
    console.error('Error importing projects:', error)
    return false
  }
}

// ============================================================================
// Validation
// ============================================================================

export function validateProject(project: Partial<Project>): {
  valid: boolean
  errors: string[]
} {
  const errors: string[] = []

  if (!project.name || project.name.trim().length === 0) {
    errors.push('Project name is required')
  }

  if (project.name && project.name.length > 100) {
    errors.push('Project name must be 100 characters or less')
  }

  if (project.description && project.description.length > 500) {
    errors.push('Project description must be 500 characters or less')
  }

  return {
    valid: errors.length === 0,
    errors
  }
}

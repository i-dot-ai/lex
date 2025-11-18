/**
 * Search History Management
 * Stores recent searches in localStorage for quick access
 */

const STORAGE_KEY = 'lex_search_history'
const MAX_HISTORY_ITEMS = 50

export interface SearchHistoryItem {
  id: string
  query: string
  type: 'legislation' | 'caselaw'
  timestamp: Date
  filters?: {
    // Legislation filters
    legislationTypes?: string[]
    yearFrom?: number
    yearTo?: number

    // Caselaw filters
    courts?: string[]
    divisions?: string[]
  }
  resultCount?: number
}

interface SearchHistoryStorage {
  version: '1.0'
  items: SearchHistoryItem[]
  lastUpdated: Date
}

/**
 * Get all search history items
 */
export function getSearchHistory(): SearchHistoryItem[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    if (!data) return []

    const storage: SearchHistoryStorage = JSON.parse(data)

    // Convert date strings back to Date objects
    return storage.items.map(item => ({
      ...item,
      timestamp: new Date(item.timestamp)
    }))
  } catch (error) {
    console.error('Failed to load search history:', error)
    return []
  }
}

/**
 * Get search history filtered by type
 */
export function getSearchHistoryByType(type: 'legislation' | 'caselaw'): SearchHistoryItem[] {
  return getSearchHistory().filter(item => item.type === type)
}

/**
 * Add a search to history
 */
export function addToSearchHistory(
  query: string,
  type: 'legislation' | 'caselaw',
  filters?: SearchHistoryItem['filters'],
  resultCount?: number
): void {
  try {
    const history = getSearchHistory()

    // Don't add empty queries
    if (!query.trim()) return

    // Check if this exact search already exists (same query, type, and filters)
    const existingIndex = history.findIndex(item =>
      item.query === query &&
      item.type === type &&
      JSON.stringify(item.filters) === JSON.stringify(filters)
    )

    // If exists, move it to the top instead of adding duplicate
    if (existingIndex !== -1) {
      const existing = history.splice(existingIndex, 1)[0]
      if (existing) {
        existing.timestamp = new Date()
        existing.resultCount = resultCount
        history.unshift(existing)
      }
    } else {
      // Add new item at the beginning
      const newItem: SearchHistoryItem = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        query,
        type,
        timestamp: new Date(),
        filters,
        resultCount
      }
      history.unshift(newItem)
    }

    // Keep only MAX_HISTORY_ITEMS
    const trimmed = history.slice(0, MAX_HISTORY_ITEMS)

    const storage: SearchHistoryStorage = {
      version: '1.0',
      items: trimmed,
      lastUpdated: new Date()
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(storage))
  } catch (error) {
    console.error('Failed to save search history:', error)
  }
}

/**
 * Remove a specific search from history
 */
export function removeFromSearchHistory(id: string): void {
  try {
    const history = getSearchHistory()
    const filtered = history.filter(item => item.id !== id)

    const storage: SearchHistoryStorage = {
      version: '1.0',
      items: filtered,
      lastUpdated: new Date()
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(storage))
  } catch (error) {
    console.error('Failed to remove from search history:', error)
  }
}

/**
 * Clear all search history
 */
export function clearSearchHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    console.error('Failed to clear search history:', error)
  }
}

/**
 * Clear search history by type
 */
export function clearSearchHistoryByType(type: 'legislation' | 'caselaw'): void {
  try {
    const history = getSearchHistory()
    const filtered = history.filter(item => item.type !== type)

    const storage: SearchHistoryStorage = {
      version: '1.0',
      items: filtered,
      lastUpdated: new Date()
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(storage))
  } catch (error) {
    console.error('Failed to clear search history by type:', error)
  }
}

/**
 * Format a relative time string
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`

  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: diffDays > 365 ? 'numeric' : undefined
  })
}

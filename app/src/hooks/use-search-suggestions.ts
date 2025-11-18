import { useState, useEffect, useCallback } from 'react'
import { getSearchHistoryByType } from '@/lib/search-history'

interface SearchSuggestions {
  recentSearches: string[]
  aiSuggestions: string[]
  isLoading: boolean
  error: string | null
}

const DEFAULT_SUGGESTIONS = {
  legislation: [
    'Data protection compliance requirements',
    'Employment law updates 2024',
    'Corporate governance obligations',
    'Consumer protection regulations'
  ],
  caselaw: [
    'Human rights case precedents',
    'Commercial contract disputes',
    'Employment tribunal decisions',
    'Property law judgments'
  ]
}

export function useSearchSuggestions(searchType: 'legislation' | 'caselaw'): SearchSuggestions {
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generateAISuggestions = useCallback(async (queries: string[]) => {
    if (queries.length === 0) {
      setAiSuggestions(DEFAULT_SUGGESTIONS[searchType])
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/suggestions/from-history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recentQueries: queries,
          searchType
        })
      })

      if (!response.ok) {
        throw new Error('Failed to generate suggestions')
      }

      const data = await response.json()
      setAiSuggestions(data.suggestions || DEFAULT_SUGGESTIONS[searchType])
    } catch (err) {
      console.error('Error generating AI suggestions:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
      setAiSuggestions(DEFAULT_SUGGESTIONS[searchType])
    } finally {
      setIsLoading(false)
    }
  }, [searchType])

  useEffect(() => {
    // Get recent search history
    const history = getSearchHistoryByType(searchType)
    const recentQueries = history
      .slice(0, 3) // Last 3 searches
      .map(item => item.query)
      .filter((query, index, self) => self.indexOf(query) === index) // Remove duplicates

    setRecentSearches(recentQueries)

    // Generate AI suggestions based on recent searches
    generateAISuggestions(recentQueries)
  }, [searchType, generateAISuggestions])

  // Listen for changes to search history
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'lex_search_history') {
        // Refresh suggestions when history changes
        const history = getSearchHistoryByType(searchType)
        const recentQueries = history
          .slice(0, 3)
          .map(item => item.query)
          .filter((query, index, self) => self.indexOf(query) === index)

        setRecentSearches(recentQueries)
        generateAISuggestions(recentQueries)
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [searchType, generateAISuggestions])

  return {
    recentSearches,
    aiSuggestions,
    isLoading,
    error
  }
}
import { useEffect, useRef } from 'react'
import { addToSearchHistory, type SearchHistoryItem } from '@/lib/search-history'

interface UseSearchHistoryTrackingOptions {
  type: 'legislation' | 'caselaw'
  query: string
  filters: SearchHistoryItem['filters']
  resultCount: number
  enabled: boolean
}

/**
 * Automatically tracks searches in search history
 * Only saves when query changes and there are results
 */
export function useSearchHistoryTracking({
  type,
  query,
  filters,
  resultCount,
  enabled
}: UseSearchHistoryTrackingOptions) {
  const lastSavedQueryRef = useRef<string>('')

  useEffect(() => {
    if (!enabled || !query || resultCount === 0) {
      return
    }

    // Only save if this is a different query than last saved
    if (query !== lastSavedQueryRef.current) {
      addToSearchHistory(query, type, filters, resultCount)
      lastSavedQueryRef.current = query
    }
  }, [enabled, query, type, filters, resultCount])
}

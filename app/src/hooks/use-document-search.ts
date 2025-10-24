import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useRouter } from 'next/navigation'
import { API_CONFIG, PAGINATION } from '@/lib/config'
import { addToSearchHistory, type SearchHistoryItem } from '@/lib/search-history'

export type SortOption = 'relevance' | 'date-desc' | 'date-asc' | 'title-asc' | 'title-desc'

interface DocumentSearchConfig<TResult, TFilter> {
  // Document type
  type: 'legislation' | 'caselaw'

  // API configuration
  endpoint: string

  // Default values
  defaultFilters: TFilter
  defaultYearTo: string

  // Filter handling
  parseFiltersFromUrl: (params: URLSearchParams) => TFilter
  buildFilterParamsForUrl: (filters: TFilter) => Record<string, string>
  buildSearchHistoryFilters: (filters: TFilter, yearFrom?: string, yearTo?: string) => SearchHistoryItem['filters']

  // API request building
  buildApiRequestBody: (params: {
    query: string
    filters: TFilter
    yearFrom?: string
    yearTo?: string
    currentPage: number
    pageSize: number
  }) => unknown

  // Response handling
  getResults: (response: unknown) => TResult[]
  getTotal: (response: unknown) => number

  // Client-side operations
  sortResults: (results: TResult[], sortBy: SortOption) => TResult[]
  filterResults: (results: TResult[], filterText: string) => TResult[]
}

export function useDocumentSearch<TResult, TFilter>(
  config: DocumentSearchConfig<TResult, TFilter>
) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const searchInputRef = useRef<HTMLInputElement>(null)

  // State
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [yearFrom, setYearFrom] = useState(searchParams.get('year_from') || '')
  const [yearTo, setYearTo] = useState(searchParams.get('year_to') || config.defaultYearTo)
  const [filters, setFilters] = useState<TFilter>(() => config.parseFiltersFromUrl(searchParams))
  const [sortBy, setSortBy] = useState<SortOption>('relevance')
  const [filterText, setFilterText] = useState('')
  const [previewItem, setPreviewItem] = useState<TResult | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const currentPage = parseInt(searchParams.get('page') || '1')

  // Keyboard shortcut: Cmd/Ctrl+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // TanStack Query for fetching results
  const { data: response, isLoading, error } = useQuery({
    queryKey: [config.type, query, filters, yearFrom, yearTo, currentPage],
    queryFn: async () => {
      if (!query) return null

      const requestBody = config.buildApiRequestBody({
        query,
        filters,
        yearFrom,
        yearTo,
        currentPage,
        pageSize: PAGINATION.DEFAULT_PAGE_SIZE,
      })

      const res = await fetch(`${API_CONFIG.baseUrl}${config.endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })

      if (!res.ok) {
        throw new Error('Search failed')
      }

      return res.json()
    },
    enabled: !!query,
  })

  const results = response ? config.getResults(response) : []
  const total = response ? config.getTotal(response) : 0

  // Sort results client-side
  const sortedResults = config.sortResults([...results], sortBy)

  // Filter results client-side
  const filteredResults = config.filterResults(sortedResults, filterText)

  // Handle search submission
  const handleSearch = useCallback(() => {
    const params = new URLSearchParams()
    params.set('q', query)
    if (yearFrom) params.set('year_from', yearFrom)
    if (yearTo) params.set('year_to', yearTo)

    const filterParams = config.buildFilterParamsForUrl(filters)
    Object.entries(filterParams).forEach(([key, value]) => {
      params.set(key, value)
    })

    params.set('page', '1')

    // Save to history on explicit search submission
    if (query.trim()) {
      addToSearchHistory(
        query,
        config.type,
        config.buildSearchHistoryFilters(filters, yearFrom, yearTo),
        total
      )
    }

    router.push(`/${config.type}?${params.toString()}`)
  }, [query, yearFrom, yearTo, filters, router, config, total])

  // Handle selecting from search history
  const handleSelectFromHistory = useCallback((item: SearchHistoryItem) => {
    setQuery(item.query)
    setYearFrom(item.filters?.yearFrom?.toString() || '')
    setYearTo(item.filters?.yearTo?.toString() || config.defaultYearTo)

    // Parse filters from history item based on type
    if (config.type === 'legislation') {
      setFilters(item.filters?.legislationTypes as TFilter || config.defaultFilters)
    } else {
      setFilters(item.filters?.courts as TFilter || config.defaultFilters)
    }

    // Trigger search
    const params = new URLSearchParams()
    params.set('q', item.query)
    if (item.filters?.yearFrom) params.set('year_from', item.filters.yearFrom.toString())
    if (item.filters?.yearTo) params.set('year_to', item.filters.yearTo.toString())

    // Build filter params
    const filterParams = config.buildFilterParamsForUrl(filters)
    Object.entries(filterParams).forEach(([key, value]) => {
      params.set(key, value)
    })

    params.set('page', '1')

    router.push(`/${config.type}?${params.toString()}`)
  }, [router, config, filters])

  // Handle page change
  const handlePageChange = useCallback((page: number) => {
    // Save to history when user browses to additional pages (shows interest)
    // Skip page 1 since handleSearch already saved it
    if (page > 1 && query.trim() && total > 0) {
      addToSearchHistory(
        query,
        config.type,
        config.buildSearchHistoryFilters(filters, yearFrom, yearTo),
        total
      )
    }

    const params = new URLSearchParams(searchParams.toString())
    params.set('page', page.toString())
    router.push(`/${config.type}?${params.toString()}`)
  }, [searchParams, router, config, query, filters, yearFrom, yearTo, total])

  // Clear all filters
  const clearFilters = useCallback(() => {
    setQuery('')
    setYearFrom('')
    setYearTo(config.defaultYearTo)
    setFilters(config.defaultFilters)
    router.push(`/${config.type}`)
  }, [router, config])

  // Handle preview
  const openPreview = useCallback((item: TResult) => {
    // Save to history when user engages with results
    if (query.trim() && total > 0) {
      addToSearchHistory(
        query,
        config.type,
        config.buildSearchHistoryFilters(filters, yearFrom, yearTo),
        total
      )
    }

    setPreviewItem(item)
    setPreviewOpen(true)
  }, [query, config, filters, yearFrom, yearTo, total])

  const closePreview = useCallback(() => {
    setPreviewOpen(false)
  }, [])

  const totalPages = Math.ceil(total / PAGINATION.DEFAULT_PAGE_SIZE)
  const hasResults = results.length > 0
  const showEmptyState = !isLoading && !hasResults && !!query

  return {
    // State
    query,
    setQuery,
    yearFrom,
    setYearFrom,
    yearTo,
    setYearTo,
    filters,
    setFilters,
    sortBy,
    setSortBy,
    filterText,
    setFilterText,
    currentPage,

    // Results
    results: filteredResults,
    total,
    totalPages,
    hasResults,
    showEmptyState,
    isLoading,
    error,

    // Preview
    previewItem,
    previewOpen,
    openPreview,
    closePreview,
    setPreviewOpen,

    // Handlers
    handleSearch,
    handleSelectFromHistory,
    handlePageChange,
    clearFilters,

    // Refs
    searchInputRef,
  }
}

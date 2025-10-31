import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { API_CONFIG } from '@/lib/config'

interface LegislationResult {
  id: string
  uri: string
  title: string
  description: string
  type: string
  year: number
  number: number
  status: string
  extent: string[]
}

export function useLegislationPrefetch() {
  const queryClient = useQueryClient()

  const prefetchLegislation = useCallback((legislation: LegislationResult) => {
    // Prefetch sections data
    queryClient.prefetchQuery({
      queryKey: ['legislation-sections', legislation.uri],
      queryFn: async () => {
        const res = await fetch(`${API_CONFIG.baseUrl}/legislation/sections`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uri: legislation.uri }),
        })
        if (!res.ok) throw new Error('Failed to fetch sections')
        return res.json()
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
    })

    // Prefetch HTML content
    queryClient.prefetchQuery({
      queryKey: ['legislation-html', legislation.uri],
      queryFn: async () => {
        const res = await fetch(`${API_CONFIG.baseUrl}/legislation/html`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uri: legislation.uri }),
        })
        if (!res.ok) throw new Error('Failed to fetch HTML')
        return res.json()
      },
      staleTime: 10 * 60 * 1000, // 10 minutes
    })
  }, [queryClient])

  return { prefetchLegislation }
}
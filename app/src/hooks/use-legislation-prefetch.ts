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
      queryKey: ['legislation-sections', legislation.id],
      queryFn: async () => {
        const response = await fetch(`${API_CONFIG.baseUrl}/legislation/section/lookup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            legislation_id: legislation.id,
            limit: 100
          })
        })
        if (!response.ok) throw new Error('Failed to fetch sections')
        return response.json()
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
    })

    // Build legislation path for HTML
    const typeMap = {
      'ukpga': 'ukpga',
      'uksi': 'uksi',
      'asp': 'asp',
      'asc': 'asc',
      'anaw': 'anaw',
      'mnia': 'nia',
      'ukci': 'ukci',
      'ukla': 'ukla',
      'ukcm': 'ukcm',
      'uksro': 'uksro',
      'nisro': 'nisro',
      'wsi': 'wsi',
      'ssi': 'ssi',
      'nisi': 'nisi',
      'nisr': 'nisr',
    }
    const legislationType = typeMap[legislation.type as keyof typeof typeMap] || legislation.type
    const legislationPath = `${legislationType}/${legislation.year}/${legislation.number}`

    // Prefetch HTML content
    queryClient.prefetchQuery({
      queryKey: ['legislation-html', legislation.id],
      queryFn: async () => {
        const response = await fetch(`${API_CONFIG.baseUrl}/legislation/proxy/${legislationPath}/data.html`)
        if (!response.ok) throw new Error('Failed to fetch HTML')
        return response.text()
      },
      staleTime: 24 * 60 * 60 * 1000, // 24 hours - legislation is immutable
      gcTime: 24 * 60 * 60 * 1000,    // 24 hours - keep in memory
    })
  }, [queryClient])

  return { prefetchLegislation }
}
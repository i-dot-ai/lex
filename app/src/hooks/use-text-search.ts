import { useEffect, useState, useCallback, RefObject } from 'react'

interface UseTextSearchOptions {
  containerRef: RefObject<HTMLElement | null>
  searchText: string
}

interface UseTextSearchReturn {
  matchCount: number
  currentIndex: number
  goToNext: () => void
  goToPrevious: () => void
  clearSearch: () => void
}

// Inject CSS for highlight styles (bypasses Next.js CSS parser)
const injectHighlightStyles = () => {
  if (typeof document === 'undefined') return
  if (document.getElementById('highlight-styles')) return

  const style = document.createElement('style')
  style.id = 'highlight-styles'
  style.textContent = `
    ::highlight(search-matches) {
      background-color: rgb(254 240 138);
      color: inherit;
    }

    .dark ::highlight(search-matches) {
      background-color: rgb(133 77 14);
      color: inherit;
    }

    ::highlight(search-current) {
      background-color: rgb(251 146 60);
      color: rgb(0 0 0);
    }

    .dark ::highlight(search-current) {
      background-color: rgb(234 88 12);
      color: rgb(255 255 255);
    }
  `
  document.head.appendChild(style)
}

export function useTextSearch({ containerRef, searchText }: UseTextSearchOptions): UseTextSearchReturn {
  const [matchCount, setMatchCount] = useState(0)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [ranges, setRanges] = useState<Range[]>([])

  // Inject styles on first mount
  useEffect(() => {
    injectHighlightStyles()
  }, [])

  // Find all matches and create ranges
  useEffect(() => {
    if (!containerRef.current || !searchText || searchText.length < 2) {
      // Clear highlights
      CSS.highlights?.clear()
      setMatchCount(0)
      setCurrentIndex(0)
      setRanges([])
      return
    }

    const container = containerRef.current
    const searchLower = searchText.toLowerCase()
    const foundRanges: Range[] = []

    // Use TreeWalker to find all text nodes
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) => {
          const parent = node.parentElement
          if (!parent || parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE') {
            return NodeFilter.FILTER_REJECT
          }
          return node.textContent?.toLowerCase().includes(searchLower)
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT
        }
      }
    )

    // Collect all text nodes
    const textNodes: Text[] = []
    let node: Node | null
    while ((node = walker.nextNode())) {
      textNodes.push(node as Text)
    }

    // Create ranges for each match
    textNodes.forEach(textNode => {
      const text = textNode.textContent || ''
      const textLower = text.toLowerCase()
      let startIndex = 0

      while (startIndex < text.length) {
        const index = textLower.indexOf(searchLower, startIndex)
        if (index === -1) break

        const range = new Range()
        range.setStart(textNode, index)
        range.setEnd(textNode, index + searchText.length)
        foundRanges.push(range)

        startIndex = index + 1
      }
    })

    setRanges(foundRanges)
    setMatchCount(foundRanges.length)
    setCurrentIndex(foundRanges.length > 0 ? 0 : -1)

    // Create highlights using CSS Custom Highlight API
    if (typeof CSS !== 'undefined' && CSS.highlights) {
      // All matches highlight
      const allMatchesHighlight = new Highlight(...foundRanges)
      CSS.highlights.set('search-matches', allMatchesHighlight)

      // Current match highlight (will be updated separately)
      if (foundRanges.length > 0) {
        const firstRange = foundRanges[0]
        if (firstRange) {
          const currentHighlight = new Highlight(firstRange)
          CSS.highlights.set('search-current', currentHighlight)

          // Scroll to first match
          const rect = firstRange.getBoundingClientRect()
          const scrollContainer = container.closest('[data-radix-scroll-area-viewport]') || container
          const containerRect = scrollContainer.getBoundingClientRect()

          if (rect.top < containerRect.top || rect.bottom > containerRect.bottom) {
            firstRange.startContainer.parentElement?.scrollIntoView({
              behavior: 'smooth',
              block: 'center'
            })
          }
        }
      }
    }

    return () => {
      CSS.highlights?.clear()
    }
  }, [containerRef, searchText])

  // Update current match highlight
  useEffect(() => {
    if (typeof CSS === 'undefined' || !CSS.highlights || ranges.length === 0 || currentIndex < 0) return

    const range = ranges[currentIndex]
    if (!range) return

    const currentHighlight = new Highlight(range)
    CSS.highlights.set('search-current', currentHighlight)

    // Scroll to current match
    const rect = range.getBoundingClientRect()
    const container = containerRef.current
    if (!container) return

    const scrollContainer = container.closest('[data-radix-scroll-area-viewport]') || container
    const containerRect = scrollContainer.getBoundingClientRect()

    if (rect.top < containerRect.top || rect.bottom > containerRect.bottom) {
      range.startContainer.parentElement?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  }, [currentIndex, ranges, containerRef])

  const goToNext = useCallback(() => {
    if (ranges.length === 0) return
    setCurrentIndex((prev) => (prev + 1) % ranges.length)
  }, [ranges.length])

  const goToPrevious = useCallback(() => {
    if (ranges.length === 0) return
    setCurrentIndex((prev) => (prev - 1 + ranges.length) % ranges.length)
  }, [ranges.length])

  const clearSearch = useCallback(() => {
    CSS.highlights?.clear()
    setMatchCount(0)
    setCurrentIndex(0)
    setRanges([])
  }, [])

  return {
    matchCount,
    currentIndex: currentIndex >= 0 ? currentIndex + 1 : 0, // Convert to 1-indexed for display
    goToNext,
    goToPrevious,
    clearSearch
  }
}

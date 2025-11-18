"use client"

import { useState, RefObject, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Search, X, ChevronUp, ChevronDown } from "lucide-react"
import { useTextSearch } from "@/hooks/use-text-search"

interface TextSearchProps {
  containerRef: RefObject<HTMLElement | null>
  placeholder?: string
  onClose?: () => void
}

export function TextSearch({ containerRef, placeholder = "Search...", onClose }: TextSearchProps) {
  const [searchText, setSearchText] = useState("")
  const { matchCount, currentIndex, goToNext, goToPrevious, clearSearch } = useTextSearch({
    containerRef,
    searchText
  })

  const handleClear = () => {
    setSearchText("")
    clearSearch()
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle if search is active
      if (!searchText || matchCount === 0) return

      // Enter = Next, Shift+Enter = Previous
      if (e.key === 'Enter') {
        e.preventDefault()
        if (e.shiftKey) {
          goToPrevious()
        } else {
          goToNext()
        }
      }

      // Escape = Clear
      if (e.key === 'Escape') {
        handleClear()
        onClose?.()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [searchText, matchCount, goToNext, goToPrevious, handleClear, onClose])

  return (
    <div className="flex gap-2 items-center">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          placeholder={placeholder}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="pl-9 pr-9 h-9"
        />
        {searchText && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {matchCount > 0 && (
        <>
          <div className="text-sm text-muted-foreground whitespace-nowrap min-w-[60px] text-center">
            {currentIndex} of {matchCount}
          </div>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={goToPrevious}
              className="h-9 w-9 p-0"
              title="Previous match (Shift+Enter)"
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={goToNext}
              className="h-9 w-9 p-0"
              title="Next match (Enter)"
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

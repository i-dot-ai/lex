"use client"

import { useState, useEffect } from "react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { History, X, Trash2 } from "lucide-react"
import {
  getSearchHistoryByType,
  removeFromSearchHistory,
  clearSearchHistoryByType,
  formatRelativeTime,
  type SearchHistoryItem,
} from "@/lib/search-history"

interface SearchHistoryDropdownProps {
  type: 'legislation' | 'caselaw'
  onSelectSearch: (item: SearchHistoryItem) => void
  variant?: 'default' | 'compact'
}

export function SearchHistoryDropdown({ type, onSelectSearch, variant = 'default' }: SearchHistoryDropdownProps) {
  const [history, setHistory] = useState<SearchHistoryItem[]>([])
  const [open, setOpen] = useState(false)

  // Load history on mount and when type changes
  useEffect(() => {
    setHistory(getSearchHistoryByType(type))
  }, [type])

  // Reload history when dropdown opens (to get fresh data)
  useEffect(() => {
    if (open) {
      setHistory(getSearchHistoryByType(type))
    }
  }, [open, type])

  const handleSelectSearch = (item: SearchHistoryItem) => {
    onSelectSearch(item)
    setOpen(false)
  }

  const handleRemoveItem = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    removeFromSearchHistory(id)
    setHistory(prev => prev.filter(item => item.id !== id))
  }

  const handleClearAll = (e: React.MouseEvent) => {
    e.stopPropagation()
    clearSearchHistoryByType(type)
    setHistory([])
  }

  const formatFilters = (item: SearchHistoryItem): string => {
    const parts: string[] = []

    if (item.filters?.legislationTypes?.length) {
      parts.push(item.filters.legislationTypes.join(', ').toUpperCase())
    }

    if (item.filters?.courts?.length) {
      parts.push(item.filters.courts.join(', ').toUpperCase())
    }

    if (item.filters?.divisions?.length) {
      parts.push(item.filters.divisions.join(', ').toUpperCase())
    }

    if (item.filters?.yearFrom || item.filters?.yearTo) {
      const yearRange = [
        item.filters.yearFrom || '',
        item.filters.yearTo || ''
      ].filter(Boolean).join('-')
      if (yearRange) parts.push(yearRange)
    }

    return parts.length > 0 ? ` • ${parts.join(' • ')}` : ''
  }

  if (history.length === 0 && open) {
    return (
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          {variant === 'compact' ? (
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              <History className="h-4 w-4" />
            </Button>
          ) : (
            <Button variant="ghost" size="sm" className="gap-2">
              <History className="h-4 w-4" />
              History
            </Button>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-80">
          <DropdownMenuLabel>Search History</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <div className="p-4 text-center text-sm text-muted-foreground">
            No search history yet
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        {variant === 'compact' ? (
          <Button variant="ghost" size="sm" className="h-8 px-2 gap-1">
            <History className="h-4 w-4" />
            <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-xs font-medium">
              {history.length}
            </span>
          </Button>
        ) : (
          <Button variant="ghost" size="sm" className="gap-2">
            <History className="h-4 w-4" />
            History
            {history.length > 0 && (
              <span className="ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium">
                {history.length}
              </span>
            )}
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[400px]">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">Recent Searches</DropdownMenuLabel>
          {history.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearAll}
              className="h-auto px-2 py-1 text-xs text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-3 w-3 mr-1" />
              Clear all
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />
        <ScrollArea className="max-h-[400px]">
          {history.map((item) => (
            <DropdownMenuItem
              key={item.id}
              className="flex items-start gap-2 p-3 cursor-pointer"
              onClick={() => handleSelectSearch(item)}
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium line-clamp-1">
                  {item.query}
                </div>
                <div className="text-xs text-muted-foreground line-clamp-1">
                  {formatRelativeTime(item.timestamp)}
                  {item.resultCount !== undefined && ` • ${item.resultCount} results`}
                  {formatFilters(item)}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => handleRemoveItem(e, item.id)}
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </Button>
            </DropdownMenuItem>
          ))}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

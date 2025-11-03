"use client"

import { useSearchSuggestions } from "@/hooks/use-search-suggestions"
import { Button } from "@/components/ui/button"
import { Clock, Sparkles } from "lucide-react"

interface SuggestionItemProps {
  query: string
  onClick: (query: string) => void
  type: 'recent' | 'ai'
}

function SuggestionItem({ query, onClick, type }: SuggestionItemProps) {
  const colorClasses = type === 'recent' 
    ? 'bg-sky-50 hover:bg-sky-100 border-sky-100 hover:border-sky-200'
    : 'bg-fuchsia-50 hover:bg-fuchsia-100 border-fuchsia-100 hover:border-fuchsia-200'
  
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => onClick(query)}
      className={`justify-start h-auto p-3 text-sm font-normal 
                 shadow-sm hover:shadow-md transition-all duration-200 ${colorClasses}`}
    >
      {query}
    </Button>
  )
}

interface SearchSuggestionsProps {
  searchType: 'legislation' | 'caselaw'
  onSuggestionClick: (query: string) => void
  className?: string
}

export function SearchSuggestions({ 
  searchType, 
  onSuggestionClick, 
  className = "" 
}: SearchSuggestionsProps) {
  const { recentSearches, aiSuggestions, isLoading } = useSearchSuggestions(searchType)

  const hasAnySuggestions = recentSearches.length > 0 || aiSuggestions.length > 0

  if (!hasAnySuggestions && !isLoading) {
    return null
  }

  return (
    <div className={`bg-card border border-border/40 rounded-lg p-4 space-y-4 ${className}`}>
      {recentSearches.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            Recent searches
          </h3>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((query, index) => (
              <SuggestionItem
                key={`recent-${index}`}
                query={query}
                onClick={onSuggestionClick}
                type="recent"
              />
            ))}
          </div>
        </div>
      )}

      {recentSearches.length > 0 && (aiSuggestions.length > 0 || isLoading) && (
        <div className="border-t border-border/20" />
      )}

      {(aiSuggestions.length > 0 || isLoading) && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            {recentSearches.length > 0 ? 'Based on your history' : 'Suggested searches'}
          </h3>
          <div className="flex flex-wrap gap-2">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={`loading-${index}`}
                  className="h-10 w-32 bg-muted/30 animate-pulse rounded-md"
                />
              ))
            ) : (
              aiSuggestions.map((query, index) => (
                <SuggestionItem
                  key={`ai-${index}`}
                  query={query}
                  onClick={onSuggestionClick}
                  type="ai"
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
import { SearchX, Lightbulb } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface EmptyStateProps {
  query?: string
  onClear?: () => void
  onSuggestionClick?: (suggestion: string) => void
  type?: 'legislation' | 'caselaw'
}

const SUGGESTIONS = {
  legislation: [
    "Data Protection Act 2018",
    "Human Rights Act 1998",
    "Freedom of Information Act 2000",
    "Equality Act 2010",
    "Companies Act 2006"
  ],
  caselaw: [
    "breach of contract",
    "negligence",
    "judicial review",
    "unfair dismissal",
    "reasonable force"
  ]
}

export function EmptyState({ query, onClear, onSuggestionClick, type = 'legislation' }: EmptyStateProps) {
  const suggestions = SUGGESTIONS[type]

  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center py-12">
        <SearchX className="h-16 w-16 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">No results found</h3>
        {query ? (
          <p className="text-sm text-muted-foreground text-center mb-4">
            We couldn&apos;t find any documents matching &quot;{query}&quot;
          </p>
        ) : (
          <p className="text-sm text-muted-foreground text-center mb-4">
            Try searching for something
          </p>
        )}
        <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground mb-4">
          <p>Try:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Using different keywords</li>
            <li>Checking your spelling</li>
            <li>Removing some filters</li>
          </ul>
        </div>
        {onClear && (
          <Button variant="outline" onClick={onClear} className="mb-4">
            Clear all filters
          </Button>
        )}

        {onSuggestionClick && (
          <div className="w-full max-w-2xl pt-4 border-t">
            <div className="flex items-center justify-center gap-2 mb-3 text-sm text-muted-foreground">
              <Lightbulb className="h-4 w-4" />
              <span>Try these popular searches:</span>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {suggestions.map((suggestion) => (
                <Button
                  key={suggestion}
                  variant="secondary"
                  size="sm"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="text-xs"
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

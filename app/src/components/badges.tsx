import { Badge } from "@/components/ui/badge"
import { CheckCircle2, FileEdit } from "lucide-react"
import { cn } from "@/lib/utils"

// Status badge for legislation
// Based on actual data: "final" (68,785 docs), "revised" (56,317 docs)
export function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { variant: "default" | "secondary" | "destructive" | "outline", className: string, icon: React.ReactNode }> = {
    "final": {
      variant: "default",
      className: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
      icon: <CheckCircle2 className="h-3 w-3" />
    },
    "revised": {
      variant: "secondary",
      className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      icon: <FileEdit className="h-3 w-3" />
    },
  }

  const config = statusConfig[status.toLowerCase()] || {
    variant: "outline" as const,
    className: "",
    icon: null
  }

  return (
    <Badge variant={config.variant} className={cn("text-xs", config.className)}>
      {config.icon}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  )
}

// Extent badges for geographical coverage
export function ExtentBadges({ extent }: { extent: string[] }) {
  if (!extent || extent.length === 0) return null

  // Filter out empty strings and whitespace-only strings
  const validExtent = extent.filter(e => e && e.trim().length > 0)

  if (validExtent.length === 0) return null

  return (
    <>
      {validExtent.map((e) => (
        <Badge key={e} variant="outline" className="text-xs">
          {e}
        </Badge>
      ))}
    </>
  )
}

// Legislation type badge
export function LegislationTypeBadge({ type, year, number }: { type: string; year: number; number: number }) {
  return (
    <Badge variant="secondary" className="text-xs font-mono">
      {type.toUpperCase()} {year}/{number}
    </Badge>
  )
}

// Court badge for caselaw
export function CourtBadge({ court, division }: { court: string; division?: string }) {
  return (
    <Badge variant="default" className="text-xs bg-blue-600">
      {court.toUpperCase()}
      {division && ` / ${division.toUpperCase()}`}
    </Badge>
  )
}

// Citation badge
export function CitationBadge({ citation }: { citation: string }) {
  return (
    <Badge variant="outline" className="text-xs font-mono">
      {citation}
    </Badge>
  )
}

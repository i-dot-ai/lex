import { ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface SourceGovAuLinkProps {
  href: string
  source?: "legislation"
  variant?: "inline" | "button" | "primary"
  className?: string
  children?: React.ReactNode
}

/**
 * Attribution link back to the original source on legislation.gov.au.
 *
 * All content displayed in this app is derived from the Federal Register of
 * Legislation at https://www.legislation.gov.au and is reused under the
 * Terms of Use at https://www.legislation.gov.au/terms-of-use.
 * This component surfaces the link-back required by those terms.
 */
export function SourceGovAuLink({
  href,
  source = "legislation",
  variant = "button",
  className,
  children,
}: SourceGovAuLinkProps) {
  const externalIconSize = variant === "primary" ? "h-4 w-4" : "h-3 w-3"

  const defaultText = (
    <>
      <span className="font-semibold">legislation</span>.gov.au
    </>
  )

  if (variant === "button") {
    return (
      <Button variant="outline" size="sm" asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={cn("gap-1.5", className)}
          aria-label={`View on legislation.gov.au (opens in new tab)`}
        >
          <AuGovIcon />
          <span className="text-sm">{children || defaultText}</span>
          <ExternalLink className={externalIconSize} />
        </a>
      </Button>
    )
  }

  if (variant === "primary") {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-2 w-full px-4 py-3 rounded-md text-sm font-medium justify-center transition-colors",
          "bg-[#00698f] text-white hover:bg-[#005570] active:bg-[#004460]",
          "min-h-[44px]", // WCAG minimum touch target
          className
        )}
        aria-label={`View on legislation.gov.au (opens in new tab)`}
      >
        <AuGovIcon inverted />
        <span>{children || defaultText}</span>
        <ExternalLink className={externalIconSize} />
      </a>
    )
  }

  // inline variant
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "inline-flex items-center gap-1.5 text-sm text-primary hover:underline transition-colors",
        className
      )}
      aria-label={`View on legislation.gov.au (opens in new tab)`}
    >
      <AuGovIcon />
      <span>{children || defaultText}</span>
      <ExternalLink className={externalIconSize} />
    </a>
  )
}

/**
 * Small inline SVG badge representing the Australian Government.
 * Uses the Commonwealth gold and blue colour scheme.
 */
function AuGovIcon({ inverted = false }: { inverted?: boolean }) {
  const bg = inverted ? "white" : "#00698f"
  const fg = inverted ? "#00698f" : "white"
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
      className="flex-shrink-0"
    >
      <circle cx="8" cy="8" r="7.5" fill={bg} />
      <text
        x="8"
        y="11.5"
        textAnchor="middle"
        fontSize="6.5"
        fontWeight="700"
        fontFamily="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        fill={fg}
      >
        AU
      </text>
    </svg>
  )
}

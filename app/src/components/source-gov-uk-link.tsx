import Image from "next/image"
import { ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface SourceGovUkLinkProps {
  href: string
  source: "legislation" | "caselaw"
  variant?: "inline" | "button" | "primary"
  className?: string
  children?: React.ReactNode
}

export function SourceGovUkLink({
  href,
  source,
  variant = "button",
  className,
  children,
}: SourceGovUkLinkProps) {
  const iconSize = 16
  const externalIconSize = variant === "primary" ? "h-4 w-4" : "h-3 w-3"

  const defaultText = source === "legislation"
    ? <><span className="font-semibold">legislation</span>.gov.uk</>
    : <><span className="font-semibold">caselaw</span>.nationalarchives.gov.uk</>

  // Button variant - use actual Button component
  if (variant === "button") {
    return (
      <Button variant="outline" size="sm" asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={cn("gap-1.5 font-roboto", className)}
        >
          <Image
            src="/uk-govt-crest.png"
            alt="UK Government"
            width={iconSize}
            height={iconSize}
            className="flex-shrink-0"
          />
          <span className="text-sm">
            {children || defaultText}
          </span>
          <ExternalLink className={externalIconSize} />
        </a>
      </Button>
    )
  }

  // Inline and primary variants - use plain anchor
  const variantClasses = {
    inline: "gap-1.5 text-sm text-primary hover:underline",
    primary: "gap-2 w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm font-medium justify-center",
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "inline-flex items-center font-roboto transition-colors",
        variantClasses[variant],
        className
      )}
    >
      <Image
        src="/uk-govt-crest.png"
        alt="UK Government"
        width={iconSize}
        height={iconSize}
        className={cn(
          "flex-shrink-0",
          variant === "primary" && "brightness-0 invert"
        )}
      />
      <span>
        {children || defaultText}
      </span>
      <ExternalLink className={externalIconSize} />
    </a>
  )
}

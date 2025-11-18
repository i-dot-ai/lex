/**
 * Citation formatting utilities for UK legislation and caselaw
 * Supports OSCOLA, Bluebook, Plain text, and Markdown formats
 */

export type CitationFormat = 'oscola' | 'bluebook' | 'plain' | 'markdown'

interface LegislationCitation {
  title: string
  type: string
  year: number
  number: number
  uri: string
}

interface CaselawCitation {
  name: string
  court: string
  year: number
  number: number
  cite_as?: string
  date: string
  id: string
}

/**
 * Format legislation citation according to specified format
 */
export function formatLegislationCitation(
  legislation: LegislationCitation,
  format: CitationFormat
): string {
  const typeUpper = legislation.type.toUpperCase()
  const citation = `${typeUpper} ${legislation.year}/${legislation.number}`

  switch (format) {
    case 'oscola':
      // OSCOLA: Title, Type Year/Number
      return `${legislation.title}, ${citation}`

    case 'bluebook':
      // Bluebook: Title, Type Year/Number (UK)
      return `${legislation.title}, ${citation} (UK)`

    case 'markdown':
      // Markdown with link
      return `[${legislation.title}](${legislation.uri}) (${citation})`

    case 'plain':
    default:
      // Plain text: Title (Type Year/Number)
      return `${legislation.title} (${citation})`
  }
}

/**
 * Format caselaw citation according to specified format
 */
export function formatCaselawCitation(
  caselaw: CaselawCitation,
  format: CitationFormat
): string {
  const neutralCitation = `[${caselaw.year}] ${caselaw.court.toUpperCase()} ${caselaw.number}`
  const year = new Date(caselaw.date).getFullYear()

  switch (format) {
    case 'oscola':
      // OSCOLA: Name [Year] Court Number
      // If there's a parallel citation, include it
      if (caselaw.cite_as) {
        return `${caselaw.name} ${neutralCitation}, ${caselaw.cite_as}`
      }
      return `${caselaw.name} ${neutralCitation}`

    case 'bluebook':
      // Bluebook: Name, Citation (Court Year)
      const court = formatCourtForBluebook(caselaw.court)
      if (caselaw.cite_as) {
        return `${caselaw.name}, ${caselaw.cite_as} (${court} ${year})`
      }
      return `${caselaw.name}, ${neutralCitation} (${court} ${year})`

    case 'markdown':
      // Markdown with link
      if (caselaw.cite_as) {
        return `[${caselaw.name}](${caselaw.id}) ${neutralCitation}, ${caselaw.cite_as}`
      }
      return `[${caselaw.name}](${caselaw.id}) ${neutralCitation}`

    case 'plain':
    default:
      // Plain text: Name [Year] Court Number
      if (caselaw.cite_as) {
        return `${caselaw.name} ${neutralCitation} (${caselaw.cite_as})`
      }
      return `${caselaw.name} ${neutralCitation}`
  }
}

/**
 * Format court name for Bluebook style
 */
function formatCourtForBluebook(court: string): string {
  const courtMap: Record<string, string> = {
    uksc: 'UK Sup. Ct.',
    ukpc: 'Privy Council',
    ewca: 'Eng. & Wales Ct. App.',
    ewhc: 'Eng. & Wales High Ct.',
    ewcr: 'Crown Ct.',
    ewcc: 'County Ct.',
    ewfc: 'Fam. Ct.',
    ukut: 'Upper Trib.',
    ukftt: 'First-tier Trib.',
  }

  return courtMap[court.toLowerCase()] || court.toUpperCase()
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    return false
  }
}

/**
 * Get citation format display name
 */
export function getCitationFormatLabel(format: CitationFormat): string {
  switch (format) {
    case 'oscola':
      return 'OSCOLA'
    case 'bluebook':
      return 'Bluebook'
    case 'markdown':
      return 'Markdown'
    case 'plain':
      return 'Plain Text'
  }
}

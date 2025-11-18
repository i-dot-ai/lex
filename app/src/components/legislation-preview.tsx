"use client"

import { useState, useRef, useEffect, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { API_CONFIG } from "@/lib/config"
import DOMPurify from 'isomorphic-dompurify'
import { SourceGovUkLink } from "@/components/source-gov-uk-link"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ExternalLink,
  AlertCircle,
  Copy,
  Check,
  Link2,
  List,
  ChevronUp,
  ChevronDown,
  X,
  Star,
  Target,
  Eye,
  ScrollText,
  Search,
} from "lucide-react"
import { StatusBadge, ExtentBadges, LegislationTypeBadge } from "./badges"
import { TextSearch } from "./text-search"
import {
  formatLegislationCitation,
  copyToClipboard,
  getCitationFormatLabel,
  type CitationFormat,
} from "@/lib/citations"

interface RelevantSection {
  number: string
  type: string
  score: number
}

interface LegislationPreviewProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  legislation: {
    id: string
    uri: string
    title: string
    description: string
    type: string
    year: number
    number: number
    status: string
    extent: string[]
    enactment_date?: string
    publisher?: string
  }
  relevantSections?: RelevantSection[]
}

interface LegislationSection {
  id: string
  title: string
  text: string
  number: number
  provision_type: string
}

interface CitingCase {
  id: string
  name: string
  year: number
  court: string
  number: number
}

export function LegislationPreview({ open, onOpenChange, legislation, relevantSections }: LegislationPreviewProps) {
  const [activeTab, setActiveTab] = useState("overview")
  const [copiedFormat, setCopiedFormat] = useState<CitationFormat | null>(null)
  const [showToc, setShowToc] = useState(true)
  const [activeSection, setActiveSection] = useState<string | null>(null)
  const [currentRelevantIndex, setCurrentRelevantIndex] = useState(0)
  const [showRelevanceNav, setShowRelevanceNav] = useState(true)
  const [searchExpanded, setSearchExpanded] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  // Handle citation copy
  const handleCopyCitation = async (format: CitationFormat) => {
    const citation = formatLegislationCitation(
      {
        title: legislation.title,
        type: legislation.type,
        year: legislation.year,
        number: legislation.number,
        uri: legislation.uri,
      },
      format
    )

    const success = await copyToClipboard(citation)
    if (success) {
      setCopiedFormat(format)
      setTimeout(() => setCopiedFormat(null), 2000)
    }
  }

  // Handle copy full text
  const handleCopyFullText = async () => {
    if (!htmlContent) return

    // Strip HTML tags and get plain text
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = htmlContent
    const plainText = tempDiv.textContent || tempDiv.innerText || ''

    const success = await copyToClipboard(plainText)
    if (success) {
      setCopiedFormat('fulltext' as CitationFormat)
      setTimeout(() => setCopiedFormat(null), 2000)
    }
  }

  // Scroll to section when clicking TOC item
  const scrollToSection = (sectionNumber: string, provisionType?: string) => {
    if (!contentRef.current) return

    // Normalize the number (remove trailing dots, lowercase)
    const normalizedNumber = sectionNumber.trim().replace(/\.$/, '')
    const lowerType = provisionType?.toLowerCase()

    let element: Element | null = null

    // Strategy 1: Try direct ID lookup based on provision type
    if (lowerType === 'part') {
      element = contentRef.current.querySelector(`[id="part-${normalizedNumber}"]`)
    } else if (lowerType === 'schedule') {
      element = contentRef.current.querySelector(`[id="schedule-${normalizedNumber}"]`)
    } else if (lowerType === 'section' || lowerType === 'regulation') {
      // Try both section and regulation patterns
      element = contentRef.current.querySelector(`[id="section-${normalizedNumber}"]`) ||
                contentRef.current.querySelector(`[id="regulation-${normalizedNumber}"]`)
    }

    // Strategy 2: Fallback to searching by text content within specific element types
    if (!element) {
      const selectors = [
        '.section',
        '.hcontainer.regulation',
        '.part',
        '.schedule'
      ]

      for (const selector of selectors) {
        const elements = contentRef.current.querySelectorAll(selector)
        for (const el of elements) {
          const numElement = el.querySelector('.num')
          if (!numElement) continue

          const numText = numElement.textContent?.trim() || ''

          // Match exact number (handling "1" vs "1." and "Part 1" vs "1")
          const numNormalized = numText.replace(/\.$/, '').replace(/^(Part|PART|Schedule|SCHEDULE)\s+/i, '')

          if (numNormalized === normalizedNumber) {
            element = el
            break
          }
        }
        if (element) break
      }
    }

    // Perform scroll if element found
    if (element) {
      const scrollViewport = contentRef.current.closest('[data-radix-scroll-area-viewport]')

      if (scrollViewport) {
        // Get current scroll position
        const currentScroll = scrollViewport.scrollTop
        // Get viewport position
        const viewportRect = scrollViewport.getBoundingClientRect()
        // Get element position (relative to viewport)
        const elementRect = element.getBoundingClientRect()
        // Calculate how far the element is from the top of the viewport
        const offsetFromViewportTop = elementRect.top - viewportRect.top

        // Scroll to position (current scroll + offset - 20px padding)
        scrollViewport.scrollTo({
          top: currentScroll + offsetFromViewportTop - 20,
          behavior: 'smooth'
        })
      } else {
        // Fallback for non-ScrollArea containers
        element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }

      setActiveSection(normalizedNumber)

      // Scroll TOC to show this item
      const tocItem = document.querySelector(`[data-section-number="${normalizedNumber}"]`)
      if (tocItem) {
        tocItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    } else {
      console.warn(`Could not find element for section ${sectionNumber} (type: ${provisionType})`)
    }
  }

  // Navigate to next relevant section
  const goToNextRelevant = () => {
    if (!relevantSections || relevantSections.length === 0) return
    const nextIndex = (currentRelevantIndex + 1) % relevantSections.length
    setCurrentRelevantIndex(nextIndex)
    const section = relevantSections[nextIndex]
    if (section) {
      scrollToSection(section.number, section.type)
    }
  }

  // Navigate to previous relevant section
  const goToPrevRelevant = () => {
    if (!relevantSections || relevantSections.length === 0) return
    const prevIndex = (currentRelevantIndex - 1 + relevantSections.length) % relevantSections.length
    setCurrentRelevantIndex(prevIndex)
    const section = relevantSections[prevIndex]
    if (section) {
      scrollToSection(section.number, section.type)
    }
  }

  // Extract legislation path from URI (e.g., "ukpga/2024/9" from "http://www.legislation.gov.uk/ukpga/2024/9")
  const legislationPath = legislation.uri
    .replace('https://www.legislation.gov.uk/', '')
    .replace('http://www.legislation.gov.uk/', '')

  // Fetch sections when Sections or Full Text tab is active (needed for TOC)
  const { data: sections } = useQuery<LegislationSection[]>({
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
    enabled: open && activeTab === 'fulltext'
  })

  // Fetch full HTML content when Full Text tab is active
  const { data: htmlContent, isLoading: htmlLoading } = useQuery<string>({
    queryKey: ['legislation-html', legislation.id],
    queryFn: async () => {
      const response = await fetch(`${API_CONFIG.baseUrl}/legislation/proxy/${legislationPath}/data.html`)
      if (!response.ok) throw new Error('Failed to fetch HTML')
      return response.text()
    },
    enabled: open && activeTab === 'fulltext',
    staleTime: 24 * 60 * 60 * 1000, // 24 hours - legislation is immutable
    gcTime: 24 * 60 * 60 * 1000,    // 24 hours - keep in memory
  })

  // Fetch citing cases for cross-references
  const { data: citingCases, isLoading: citingCasesLoading } = useQuery({
    queryKey: ['legislation-citing-cases', legislation.uri],
    queryFn: async () => {
      const response = await fetch(`${API_CONFIG.baseUrl}/caselaw/reference/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference_id: legislation.uri,
          reference_type: 'legislation',
          size: 10
        })
      })
      if (!response.ok) return []
      return response.json()
    },
    enabled: open && activeTab === 'overview'
  })

  // Memoize sanitized HTML to avoid re-sanitization on every render
  const sanitizedHtml = useMemo(() => {
    if (!htmlContent) return ''

    // Fix relative image URLs and sanitize in one operation
    return DOMPurify.sanitize(
      htmlContent.replace(/src="\/images\//g, 'src="https://www.legislation.gov.uk/images/'),
      {
        ADD_TAGS: ['img'],
        ADD_ATTR: ['src', 'alt', 'width', 'height', 'class']
      }
    )
  }, [htmlContent])

  // Track active section with IntersectionObserver
  useEffect(() => {
    if (!contentRef.current || !sections || activeTab !== 'fulltext') return

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the first section that's visible
        const visibleEntry = entries.find(entry => entry.isIntersecting)
        if (visibleEntry) {
          const sectionElement = visibleEntry.target
          const numElement = sectionElement.querySelector('.num')
          if (numElement) {
            const numText = numElement.textContent?.trim() || ''
            // Normalize: remove trailing dots and Part/Schedule prefixes
            const normalized = numText.replace(/\.$/, '').replace(/^(Part|PART|Schedule|SCHEDULE)\s+/i, '')
            if (normalized) {
              setActiveSection(normalized)
            }
          }
        }
      },
      {
        root: contentRef.current.closest('[data-radix-scroll-area-viewport]'),
        rootMargin: '-20% 0px -70% 0px',
        threshold: 0
      }
    )

    // Observe all provision elements (sections, regulations, parts, schedules)
    const sectionElements = contentRef.current.querySelectorAll('.section, .hcontainer.regulation, .part, .schedule')
    sectionElements.forEach(el => observer.observe(el))

    return () => observer.disconnect()
  }, [sections, activeTab, contentRef])

  // Auto-scroll to top relevant section when opening from search with relevant sections
  useEffect(() => {
    // Only auto-switch when dialog first opens (not when user manually changes tabs)
    if (!open || !relevantSections || relevantSections.length === 0) return

    // Switch to fulltext tab automatically on open
    setActiveTab('fulltext')

    // Only scroll if we have HTML content
    if (!htmlContent) return

    // Small delay to ensure DOM is ready
    const timer = setTimeout(() => {
      const topSection = relevantSections[0]
      if (topSection) {
        scrollToSection(topSection.number, topSection.type)
      }
    }, 150)

    return () => clearTimeout(timer)
    // Only run when dialog opens or relevant sections change, NOT when activeTab changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, relevantSections, htmlContent])

  // Reset relevance navigation when dialog closes
  useEffect(() => {
    if (!open) {
      setCurrentRelevantIndex(0)
      setShowRelevanceNav(true)
    }
  }, [open])

  // Apply highlight classes to relevant sections in rendered HTML
  useEffect(() => {
    if (!contentRef.current || !relevantSections || relevantSections.length === 0) return
    if (!htmlContent || activeTab !== 'fulltext') return

    // Remove all existing highlight classes
    const allSections = contentRef.current.querySelectorAll('.section, .hcontainer.regulation, .part, .schedule')
    allSections.forEach(el => {
      el.classList.remove('section-highlighted-primary', 'section-highlighted-secondary', 'section-highlighted-tertiary')
    })

    // Apply highlight classes based on relevance scores
    relevantSections.forEach((relevant, index) => {
      const normalizedNumber = relevant.number.trim().replace(/\.$/, '')
      const lowerType = relevant.type.toLowerCase()

      // Try to find the element
      let element: Element | null = null

      // Direct ID lookup based on type
      if (lowerType === 'part') {
        element = contentRef.current?.querySelector(`[id="part-${normalizedNumber}"]`) || null
      } else if (lowerType === 'schedule') {
        element = contentRef.current?.querySelector(`[id="schedule-${normalizedNumber}"]`) || null
      } else if (lowerType === 'section' || lowerType === 'regulation') {
        element = contentRef.current?.querySelector(`[id="section-${normalizedNumber}"]`) ||
                  contentRef.current?.querySelector(`[id="regulation-${normalizedNumber}"]`) || null
      }

      // Fallback: find by text content
      if (!element) {
        const selectors = ['.section', '.hcontainer.regulation', '.part', '.schedule']
        for (const selector of selectors) {
          const elements = contentRef.current?.querySelectorAll(selector) || []
          for (const el of elements) {
            const numElement = el.querySelector('.num')
            if (!numElement) continue
            const numText = numElement.textContent?.trim() || ''
            const numNormalized = numText.replace(/\.$/, '').replace(/^(Part|PART|Schedule|SCHEDULE)\s+/i, '')
            if (numNormalized === normalizedNumber) {
              element = el
              break
            }
          }
          if (element) break
        }
      }

      // Apply appropriate highlight class
      if (element) {
        if (index === 0) {
          // Top section gets animated highlight
          element.classList.add('section-highlighted-primary')
        } else if (relevant.score >= 0.85) {
          // High scores get secondary highlight
          element.classList.add('section-highlighted-secondary')
        } else {
          // Lower scores get tertiary highlight
          element.classList.add('section-highlighted-tertiary')
        }
      }
    })
  }, [relevantSections, htmlContent, activeTab, contentRef])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-4xl overflow-hidden flex flex-col p-4 gap-0">
        <SheetHeader className="space-y-2 p-0 pb-3">
          <div className="flex items-start gap-2 pr-8">
            <SheetTitle className="text-xl font-bold leading-tight flex-1">
              {legislation.title}
            </SheetTitle>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="shrink-0 opacity-70 hover:opacity-100 transition-opacity">
                  {copiedFormat ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {(['oscola', 'bluebook', 'plain', 'markdown'] as CitationFormat[]).map((format) => (
                  <DropdownMenuItem
                    key={format}
                    onClick={() => handleCopyCitation(format)}
                    className={copiedFormat === format ? "bg-accent" : ""}
                  >
                    {copiedFormat === format && <Check className="h-4 w-4 mr-2" />}
                    {getCitationFormatLabel(format)}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuItem
                  onClick={handleCopyFullText}
                  disabled={!htmlContent}
                  className={copiedFormat === 'fulltext' ? "bg-accent" : ""}
                >
                  {copiedFormat === 'fulltext' && <Check className="h-4 w-4 mr-2" />}
                  Full Text
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <SheetDescription className="flex flex-wrap items-center gap-1.5">
              <LegislationTypeBadge
                type={legislation.type}
                year={legislation.year}
                number={legislation.number}
              />
              <StatusBadge status={legislation.status} />
              <ExtentBadges extent={legislation.extent} />
            </SheetDescription>
            <div className="flex gap-1.5 flex-wrap">
              <SourceGovUkLink
                href={legislation.uri}
                source="legislation"
                variant="button"
              />
            </div>
          </div>
        </SheetHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-2 h-9 items-center rounded-md border bg-background p-1 mb-2">
            <TabsTrigger value="overview" className="text-sm data-[state=active]:bg-muted data-[state=active]:border data-[state=active]:shadow-sm transition-all gap-2 h-full py-0">
              <Eye className="h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="fulltext" className="text-sm data-[state=active]:bg-muted data-[state=active]:border data-[state=active]:shadow-sm transition-all gap-2 h-full py-0">
              <ScrollText className="h-4 w-4" />
              Full Text
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="flex-1 overflow-hidden mt-0">
            <ScrollArea className="h-full pr-4">
              <div className="space-y-3">
                {/* Description */}
                {legislation.description && (
                  <Card className="gap-2">
                    <CardHeader>
                      <CardTitle className="text-sm font-medium">Description</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {legislation.description}
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Metadata */}
                <Card className="gap-2">
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">Metadata</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Type</span>
                      <span className="font-medium">{legislation.type.toUpperCase()}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Year</span>
                      <span className="font-medium">{legislation.year}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Number</span>
                      <span className="font-medium">{legislation.number}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Status</span>
                      <div><StatusBadge status={legislation.status} /></div>
                    </div>
                    {legislation.extent && legislation.extent.filter(e => e.trim()).length > 0 && (
                      <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                        <span className="text-muted-foreground">Extent</span>
                        <div><ExtentBadges extent={legislation.extent} /></div>
                      </div>
                    )}
                    {legislation.enactment_date && (
                      <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                        <span className="text-muted-foreground">Enacted</span>
                        <span className="font-medium">
                          {new Date(legislation.enactment_date).toLocaleDateString('en-GB', {
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric'
                          })}
                        </span>
                      </div>
                    )}
                    {legislation.publisher && (
                      <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
                        <span className="text-muted-foreground">Publisher</span>
                        <span className="font-medium">{legislation.publisher}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Cross-References */}
                <Card className="gap-2">
                  <CardHeader>
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Link2 className="h-4 w-4" />
                      Cited By
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {citingCasesLoading ? (
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-3/4" />
                      </div>
                    ) : citingCases && citingCases.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-sm text-muted-foreground mb-3">
                          Referenced by {citingCases.length} case{citingCases.length > 1 ? 's' : ''}
                          {citingCases.length === 10 && ' (showing first 10)'}
                        </p>
                        <div className="space-y-2">
                          {citingCases.slice(0, 5).map((caselaw: CitingCase) => (
                            <a
                              key={caselaw.id}
                              href={caselaw.id}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block p-2 rounded-md hover:bg-accent transition-colors text-sm"
                            >
                              <div className="font-medium line-clamp-1">{caselaw.name}</div>
                              <div className="text-xs text-muted-foreground">
                                [{caselaw.year}] {caselaw.court.toUpperCase()} {caselaw.number}
                              </div>
                            </a>
                          ))}
                        </div>
                        {citingCases.length > 5 && (
                          <p className="text-xs text-muted-foreground mt-2">
                            + {citingCases.length - 5} more cases
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No citing cases found in database
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* External Link */}
                <SourceGovUkLink
                  href={legislation.uri}
                  source="legislation"
                  variant="primary"
                />
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="fulltext" className="flex-1 overflow-hidden mt-0 flex flex-col">
            {/* Relevance Navigator */}
            {relevantSections && relevantSections.length > 0 && showRelevanceNav && (
              <div className="flex items-center gap-2 px-2.5 py-1.5 mb-2 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md">
                <Target className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                <div className="flex-1 text-sm text-amber-900 dark:text-amber-100">
                  <span className="font-medium">{relevantSections.length} relevant section{relevantSections.length !== 1 ? 's' : ''} found</span>
                  <span className="text-amber-700 dark:text-amber-300 ml-1">• Viewing {currentRelevantIndex + 1} of {relevantSections.length}</span>
                </div>
                <div className="flex gap-0.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={goToPrevRelevant}
                    className="h-6 w-6 p-0 text-amber-700 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100"
                    disabled={relevantSections.length <= 1}
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={goToNextRelevant}
                    className="h-6 w-6 p-0 text-amber-700 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100"
                    disabled={relevantSections.length <= 1}
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowRelevanceNav(false)}
                    className="h-6 w-6 p-0 text-amber-700 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}

            {/* Content with TOC */}
            <div className="flex-1 overflow-hidden flex gap-5 relative">
              {/* Floating TOC Toggle Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowToc(!showToc)}
                className={`absolute top-2 z-10 h-8 w-8 p-0 backdrop-blur-sm bg-background/80 hover:bg-background shadow-md transition-all duration-300 ${
                  showToc && sections && sections.length > 0 ? 'left-[242px]' : 'left-2'
                }`}
                title={showToc ? 'Hide Contents' : 'Show Contents'}
              >
                <List className="h-4 w-4" />
              </Button>

              {/* Floating Search Button/Panel */}
              <div className="absolute top-2 right-2 z-10">
                {searchExpanded ? (
                  <div className="flex items-center gap-2 backdrop-blur-sm bg-background/95 rounded-md shadow-lg border p-1 animate-in slide-in-from-right-5 duration-200">
                    <TextSearch containerRef={contentRef} placeholder="Search..." />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSearchExpanded(false)}
                      className="h-8 w-8 p-0 shrink-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSearchExpanded(true)}
                    className="h-8 w-8 p-0 backdrop-blur-sm bg-background/80 hover:bg-background shadow-md"
                    title="Search within text"
                  >
                    <Search className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {/* Table of Contents */}
              <div
                className={`shrink-0 border-r pr-4 transition-all duration-300 ease-in-out overflow-hidden ${
                  showToc && sections && sections.length > 0 ? 'w-64 opacity-100' : 'w-0 opacity-0 pr-0 border-r-0'
                }`}
              >
                {sections && sections.length > 0 && (
                  <ScrollArea className="h-full">
                    <div className="space-y-1">
                      <div className="text-sm font-semibold mb-2 sticky top-0 bg-background py-2">
                        Contents
                      </div>
                      {sections.map((section) => {
                        const isSection = section.provision_type.toLowerCase() === 'section'
                        const isPart = section.provision_type.toLowerCase() === 'part'
                        const isSchedule = section.provision_type.toLowerCase() === 'schedule'
                        const sectionNumber = String(section.number)
                        const normalizedNumber = sectionNumber.trim().replace(/\.$/, '')
                        const isActive = activeSection === normalizedNumber

                        // Check if this section is in the relevant sections
                        const relevance = relevantSections?.find(r => r.number === normalizedNumber)

                        return (
                          <button
                            key={section.id}
                            data-section-number={normalizedNumber}
                            onClick={() => scrollToSection(sectionNumber, section.provision_type)}
                            className={`
                              w-full text-left text-xs py-1.5 px-2 rounded transition-colors
                              ${isActive ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'}
                              ${isPart ? 'font-semibold mt-3' : ''}
                              ${isSchedule ? 'font-semibold mt-3 italic' : ''}
                              ${isSection ? 'pl-4' : ''}
                              ${relevance ? 'border-l-2 border-amber-500' : ''}
                            `}
                          >
                            <div className="flex items-start gap-2">
                              <span className={`shrink-0 min-w-[3ch] ${isActive ? 'text-accent-foreground' : 'text-muted-foreground'}`}>
                                {section.number}
                              </span>
                              <span className="line-clamp-2 flex-1">{section.title}</span>
                              {relevance && (
                                <div className="flex items-center gap-1 shrink-0 ml-auto">
                                  {relevance.score >= 0.85 ? (
                                    <>
                                      <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                                      <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                                    </>
                                  ) : (
                                    <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                                  )}
                                  <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                                    {Math.round(relevance.score * 100)}%
                                  </span>
                                </div>
                              )}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </ScrollArea>
                )}
              </div>

              {/* Main content */}
              <ScrollArea className={`flex-1 transition-all duration-300 ${showToc && sections && sections.length > 0 ? '' : 'pl-12'}`}>
                {htmlLoading ? (
                  <div className="space-y-4 p-4">
                    <Skeleton className="h-8 w-3/4" />
                    <Skeleton className="h-40 w-full" />
                    <Skeleton className="h-40 w-full" />
                    <Skeleton className="h-40 w-full" />
                  </div>
                ) : htmlContent ? (
                  <div
                    ref={contentRef}
                    className="legislation-content pr-4"
                    dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
                  />
                ) : (
                  <Alert className="m-4">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Failed to load legislation content. Please try again or{" "}
                      <SourceGovUkLink
                        href={legislation.uri}
                        source="legislation"
                        variant="inline"
                      >
                        view on <span className="font-semibold">legislation</span>.gov.uk
                      </SourceGovUkLink>
                    </AlertDescription>
                  </Alert>
                )}
              </ScrollArea>
            </div>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}

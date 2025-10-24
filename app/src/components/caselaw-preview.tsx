"use client"

import { useState } from "react"
import {
  formatCaselawCitation,
  copyToClipboard,
  getCitationFormatLabel,
  type CitationFormat,
} from "@/lib/citations"
import { SourceGovUkLink } from "@/components/source-gov-uk-link"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ExternalLink, Copy, Check, Link2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { API_CONFIG } from "@/lib/config"
import { CourtBadge, CitationBadge } from "./badges"
import { AddToProjectButton } from "./add-to-project-button"

interface CaselawPreviewProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  caselaw: {
    id: string
    court: string
    division?: string
    year: number
    number: number
    name: string
    cite_as?: string
    date: string
    header: string
  }
}

interface CitingCase {
  id: string
  name: string
  year: number
  court: string
  number: number
}

export function CaselawPreview({ open, onOpenChange, caselaw }: CaselawPreviewProps) {
  const [activeTab, setActiveTab] = useState("overview")
  const [copiedFormat, setCopiedFormat] = useState<CitationFormat | null>(null)

  // Handle citation copy
  const handleCopyCitation = async (format: CitationFormat) => {
    const citation = formatCaselawCitation(
      {
        name: caselaw.name,
        court: caselaw.court,
        year: caselaw.year,
        number: caselaw.number,
        cite_as: caselaw.cite_as,
        date: caselaw.date,
        id: caselaw.id,
      },
      format
    )

    const success = await copyToClipboard(citation)
    if (success) {
      setCopiedFormat(format)
      setTimeout(() => setCopiedFormat(null), 2000)
    }
  }

  // Fetch cases that cite this case
  const { data: citingCases, isLoading: citingCasesLoading } = useQuery({
    queryKey: ['caselaw-citing-cases', caselaw.id],
    queryFn: async () => {
      const response = await fetch(`${API_CONFIG.baseUrl}/caselaw/reference/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference_id: caselaw.id,
          reference_type: 'caselaw',
          size: 10
        })
      })
      if (!response.ok) return []
      return response.json()
    },
    enabled: open && activeTab === 'overview'
  })

  // Fetch full caselaw details to get legislation references
  const { data: caselawDetails, isLoading: caselawDetailsLoading } = useQuery({
    queryKey: ['caselaw-details', caselaw.id],
    queryFn: async () => {
      const response = await fetch(`${API_CONFIG.baseUrl}/caselaw/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: caselaw.name,
          court: [caselaw.court],
          year_from: caselaw.year,
          year_to: caselaw.year,
          size: 1
        })
      })
      if (!response.ok) return null
      const data = await response.json()
      return data.results?.[0] || null
    },
    enabled: open && activeTab === 'overview'
  })

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-4xl overflow-hidden flex flex-col p-6">
        <SheetHeader>
          <SheetTitle className="text-lg leading-tight pr-8">
            {caselaw.name}
          </SheetTitle>
          <SheetDescription className="flex flex-wrap gap-2 mt-2">
            <CourtBadge court={caselaw.court} division={caselaw.division} />
            {caselaw.cite_as && <CitationBadge citation={caselaw.cite_as} />}
            <CitationBadge
              citation={`[${caselaw.year}] ${caselaw.court.toUpperCase()} ${caselaw.number}`}
            />
          </SheetDescription>
          <div className="mt-3 flex gap-2">
            <AddToProjectButton
              document={{
                documentId: caselaw.id,
                type: 'caselaw',
                addedBy: 'user',
                notes: '',
                tags: [],
                metadata: {
                  title: caselaw.name,
                  year: caselaw.year,
                  court: caselaw.court,
                  citation: caselaw.cite_as,
                }
              }}
              variant="outline"
              size="sm"
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  {copiedFormat ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                  Copy Citation
                </Button>
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
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </SheetHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-1 mb-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="flex-1 overflow-hidden mt-0">
            <ScrollArea className="h-full pr-4">
              <div className="space-y-4">
                {/* Summary */}
                {caselaw.header && (
                  <Card className="gap-2">
                    <CardHeader>
                      <CardTitle className="text-sm font-medium">Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {caselaw.header}
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Case Details */}
                <Card className="gap-2">
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">Case Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Court</span>
                      <div><CourtBadge court={caselaw.court} division={caselaw.division} /></div>
                    </div>
                    <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Neutral Citation</span>
                      <div>
                        <CitationBadge
                          citation={`[${caselaw.year}] ${caselaw.court.toUpperCase()} ${caselaw.number}`}
                        />
                      </div>
                    </div>
                    {caselaw.cite_as && (
                      <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                        <span className="text-muted-foreground">Cite As</span>
                        <div><CitationBadge citation={caselaw.cite_as} /></div>
                      </div>
                    )}
                    <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                      <span className="text-muted-foreground">Judgment Date</span>
                      <span className="font-medium">
                        {new Date(caselaw.date).toLocaleDateString('en-GB', {
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric'
                        })}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {/* Legislation References */}
                {!caselawDetailsLoading && caselawDetails?.legislation_references && caselawDetails.legislation_references.length > 0 && (
                  <Card className="gap-2">
                    <CardHeader>
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Link2 className="h-4 w-4" />
                        References Legislation
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-3">
                        This case references {caselawDetails.legislation_references.length} piece{caselawDetails.legislation_references.length > 1 ? 's' : ''} of legislation
                      </p>
                      <div className="space-y-2">
                        {caselawDetails.legislation_references.slice(0, 5).map((ref: string, idx: number) => (
                          <a
                            key={idx}
                            href={ref}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block p-2 rounded-md hover:bg-accent transition-colors text-sm"
                          >
                            <div className="font-medium line-clamp-1">
                              {ref.split('/').pop()?.toUpperCase()}
                            </div>
                            <div className="text-xs text-muted-foreground line-clamp-1">
                              {ref}
                            </div>
                          </a>
                        ))}
                      </div>
                      {caselawDetails.legislation_references.length > 5 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          + {caselawDetails.legislation_references.length - 5} more references
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Citing Cases */}
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
                          Cited by {citingCases.length} case{citingCases.length > 1 ? 's' : ''}
                          {citingCases.length === 10 && ' (showing first 10)'}
                        </p>
                        <div className="space-y-2">
                          {citingCases.slice(0, 5).map((citingCase: CitingCase) => (
                            <a
                              key={citingCase.id}
                              href={citingCase.id}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block p-2 rounded-md hover:bg-accent transition-colors text-sm"
                            >
                              <div className="font-medium line-clamp-1">{citingCase.name}</div>
                              <div className="text-xs text-muted-foreground">
                                [{citingCase.year}] {citingCase.court.toUpperCase()} {citingCase.number}
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
                  href={caselaw.id}
                  source="caselaw"
                  variant="primary"
                />
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}

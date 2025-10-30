"use client"

import { useRouter } from "next/navigation"
import { AppSidebar } from "@/components/app-sidebar"
import { SourceGovUkLink } from "@/components/source-gov-uk-link"
import { MultiSelect } from "@/components/ui/multi-select"
import { getApiErrorMessage } from "@/lib/errors"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Search, Calendar, Building2, Gavel, Scale, ExternalLink, AlertCircle, ArrowUpDown, Filter, X } from "lucide-react"
import { ResultSkeletonList } from "@/components/result-skeleton"
import { EmptyState } from "@/components/empty-state"
import { CourtBadge, CitationBadge } from "@/components/badges"
import { CaselawPreview } from "@/components/caselaw-preview"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { SearchHistoryDropdown } from "@/components/search-history-dropdown"
import { SearchPagination } from "@/components/search-pagination"
import { useDocumentSearch } from "@/hooks/use-document-search"
import { YearRangePicker } from "@/components/ui/year-range-picker"

interface CaselawResult {
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

const sortOptions = [
  { value: 'relevance' as const, label: 'Relevance' },
  { value: 'date-desc' as const, label: 'Newest First' },
  { value: 'date-asc' as const, label: 'Oldest First' },
  { value: 'title-asc' as const, label: 'Title (A-Z)' },
  { value: 'title-desc' as const, label: 'Title (Z-A)' },
]

const courtTypeOptions = [
  {
    heading: "Senior Courts",
    options: [
      { value: "uksc", label: "UK Supreme Court", shortLabel: "UKSC", icon: Scale },
      { value: "ukpc", label: "Privy Council", shortLabel: "UKPC", icon: Scale },
      { value: "ewca", label: "Court of Appeal", shortLabel: "EWCA", icon: Gavel },
    ]
  },
  {
    heading: "High Court & Crown",
    options: [
      { value: "ewhc", label: "High Court (England and Wales)", shortLabel: "EWHC", icon: Building2 },
      { value: "ewcr", label: "Crown Court", shortLabel: "EWCR", icon: Gavel },
    ]
  },
  {
    heading: "Tribunals",
    options: [
      { value: "ukut", label: "Upper Tribunal", shortLabel: "UKUT", icon: Building2 },
      { value: "ukftt", label: "First-tier Tribunal", shortLabel: "UKFTT", icon: Building2 },
    ]
  }
]

export default function CaselawPage() {
  const router = useRouter()

  const search = useDocumentSearch<CaselawResult, string[]>({
    type: 'caselaw',
    endpoint: '/caselaw/search',
    defaultFilters: ["uksc", "ukpc", "ewca"],
    defaultYearTo: new Date().getFullYear().toString(),

    parseFiltersFromUrl: (params) => {
      return params.get('courts')?.split(',') || ["uksc", "ukpc", "ewca"]
    },

    buildFilterParamsForUrl: (filters): Record<string, string> => {
      return filters.length > 0 ? { courts: filters.join(',') } : {}
    },

    buildSearchHistoryFilters: (filters, yearFrom, yearTo) => ({
      courts: filters.length > 0 ? filters : undefined,
      yearFrom: yearFrom ? parseInt(yearFrom) : undefined,
      yearTo: yearTo ? parseInt(yearTo) : undefined,
    }),

    buildApiRequestBody: ({ query, filters, yearFrom, yearTo, currentPage, pageSize }) => ({
      query,
      year_from: yearFrom ? parseInt(yearFrom) : undefined,
      year_to: yearTo ? parseInt(yearTo) : undefined,
      court: filters.length > 0 ? filters : undefined,
      offset: (currentPage - 1) * pageSize,
      size: pageSize,
    }),

    getResults: (response) => (response as { results?: CaselawResult[] })?.results || [],
    getTotal: (response) => (response as { total?: number })?.total || 0,

    sortResults: (results, sortBy) => {
      return results.sort((a, b) => {
        switch (sortBy) {
          case 'date-desc':
            return new Date(b.date).getTime() - new Date(a.date).getTime()
          case 'date-asc':
            return new Date(a.date).getTime() - new Date(b.date).getTime()
          case 'title-asc':
            return a.name.localeCompare(b.name)
          case 'title-desc':
            return b.name.localeCompare(a.name)
          case 'relevance':
          default:
            return 0
        }
      })
    },

    filterResults: (results, filterText) => {
      if (!filterText) return results
      const searchLower = filterText.toLowerCase()
      return results.filter(result =>
        result.name.toLowerCase().includes(searchLower) ||
        result.header?.toLowerCase().includes(searchLower) ||
        result.court.toLowerCase().includes(searchLower) ||
        result.cite_as?.toLowerCase().includes(searchLower) ||
        result.year.toString().includes(searchLower)
      )
    },
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-[orientation=vertical]:h-4"
            />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="/">Home</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Caselaw Search</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          {/* Search Form */}
          <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="query">Search Query</Label>
                  <span className="text-xs text-muted-foreground">
                    <kbd className="px-1.5 py-0.5 text-xs font-semibold bg-muted rounded">⌘K</kbd> to focus
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    ref={search.searchInputRef}
                    id="query"
                    placeholder="e.g., breach of contract, negligence, judicial review"
                    value={search.query}
                    onChange={(e) => search.setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && search.handleSearch()}
                    className="flex-1"
                  />
                  <SearchHistoryDropdown
                    type="caselaw"
                    onSelectSearch={search.handleSelectFromHistory}
                    variant="compact"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-4">
                <div className="space-y-2">
                  <Label>Court Types</Label>
                  <MultiSelect
                    options={courtTypeOptions}
                    onValueChange={search.setFilters}
                    defaultValue={search.filters}
                    placeholder="Select courts"
                    maxCount={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Year Range</Label>
                  <YearRangePicker
                    value={{
                      from: search.yearFrom ? parseInt(search.yearFrom) : undefined,
                      to: search.yearTo ? parseInt(search.yearTo) : undefined,
                    }}
                    onChange={(range) => {
                      search.setYearFrom(range.from?.toString() || "")
                      search.setYearTo(range.to?.toString() || "")
                    }}
                    minYear={2001}
                    maxYear={new Date().getFullYear()}
                    placeholder="Select year range"
                  />
                </div>
              </div>

              <Button
                onClick={search.handleSearch}
                disabled={search.isLoading || !search.query}
                className="w-full"
              >
                <Search className="mr-2 h-4 w-4" />
                {search.isLoading ? "Searching..." : "Search"}
              </Button>

              {search.error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {getApiErrorMessage(search.error)}
                  </AlertDescription>
                </Alert>
              )}
          </div>

          {/* Loading State */}
          {search.isLoading && <ResultSkeletonList count={5} />}

          {/* Empty State */}
          {search.showEmptyState && (
            <EmptyState
              query={search.query}
              onClear={search.clearFilters}
              onSuggestionClick={(suggestion) => {
                const params = new URLSearchParams()
                params.set('q', suggestion)
                if (search.yearFrom) params.set('year_from', search.yearFrom)
                if (search.yearTo) params.set('year_to', search.yearTo)
                if (search.filters.length > 0) params.set('courts', search.filters.join(','))
                params.set('page', '1')
                router.push(`/caselaw?${params.toString()}`)
              }}
              type="caselaw"
            />
          )}

          {/* Results */}
          {search.hasResults && !search.isLoading && (
            <>
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold">
                  {search.filterText ? (
                    <>Showing {search.results.length} of {search.total} results</>
                  ) : (
                    <>Found {search.total} results {search.totalPages > 1 && `(page ${search.currentPage} of ${search.totalPages})`}</>
                  )}
                </h2>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Filter results..."
                      value={search.filterText}
                      onChange={(e) => search.setFilterText(e.target.value)}
                      className="pl-9 pr-9 w-64"
                    />
                    {search.filterText && (
                      <button
                        onClick={() => search.setFilterText("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-2">
                      <ArrowUpDown className="h-4 w-4" />
                      <span className="hidden sm:inline">Sort by:</span>
                      {sortOptions.find(opt => opt.value === search.sortBy)?.label}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {sortOptions.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => search.setSortBy(option.value)}
                        className={search.sortBy === option.value ? "bg-accent" : ""}
                      >
                        {option.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                </div>
              </div>

              <div className="space-y-4">
                {search.results.map((result: CaselawResult) => (
                  <Card
                    key={result.id}
                    className="hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => search.openPreview(result)}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <CardTitle className="text-base leading-tight flex-1">
                          {result.name}
                        </CardTitle>
                        <div className="flex items-center gap-1.5 text-sm text-muted-foreground shrink-0">
                          <Calendar className="h-3.5 w-3.5" />
                          <span className="font-medium">
                            {new Date(result.date).toLocaleDateString('en-GB', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric'
                            })}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <CourtBadge court={result.court} division={result.division} />
                        {result.cite_as && <CitationBadge citation={result.cite_as} />}
                        <CitationBadge
                          citation={`[${result.year}] ${result.court.toUpperCase()} ${result.number}`}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <p className="text-sm text-muted-foreground mb-4 line-clamp-3">
                        {result.header || "No summary available"}
                      </p>
                      <SourceGovUkLink href={result.id} source="caselaw" variant="button" />
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Pagination */}
              <SearchPagination
                currentPage={search.currentPage}
                totalPages={search.totalPages}
                onPageChange={search.handlePageChange}
              />
            </>
          )}
        </div>

        {/* Preview Sheet */}
        {search.previewItem && (
          <CaselawPreview
            open={search.previewOpen}
            onOpenChange={search.setPreviewOpen}
            caselaw={search.previewItem}
          />
        )}
      </SidebarInset>
    </SidebarProvider>
  )
}

"use client"

import { useState } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Status, StatusIndicator, StatusLabel } from "@/components/ui/status"
import {
  AlertCircle,
  ArrowRight,
  Brain,
  Calendar,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Eye,
  FileText,
  History,
  Landmark,
  Loader2,
  Scale,
  ScrollText,
  Search,
  Server,
  Sparkles,
  Trash2,
  X,
} from "lucide-react"
import {
  StatusBadge,
  ExtentBadges,
  LegislationTypeBadge,
  CourtBadge,
  CitationBadge,
} from "@/components/badges"
import { SourceGovUkLink } from "@/components/source-gov-uk-link"

export default function DesignSystemPage() {
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null)
  const [expandedReasoning, setExpandedReasoning] = useState(false)
  const [expandedTool, setExpandedTool] = useState(false)

  const handleCopy = (format: string) => {
    setCopiedFormat(format)
    setTimeout(() => setCopiedFormat(null), 2000)
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="/">Home</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Design System</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </header>

        <ScrollArea className="h-[calc(100vh-4rem)]">
          <div className="flex flex-1 flex-col gap-12 p-6 max-w-4xl">
            {/* Hero */}
            <div className="space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Design System</h1>
              <p className="text-lg text-muted-foreground leading-relaxed">
                Lex helps legal professionals search and research UK legislation and caselaw.
                This page showcases the components that make up the interface, following the
                journey from search to discovery.
              </p>
            </div>

            {/* Chapter 1: The Search */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Chapter 1</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">The Search</h2>
                <p className="text-muted-foreground mt-2">
                  Every journey begins with a question. The search interface combines a query input
                  with type filters and smart suggestions.
                </p>
              </div>

              {/* Search Input - matching actual implementation */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Search Input</CardTitle>
                  <CardDescription>
                    Label with keyboard shortcut, input field, and history dropdown
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="query">Search Query</Label>
                      <span className="text-xs text-muted-foreground">
                        <kbd className="px-1.5 py-0.5 text-xs font-semibold bg-muted rounded">⌘K</kbd> to focus
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        id="query"
                        placeholder="e.g., data protection, artificial intelligence"
                        className="flex-1"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0 bg-sky-50 hover:bg-sky-100 border-sky-100 hover:border-sky-200"
                      >
                        <History className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Filter Badges - matching MultiSelect implementation */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Type Filters</CardTitle>
                  <CardDescription>
                    Grouped options with icons and removable badges
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label>Legislation Types</Label>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary" className="py-1.5 px-3 gap-2">
                        <Landmark className="h-4 w-4" />
                        <span>UKPGA</span>
                        <X className="h-3 w-3 cursor-pointer hover:bg-white/20 rounded-sm" />
                      </Badge>
                      <Badge variant="secondary" className="py-1.5 px-3 gap-2">
                        <ScrollText className="h-4 w-4" />
                        <span>UKSI</span>
                        <X className="h-3 w-3 cursor-pointer hover:bg-white/20 rounded-sm" />
                      </Badge>
                      <Button variant="outline" size="sm" className="h-8">
                        + Add filter
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Search Suggestions - matching actual color scheme */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Search Suggestions</CardTitle>
                  <CardDescription>
                    Recent searches (sky blue) and AI suggestions (fuchsia)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="bg-card border border-border/40 rounded-lg p-4 space-y-4">
                    {/* Recent searches */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        Recent searches
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="justify-start h-auto p-3 text-sm font-normal shadow-sm hover:shadow-md transition-all duration-200 bg-sky-50 hover:bg-sky-100 border-sky-100 hover:border-sky-200"
                        >
                          data protection gdpr
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="justify-start h-auto p-3 text-sm font-normal shadow-sm hover:shadow-md transition-all duration-200 bg-sky-50 hover:bg-sky-100 border-sky-100 hover:border-sky-200"
                        >
                          employment rights act
                        </Button>
                      </div>
                    </div>

                    <div className="border-t border-border/20" />

                    {/* AI suggestions */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-muted-foreground" />
                        Based on your history
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="justify-start h-auto p-3 text-sm font-normal shadow-sm hover:shadow-md transition-all duration-200 bg-fuchsia-50 hover:bg-fuchsia-100 border-fuchsia-100 hover:border-fuchsia-200"
                        >
                          consumer protection regulations
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="justify-start h-auto p-3 text-sm font-normal shadow-sm hover:shadow-md transition-all duration-200 bg-fuchsia-50 hover:bg-fuchsia-100 border-fuchsia-100 hover:border-fuchsia-200"
                        >
                          freedom of information
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Chapter 2: The Results */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Chapter 2</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">The Results</h2>
                <p className="text-muted-foreground mt-2">
                  Search results display rich metadata with badges and direct links to
                  authoritative sources.
                </p>
              </div>

              {/* Legislation Result - exact structure from page.tsx */}
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <CardTitle className="text-base leading-tight flex-1">
                      Data Protection Act 2018
                    </CardTitle>
                    <div className="flex items-center gap-1.5 text-sm text-muted-foreground shrink-0">
                      <Calendar className="h-3.5 w-3.5" />
                      <span className="font-medium">2018</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <LegislationTypeBadge type="ukpga" year={2018} number={12} />
                    <StatusBadge status="revised" />
                    <ExtentBadges extent={["E+W+S+NI"]} />
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                    An Act to make provision for the regulation of the processing of information relating to individuals...
                  </p>
                  <SourceGovUkLink
                    href="https://www.legislation.gov.uk/ukpga/2018/12"
                    source="legislation"
                    variant="button"
                  />
                </CardContent>
              </Card>

              {/* Caselaw Result - exact structure from page.tsx */}
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <CardTitle className="text-base leading-tight flex-1">
                      R (Privacy International) v Investigatory Powers Tribunal
                    </CardTitle>
                    <div className="flex items-center gap-1.5 text-sm text-muted-foreground shrink-0">
                      <Calendar className="h-3.5 w-3.5" />
                      <span className="font-medium">15 May 2019</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CourtBadge court="UKSC" />
                    <CitationBadge citation="[2019] UKSC 22" />
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground mb-4 line-clamp-3">
                    Supreme Court judgment on the scope of judicial review and ouster clauses in national security contexts...
                  </p>
                  <SourceGovUkLink
                    href="https://caselaw.nationalarchives.gov.uk/uksc/2019/22"
                    source="caselaw"
                    variant="button"
                  />
                </CardContent>
              </Card>

              {/* Loading Skeleton - matching animated-result-skeleton.tsx */}
              <Card className="hover:shadow-md transition-all duration-300">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <Skeleton className="h-5 w-3/4 flex-1" />
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Skeleton className="h-3.5 w-3.5 rounded" />
                      <Skeleton className="h-4 w-8" />
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Skeleton className="h-8 w-24" />
                    <Skeleton className="h-8 w-20" />
                    <Skeleton className="h-8 w-16" />
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-1 mb-4">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-2/3" />
                  </div>
                  <Skeleton className="h-9 w-40" />
                </CardContent>
              </Card>
            </section>

            {/* Chapter 3: The Document */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Chapter 3</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">The Document</h2>
                <p className="text-muted-foreground mt-2">
                  Document previews open in a sheet panel with tabs, citation copying, and
                  links to the official source.
                </p>
              </div>

              {/* Document Preview Sheet */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Document Preview</CardTitle>
                  <CardDescription>
                    Sheet panel with Overview and Full Text tabs
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Sheet>
                    <SheetTrigger asChild>
                      <Button>Open Document Preview</Button>
                    </SheetTrigger>
                    <SheetContent className="w-full sm:max-w-4xl overflow-hidden flex flex-col p-4 gap-0">
                      <SheetHeader className="space-y-2 p-0 pb-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1 flex-1">
                            <SheetTitle className="text-lg leading-tight">
                              Data Protection Act 2018
                            </SheetTitle>
                            <SheetDescription>UK Public General Act</SheetDescription>
                          </div>
                          {/* Copy citation dropdown */}
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
                              {['OSCOLA', 'Bluebook', 'Plain Text', 'Markdown'].map((format) => (
                                <DropdownMenuItem
                                  key={format}
                                  onClick={() => handleCopy(format)}
                                  className={copiedFormat === format ? "bg-accent" : ""}
                                >
                                  {copiedFormat === format && <Check className="h-4 w-4 mr-2" />}
                                  {format}
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                        <div className="flex gap-1.5 flex-wrap">
                          <SourceGovUkLink
                            href="https://www.legislation.gov.uk/ukpga/2018/12"
                            source="legislation"
                            variant="button"
                          />
                        </div>
                      </SheetHeader>

                      <Tabs defaultValue="overview" className="flex-1 flex flex-col overflow-hidden">
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
                              <Card>
                                <CardHeader className="pb-2">
                                  <CardTitle className="text-sm">Metadata</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <LegislationTypeBadge type="ukpga" year={2018} number={12} />
                                    <StatusBadge status="revised" />
                                    <ExtentBadges extent={["E+W+S+NI"]} />
                                  </div>
                                </CardContent>
                              </Card>
                              <Card>
                                <CardHeader className="pb-2">
                                  <CardTitle className="text-sm">Description</CardTitle>
                                </CardHeader>
                                <CardContent>
                                  <p className="text-sm text-muted-foreground">
                                    An Act to make provision for the regulation of the processing of
                                    information relating to individuals; to make provision in connection
                                    with the Information Commissioner&apos;s functions.
                                  </p>
                                </CardContent>
                              </Card>
                            </div>
                          </ScrollArea>
                        </TabsContent>
                        <TabsContent value="fulltext" className="flex-1 overflow-hidden mt-0">
                          <ScrollArea className="h-full pr-4">
                            <p className="text-sm text-muted-foreground">
                              Full text content would appear here...
                            </p>
                          </ScrollArea>
                        </TabsContent>
                      </Tabs>
                    </SheetContent>
                  </Sheet>
                </CardContent>
              </Card>

              {/* Source Link Variants */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Source Links</CardTitle>
                  <CardDescription>
                    Three variants: button, inline, and primary
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Button variant (default)</p>
                    <div className="flex flex-wrap gap-3">
                      <SourceGovUkLink
                        href="https://www.legislation.gov.uk/ukpga/2018/12"
                        source="legislation"
                        variant="button"
                      />
                      <SourceGovUkLink
                        href="https://caselaw.nationalarchives.gov.uk/uksc/2019/22"
                        source="caselaw"
                        variant="button"
                      />
                    </div>
                  </div>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Inline variant (for text)</p>
                    <p className="text-sm">
                      View the full text on{" "}
                      <SourceGovUkLink
                        href="https://www.legislation.gov.uk/ukpga/2018/12"
                        source="legislation"
                        variant="inline"
                      />
                    </p>
                  </div>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Primary variant (full-width CTA)</p>
                    <div className="max-w-xs">
                      <SourceGovUkLink
                        href="https://www.legislation.gov.uk/ukpga/2018/12"
                        source="legislation"
                        variant="primary"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Chapter 4: Deep Research */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Chapter 4</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">Deep Research</h2>
                <p className="text-muted-foreground mt-2">
                  The AI research assistant searches across legislation and caselaw,
                  revealing its reasoning process as it works.
                </p>
              </div>

              {/* Research Input - matching actual rounded-[2rem] style */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Research Input</CardTitle>
                  <CardDescription>
                    Rounded container with settings toggle and submit button
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="relative rounded-[2rem] border border-input/50 bg-background shadow-lg overflow-hidden">
                    <textarea
                      placeholder="Ask me anything about UK legislation or caselaw..."
                      className="w-full min-h-[100px] px-6 pt-5 pb-12 text-base bg-transparent resize-none focus-visible:outline-none"
                      defaultValue=""
                    />
                    <div className="absolute bottom-3 right-3">
                      <Button
                        size="icon"
                        className="rounded-full h-10 w-10"
                      >
                        <ArrowRight className="h-6 w-6" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Settings Panel */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Research Settings</CardTitle>
                  <CardDescription>
                    Toggle data sources and configure research depth
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="pt-2 px-5 pb-5 rounded-[2rem] bg-muted/30 border border-input/50">
                    <div className="space-y-4">
                      <div className="space-y-2.5">
                        <p className="text-sm text-muted-foreground font-medium">Search within</p>
                        <div className="flex gap-2">
                          <Button variant="default" size="sm" className="flex items-center gap-2">
                            <FileText className="h-3.5 w-3.5" />
                            Legislation
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="outline" size="sm" className="flex items-center gap-2">
                            <Scale className="h-3.5 w-3.5" />
                            Caselaw
                          </Button>
                        </div>
                      </div>
                      <div className="space-y-2.5">
                        <div className="flex items-center justify-between">
                          <p className="text-sm text-muted-foreground font-medium">Research depth</p>
                          <span className="text-xs text-muted-foreground">Max 25 steps</span>
                        </div>
                        <input
                          type="range"
                          min={3}
                          max={50}
                          defaultValue={25}
                          className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                        <p className="text-xs text-muted-foreground">Balanced (recommended)</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* AI Response Components */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">AI Response Components</CardTitle>
                  <CardDescription>
                    Reasoning traces and tool calls with expandable results
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Reasoning Trace - matching actual implementation */}
                  <div>
                    <button
                      onClick={() => setExpandedReasoning(!expandedReasoning)}
                      className="group flex items-center gap-2 text-sm text-muted-foreground/70 hover:text-muted-foreground transition-colors w-full text-left"
                    >
                      <Brain className="h-3.5 w-3.5 flex-shrink-0" />
                      <span className="italic flex-1 text-muted-foreground/70">
                        Analysing data protection requirements for children&apos;s data...
                      </span>
                      {expandedReasoning ? (
                        <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 opacity-100" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </button>
                    {expandedReasoning && (
                      <div className="mt-2 pl-6 text-sm text-muted-foreground/80">
                        <p>The user is asking about data protection requirements for children&apos;s data under UK law. I should search for relevant legislation including the Data Protection Act 2018 and UK GDPR, as well as any relevant ICO guidance...</p>
                      </div>
                    )}
                  </div>

                  {/* Tool Call - matching actual implementation */}
                  <div>
                    <button
                      onClick={() => setExpandedTool(!expandedTool)}
                      className="group flex items-center gap-2 text-sm text-muted-foreground/70 hover:text-muted-foreground transition-colors w-full text-left cursor-pointer"
                    >
                      <Search className="h-3.5 w-3.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0 flex items-baseline gap-1.5">
                        <span className="capitalize flex-shrink-0">search legislation sections</span>
                        <span className="text-xs opacity-60 font-mono truncate">
                          &quot;children data protection AADC&quot;
                        </span>
                        <span className="text-xs opacity-60 whitespace-nowrap flex-shrink-0">
                          3 results
                        </span>
                      </div>
                      {expandedTool ? (
                        <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 opacity-100" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </button>
                    {expandedTool && (
                      <div className="mt-1 pl-6 space-y-1.5 text-xs text-muted-foreground/80">
                        <div className="border-l-2 border-muted-foreground/20 pl-2 py-0.5">
                          <div className="font-medium text-muted-foreground/90">Age appropriate design code</div>
                          <div className="text-muted-foreground/70">UKPGA 2018/12 s.123</div>
                        </div>
                        <div className="border-l-2 border-muted-foreground/20 pl-2 py-0.5">
                          <div className="font-medium text-muted-foreground/90">Processing of children&apos;s data</div>
                          <div className="text-muted-foreground/70">UKPGA 2018/12 s.9</div>
                        </div>
                        <div className="border-l-2 border-muted-foreground/20 pl-2 py-0.5">
                          <div className="font-medium text-muted-foreground/90">Parental consent requirements</div>
                          <div className="text-muted-foreground/70">UKPGA 2018/12 s.8</div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Final Response */}
                  <div className="prose dark:prose-invert max-w-none">
                    <p className="text-sm">
                      Under UK law, processing children&apos;s personal data requires special consideration.
                      The <strong>Data Protection Act 2018</strong> sets the age of consent for data processing at 13 years old,
                      and requires that privacy information be written in clear, age-appropriate language.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Chapter 5: System Feedback */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Chapter 5</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">System Feedback</h2>
                <p className="text-muted-foreground mt-2">
                  Clear status indicators and confirmation dialogs keep users informed.
                </p>
              </div>

              {/* Status Indicators - matching actual Status component */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Server className="h-5 w-5" />
                    Backend Status
                  </CardTitle>
                  <CardDescription>
                    Animated indicators with semantic colors
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Status status="online">
                      <StatusIndicator />
                      <StatusLabel />
                    </Status>
                    <Button variant="outline" size="sm">Refresh Status</Button>
                  </div>

                  <Separator />

                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">All status variants:</p>
                    <div className="flex flex-wrap gap-3">
                      <Status status="online">
                        <StatusIndicator />
                        <StatusLabel />
                      </Status>
                      <Status status="degraded">
                        <StatusIndicator />
                        <StatusLabel />
                      </Status>
                      <Status status="offline">
                        <StatusIndicator />
                        <StatusLabel />
                      </Status>
                      <Status status="maintenance">
                        <StatusIndicator />
                        <StatusLabel />
                      </Status>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Inline Alerts - matching actual implementation */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Inline Alerts</CardTitle>
                  <CardDescription>
                    Contextual feedback with semantic colors
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Offline alert */}
                  <div className="flex items-start gap-2 p-3 rounded-md bg-destructive/10 border border-destructive/20">
                    <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                    <div className="text-sm text-destructive">
                      <p className="font-medium">Backend is offline</p>
                      <p className="text-xs mt-1">
                        Make sure the backend server is running on port 8000
                      </p>
                    </div>
                  </div>

                  {/* Degraded alert */}
                  <div className="flex items-start gap-2 p-3 rounded-md bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800">
                    <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5" />
                    <div className="text-sm text-amber-800 dark:text-amber-200">
                      <p className="font-medium">Backend is degraded</p>
                      <p className="text-xs mt-1">
                        The backend is responding but may have issues
                      </p>
                    </div>
                  </div>

                  {/* Success message */}
                  <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-xs">Storage cleared successfully!</span>
                  </div>
                </CardContent>
              </Card>

              {/* Confirmation Dialog - matching AlertDialog usage */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Confirmation Dialog</CardTitle>
                  <CardDescription>
                    Destructive actions require explicit confirmation
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" size="sm">
                        <Trash2 className="mr-2 h-4 w-4" />
                        Clear Storage
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Clear Browser Storage?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will remove all search history and cached data stored by Lex.
                          This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction>Clear Storage</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </CardContent>
              </Card>
            </section>

            {/* Appendix: Badge Reference */}
            <section className="space-y-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Appendix</p>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">Badge Reference</h2>
                <p className="text-muted-foreground mt-2">
                  Domain-specific badges for legislation and caselaw metadata.
                </p>
              </div>

              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Legislation status (with icons)</p>
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge status="final" />
                      <StatusBadge status="revised" />
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Legislation type (monospace)</p>
                    <div className="flex flex-wrap gap-2">
                      <LegislationTypeBadge type="ukpga" year={2024} number={1} />
                      <LegislationTypeBadge type="uksi" year={2024} number={100} />
                      <LegislationTypeBadge type="asp" year={2024} number={5} />
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Territorial extent (outline)</p>
                    <div className="flex flex-wrap gap-2">
                      <ExtentBadges extent={["E+W+S+NI"]} />
                      <ExtentBadges extent={["E+W"]} />
                      <ExtentBadges extent={["S"]} />
                      <ExtentBadges extent={["NI"]} />
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Court badges (blue)</p>
                    <div className="flex flex-wrap gap-2">
                      <CourtBadge court="UKSC" />
                      <CourtBadge court="EWCA" division="Civ" />
                      <CourtBadge court="EWCA" division="Crim" />
                      <CourtBadge court="EWHC" division="Admin" />
                      <CourtBadge court="UKUT" />
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Citations (monospace outline)</p>
                    <div className="flex flex-wrap gap-2">
                      <CitationBadge citation="[2024] UKSC 1" />
                      <CitationBadge citation="[2024] EWCA Civ 123" />
                      <CitationBadge citation="[2024] EWHC 456 (Admin)" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

          </div>
        </ScrollArea>
      </SidebarInset>
    </SidebarProvider>
  )
}

"use client"

import { useState, useEffect } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { Streamdown } from "streamdown"
import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { ArrowRight, FileText, Scale, Settings, Check, Loader2, ChevronDown, ChevronRight, Brain, Search } from "lucide-react"

// Constants for spacing, animation, and defaults
const SPACING = {
  BETWEEN_GROUPS: 'mb-5',
  WITHIN_GROUP: 'space-y-1.5',
} as const

const ANIMATION = {
  DURATION_MS: 200,
  CLASSES: 'animate-in fade-in slide-in-from-top-1 duration-200',
} as const

const RESEARCH_DEFAULTS = {
  MAX_STEPS_MIN: 3,
  MAX_STEPS_MAX: 50,
  MAX_STEPS_DEFAULT: 25,
  INITIAL_INPUT_HEIGHT: '100px',
  FOLLOW_UP_INPUT_HEIGHT: '48px',
} as const

const RESEARCH_SETTINGS_KEY = 'lex-research-maxSteps'

// Type definitions for AI SDK message parts
interface MessagePart {
  type: string
  text?: string
  content?: string
  input?: Record<string, unknown>
  args?: Record<string, unknown>
  arguments?: Record<string, unknown>
  state?: 'input-streaming' | 'input-available' | 'output-available' | 'output-error'
  output?: {
    results?: Array<{
      title?: string
      citation?: string
      name?: string
      [key: string]: unknown
    }>
    count?: number
    [key: string]: unknown
  }
}

interface DisplayCard {
  type: 'reasoning' | 'tool' | 'text'
  text?: string
  name?: string
  args?: Record<string, unknown>
  state?: string
  result?: MessagePart['output']
  resultCount?: number
  id: number
}

// Strip markdown syntax from text (for preview only)
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')  // Remove bold
    .replace(/\*(.+?)\*/g, '$1')      // Remove italics
    .replace(/`(.+?)`/g, '$1')        // Remove code
    .replace(/\[(.+?)\]\(.+?\)/g, '$1') // Remove links, keep text
    .replace(/#+\s/g, '')             // Remove headings
}

// Split message into cards - keep reasoning and tools in order, group final text
function splitMessageForDisplay(parts: MessagePart[]): DisplayCard[] {
  const cards: DisplayCard[] = []

  parts.forEach((part, index) => {
    // Individual reasoning trace
    if (part.type === 'reasoning') {
      const text = part.text || part.content || ''
      if (text.trim()) {
        cards.push({
          type: 'reasoning',
          text,
          id: index
        })
      }
    }
    // Individual tool call
    else if (part.type?.startsWith('tool-') && part.type !== 'tool-result') {
      const toolName = part.type.replace('tool-', '')

      // Extract tool results if available
      let result: MessagePart['output'] = undefined
      let resultCount = 0
      if (part.state === 'output-available' && part.output) {
        result = part.output
        // Try to count results
        if (Array.isArray(result)) {
          resultCount = result.length
        } else if (result.results && Array.isArray(result.results)) {
          resultCount = result.results.length
        } else if (typeof result === 'object' && result.count) {
          resultCount = result.count
        }
      }

      cards.push({
        type: 'tool',
        name: toolName,
        args: part.input || part.args || part.arguments,
        state: part.state,
        result,
        resultCount,
        id: index
      })
    }
    // Collect all text for final card
    else if (part.type === 'text') {
      const text = part.text
      if (text?.trim()) {
        const lastCard = cards[cards.length - 1]
        if (lastCard && lastCard.type === 'text') {
          lastCard.text += text
        } else {
          cards.push({ type: 'text', text, id: index })
        }
      }
    }
  })

  return cards
}

export default function ResearchPage() {
  const [includeLegislation, setIncludeLegislation] = useState(true)
  const [includeCaselaw, setIncludeCaselaw] = useState(true)
  const [showFilters, setShowFilters] = useState(false)
  const [input, setInput] = useState('')
  const [maxSteps, setMaxSteps] = useState<number>(RESEARCH_DEFAULTS.MAX_STEPS_DEFAULT)
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({})

  const { messages, sendMessage, status } = useChat({
    transport: new DefaultChatTransport({
      api: '/api/research/chat',
      body: {
        includeLegislation,
        includeCaselaw,
        maxSteps,
      },
    }),
  })

  // Load maxSteps from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(RESEARCH_SETTINGS_KEY)
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (!isNaN(parsed) && parsed >= RESEARCH_DEFAULTS.MAX_STEPS_MIN && parsed <= RESEARCH_DEFAULTS.MAX_STEPS_MAX) {
        setMaxSteps(parsed)
      }
    }
  }, [])

  const hasContent = Boolean(input.trim())
  const isLoading = status === 'submitted' || status === 'streaming'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (hasContent && status === 'ready') {
      sendMessage({ text: input })
      setInput('')
    }
  }

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
                <BreadcrumbItem>
                  <BreadcrumbPage>Deep Research</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col px-6">
          {/* Show input box when no messages, show chat when messages exist */}
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center">
              <div className="w-full max-w-3xl space-y-8 -mt-20">
                <h2 className="text-3xl font-medium text-center">What are you researching?</h2>

                <div className="relative w-full">
                  <div className="relative">
                    <form onSubmit={handleSubmit}>
                      <div className="rounded-[2rem] border border-input/50 bg-background/50 backdrop-blur-sm shadow-sm overflow-hidden">
                        <textarea
                          id="research-query"
                          placeholder="Ask me anything about UK legislation or caselaw..."
                          className="w-full min-h-[100px] px-6 pt-5 pb-12 text-base bg-transparent resize-none focus-visible:outline-none"
                          value={input}
                          onChange={(e) => setInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault()
                              if (hasContent) {
                                handleSubmit(e)
                              }
                            }
                          }}
                        />

                        <div className="flex items-center justify-between px-4 pb-3">
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="rounded-full h-10 w-10"
                            onClick={() => setShowFilters(!showFilters)}
                          >
                            <Settings className={`h-6 w-6 transition-transform duration-300 ${showFilters ? 'rotate-90' : ''}`} />
                          </Button>

                          <Button
                            type="submit"
                            size="icon"
                            variant={hasContent ? "default" : "ghost"}
                            className="rounded-full h-10 w-10 transition-all"
                            disabled={!hasContent || isLoading}
                          >
                            {isLoading ? (
                              <Loader2 className="h-6 w-6 animate-spin" />
                            ) : (
                              <ArrowRight className="h-6 w-6" />
                            )}
                          </Button>
                        </div>
                      </div>
                    </form>

                    {/* Settings drawer */}
                    <div
                      className={`overflow-hidden transition-all duration-300 ${
                        showFilters ? 'max-h-96 opacity-100 mt-[-1rem]' : 'max-h-0 opacity-0'
                      }`}
                    >
                      <div className="pt-6 px-5 pb-5 rounded-b-[2rem] bg-muted/30 border border-t-0 border-input/50">
                        <div className="space-y-4">
                          <div className="space-y-2.5">
                            <p className="text-sm text-muted-foreground font-medium">Search within</p>
                            <div className="flex gap-2">
                              <Button
                                type="button"
                                variant={includeLegislation ? "default" : "outline"}
                                size="sm"
                                onClick={() => setIncludeLegislation(!includeLegislation)}
                                className="flex items-center gap-2 transition-all"
                              >
                                <FileText className="h-3.5 w-3.5" />
                                Legislation
                                {includeLegislation && (
                                  <Check className="h-3.5 w-3.5 animate-in fade-in zoom-in duration-200" />
                                )}
                              </Button>
                              <Button
                                type="button"
                                variant={includeCaselaw ? "default" : "outline"}
                                size="sm"
                                onClick={() => setIncludeCaselaw(!includeCaselaw)}
                                className="flex items-center gap-2 transition-all"
                              >
                                <Scale className="h-3.5 w-3.5" />
                                Caselaw
                                {includeCaselaw && (
                                  <Check className="h-3.5 w-3.5 animate-in fade-in zoom-in duration-200" />
                                )}
                              </Button>
                            </div>
                          </div>

                          <div className="space-y-2.5">
                            <div className="flex items-center justify-between">
                              <p className="text-sm text-muted-foreground font-medium">Research depth</p>
                              <span className="text-xs text-muted-foreground">Max {maxSteps} steps</span>
                            </div>
                            <input
                              type="range"
                              min={RESEARCH_DEFAULTS.MAX_STEPS_MIN}
                              max={RESEARCH_DEFAULTS.MAX_STEPS_MAX}
                              value={maxSteps}
                              onChange={(e) => setMaxSteps(parseInt(e.target.value))}
                              className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                            />
                            <p className="text-xs text-muted-foreground">
                              {maxSteps <= 10 ? 'Quick research' : maxSteps <= 25 ? 'Balanced' : maxSteps <= 35 ? 'Deep dive' : 'Comprehensive'}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Chat interface */
            <div className="flex flex-1 flex-col max-w-3xl mx-auto w-full">
              <div className="flex-1 space-y-6 overflow-y-auto px-4 py-8">
                {messages.map((message) => {
                  if (message.role === 'user') {
                    return (
                      <div key={message.id} className="flex justify-end">
                        <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-primary text-primary-foreground">
                          <p className="text-sm whitespace-pre-wrap">
                            {message.parts.find((p) => p.type === 'text')?.text}
                          </p>
                        </div>
                      </div>
                    )
                  }

                  // Assistant message - split into cards (reasoning, tools, text)
                  const cards = splitMessageForDisplay(message.parts as MessagePart[])

                  return (
                    <div key={message.id} className="flex justify-start">
                      <div className={`max-w-[85%] ${SPACING.WITHIN_GROUP}`}>
                        {cards.map((card, cardIndex) => {
                          // Check if next card is different type for extra spacing
                          const nextCard = cards[cardIndex + 1]
                          const isDifferentTypeNext = nextCard && nextCard.type !== card.type
                          const extraSpacing = isDifferentTypeNext ? SPACING.BETWEEN_GROUPS : ''

                          // Individual reasoning trace - show first line with expand
                          if (card.type === 'reasoning') {
                            const expandKey = `${message.id}-reasoning-${card.id}`
                            const isExpanded = expandedTools[expandKey] ?? false

                            // Extract first line for preview and strip markdown
                            const firstLine = stripMarkdown(((card.text || '').split('\n')[0] || '').trim())

                            return (
                              <div key={cardIndex} className={extraSpacing}>
                                <button
                                  onClick={() => setExpandedTools(prev => ({
                                    ...prev,
                                    [expandKey]: !prev[expandKey]
                                  }))}
                                  aria-label={isExpanded ? "Collapse reasoning trace" : "Expand reasoning trace"}
                                  aria-expanded={isExpanded}
                                  className="group flex items-center gap-2 text-sm text-muted-foreground/70 hover:text-muted-foreground transition-colors w-full text-left"
                                >
                                  <Brain className="h-3.5 w-3.5 flex-shrink-0" />
                                  <span className="italic flex-1 text-muted-foreground/70">
                                    {firstLine}
                                  </span>
                                  {isExpanded ? (
                                    <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 opacity-100" />
                                  ) : (
                                    <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                                  )}
                                </button>

                                {isExpanded && (
                                  <div className={`mt-2 pl-6 prose prose-sm dark:prose-invert max-w-none opacity-80
                                    prose-headings:text-muted-foreground prose-p:text-muted-foreground
                                    prose-strong:text-muted-foreground prose-ul:text-muted-foreground
                                    prose-ol:text-muted-foreground prose-li:text-muted-foreground
                                    prose-code:text-muted-foreground prose-code:bg-muted/50
                                    ${ANIMATION.CLASSES}`}>
                                    <Streamdown parseIncompleteMarkdown={true}>
                                      {(card.text || '').split('\n').slice(1).join('\n')}
                                    </Streamdown>
                                  </div>
                                )}
                              </div>
                            )
                          }

                          // Individual tool call
                          if (card.type === 'tool') {
                            const expandKey = `${message.id}-tool-${card.id}`
                            const isExpanded = expandedTools[expandKey] ?? false
                            const hasResults = card.state === 'output-available' && (card.resultCount ?? 0) > 0

                            return (
                              <div key={cardIndex} className={extraSpacing}>
                                <button
                                  onClick={() => hasResults && setExpandedTools(prev => ({
                                    ...prev,
                                    [expandKey]: !prev[expandKey]
                                  }))}
                                  aria-label={hasResults ? (isExpanded ? "Collapse tool results" : "Expand tool results") : "No results available"}
                                  aria-expanded={hasResults ? isExpanded : undefined}
                                  className={`group flex items-center gap-2 text-sm text-muted-foreground/70 w-full text-left ${hasResults ? 'hover:text-muted-foreground transition-colors cursor-pointer' : 'cursor-default'}`}
                                  disabled={!hasResults}
                                >
                                  <Search className="h-3.5 w-3.5 flex-shrink-0" />
                                  <div className="flex-1 min-w-0 flex items-baseline gap-1.5">
                                    <span className="capitalize flex-shrink-0">{(card.name || '').replace(/_/g, ' ')}</span>
                                    {card.args && typeof card.args.query === 'string' && card.args.query && (
                                      <span className="text-xs opacity-60 font-mono truncate">
                                        &quot;{card.args.query}&quot;
                                      </span>
                                    )}
                                    {hasResults && (
                                      <span className="text-xs opacity-60 whitespace-nowrap flex-shrink-0">
                                        {card.resultCount} result{card.resultCount !== 1 ? 's' : ''}
                                      </span>
                                    )}
                                  </div>
                                  {hasResults && (
                                    isExpanded ? (
                                      <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 opacity-100" />
                                    ) : (
                                      <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                                    )
                                  )}
                                </button>

                                {isExpanded && hasResults && card.result && (
                                  <div className={`mt-1 pl-6 space-y-1.5 text-xs text-muted-foreground/80 ${ANIMATION.CLASSES}`}>
                                    {/* Render results based on structure - handle both wrapped and direct arrays */}
                                    {(() => {
                                      // Get results array - handle both direct array and wrapped in {results: []}
                                      const resultsArray = Array.isArray(card.result)
                                        ? card.result
                                        : (card.result.results && Array.isArray(card.result.results) ? card.result.results : [])

                                      // Determine tool type for appropriate rendering
                                      const isLegislationSection = card.name === 'search_legislation_sections'
                                      const isCaselawSummary = card.name === 'search_caselaw_summaries'
                                      const isAmendment = card.name === 'search_amendments'

                                      return (
                                        <>
                                          {resultsArray.slice(0, 3).map((result: Record<string, unknown>, i: number) => (
                                            <div key={i} className="border-l-2 border-muted-foreground/20 pl-2 py-0.5">
                                              {/* Legislation sections: show title and reference */}
                                              {isLegislationSection && (
                                                <>
                                                  <div className="font-medium text-muted-foreground/90">
                                                    {result.title as string || 'Untitled section'}
                                                  </div>
                                                  <div className="text-muted-foreground/70">
                                                    {(result.legislation_type as string || '').toUpperCase()} {result.legislation_year}/{result.legislation_number}
                                                    {result.number && ` s.${result.number}`}
                                                  </div>
                                                </>
                                              )}

                                              {/* Caselaw summaries: show name and citation */}
                                              {isCaselawSummary && (
                                                <>
                                                  <div className="font-medium text-muted-foreground/90">
                                                    {result.name as string || 'Unnamed case'}
                                                  </div>
                                                  <div className="text-muted-foreground/70">
                                                    {result.cite_as as string || `${(result.court as string || '').toUpperCase()} ${result.year}`}
                                                  </div>
                                                </>
                                              )}

                                              {/* Amendments: show amending/amended legislation */}
                                              {isAmendment && (
                                                <>
                                                  <div className="font-medium text-muted-foreground/90">
                                                    {result.amending_title as string || result.amended_title as string || 'Amendment'}
                                                  </div>
                                                  <div className="text-muted-foreground/70">
                                                    {result.change_type as string || 'Modified'}
                                                  </div>
                                                </>
                                              )}

                                              {/* Default fallback for other tools */}
                                              {!isLegislationSection && !isCaselawSummary && !isAmendment && (
                                                <>
                                                  {result.title && (
                                                    <div className="font-medium text-muted-foreground/90">{result.title as string}</div>
                                                  )}
                                                  {result.citation && (
                                                    <div className="text-muted-foreground/70">{result.citation as string}</div>
                                                  )}
                                                  {result.cite_as && !result.citation && (
                                                    <div className="text-muted-foreground/70">{result.cite_as as string}</div>
                                                  )}
                                                  {result.name && !result.title && (
                                                    <div className="font-medium text-muted-foreground/90">{result.name as string}</div>
                                                  )}
                                                </>
                                              )}
                                            </div>
                                          ))}
                                          {resultsArray.length > 3 && (
                                            <div className="pl-2 text-muted-foreground/60 italic">
                                              +{resultsArray.length - 3} more result{resultsArray.length - 3 !== 1 ? 's' : ''}
                                            </div>
                                          )}
                                        </>
                                      )
                                    })()}
                                  </div>
                                )}
                              </div>
                            )
                          }

                          // Text card - markdown rendering with Streamdown
                          if (card.type === 'text') {
                            return (
                              <div key={cardIndex} className={`prose dark:prose-invert max-w-none ${extraSpacing}`}>
                                <Streamdown parseIncompleteMarkdown={true}>
                                  {card.text}
                                </Streamdown>
                              </div>
                            )
                          }

                          return null
                        })}
                      </div>
                    </div>
                  )
                })}

                {isLoading && (
                  <div className="flex justify-start">
                    <div className="flex items-center gap-2 text-muted-foreground/70">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span className="text-sm italic">Researching...</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Sticky input at bottom */}
              <div className="sticky bottom-0 px-4 pb-4 pt-8 bg-gradient-to-t from-background via-background to-transparent">
                <form onSubmit={handleSubmit} className="relative">
                  <div className="relative rounded-[2rem] border border-input/50 bg-background shadow-lg overflow-hidden">
                    <textarea
                      placeholder="Ask a follow-up question..."
                      className="w-full h-[48px] px-6 pt-[14px] pb-[14px] pr-14 text-base leading-5 bg-transparent resize-none focus-visible:outline-none"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          if (hasContent) {
                            handleSubmit(e)
                          }
                        }
                      }}
                    />

                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <Button
                        type="submit"
                        size="icon"
                        variant={hasContent ? "default" : "ghost"}
                        className="rounded-full h-8 w-8"
                        disabled={!hasContent || isLoading}
                      >
                        {isLoading ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                          <ArrowRight className="h-5 w-5" />
                        )}
                      </Button>
                    </div>
                  </div>
                </form>

                <p className="text-xs text-center text-muted-foreground mt-2">
                  Lex can make mistakes. Check important info.
                </p>
              </div>
            </div>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

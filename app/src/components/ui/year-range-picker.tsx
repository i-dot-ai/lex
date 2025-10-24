"use client"

import * as React from "react"
import { Calendar, Clock, Building2, Landmark, Scale, Globe, ChevronLeft, ChevronRight, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export interface YearRange {
  from?: number
  to?: number
}

interface YearRangePickerProps {
  value?: YearRange
  onChange: (range: YearRange) => void
  minYear?: number
  maxYear?: number
  placeholder?: string
  disabled?: boolean
}

interface Preset {
  label: string
  range: YearRange
  icon: React.ComponentType<{ className?: string }>
}

interface PresetGroup {
  heading: string
  icon: React.ComponentType<{ className?: string }>
  presets: Preset[]
}

const getCurrentYear = () => new Date().getFullYear()

export function YearRangePicker({
  value,
  onChange,
  minYear = 1267,
  maxYear = getCurrentYear(),
  placeholder = "Select years",
  disabled = false,
}: YearRangePickerProps) {
  const [open, setOpen] = React.useState(false)
  const [tempFrom, setTempFrom] = React.useState<number | undefined>(value?.from)
  const [tempTo, setTempTo] = React.useState<number | undefined>(value?.to)
  const [currentDecade, setCurrentDecade] = React.useState(Math.floor(maxYear / 10) * 10)
  const [inputFrom, setInputFrom] = React.useState<string>(value?.from?.toString() || "")
  const [inputTo, setInputTo] = React.useState<string>(value?.to?.toString() || "")

  // Update internal state when external value changes
  React.useEffect(() => {
    setTempFrom(value?.from)
    setTempTo(value?.to)
    setInputFrom(value?.from?.toString() || "")
    setInputTo(value?.to?.toString() || "")
  }, [value])

  const presetGroups: PresetGroup[] = [
    {
      heading: "Quick Ranges",
      icon: Clock,
      presets: [
        { label: "Current year", range: { from: maxYear, to: maxYear }, icon: Calendar },
        { label: "Last year", range: { from: maxYear - 1, to: maxYear - 1 }, icon: Calendar },
        { label: "Last 5 years", range: { from: maxYear - 4, to: maxYear }, icon: Calendar },
        { label: "Last 10 years", range: { from: maxYear - 9, to: maxYear }, icon: Calendar },
      ],
    },
    {
      heading: "Parliaments",
      icon: Building2,
      presets: [
        { label: "Current (2024-)", range: { from: 2024, to: maxYear }, icon: Building2 },
        { label: "2019-2024", range: { from: 2019, to: 2024 }, icon: Building2 },
        { label: "2017-2019", range: { from: 2017, to: 2019 }, icon: Building2 },
        { label: "Coalition+ (2010-24)", range: { from: 2010, to: 2024 }, icon: Building2 },
      ],
    },
    {
      heading: "Political Eras",
      icon: Landmark,
      presets: [
        { label: "Post-Brexit (2020-)", range: { from: 2020, to: maxYear }, icon: Landmark },
        { label: "Brexit era (2016-)", range: { from: 2016, to: maxYear }, icon: Landmark },
        { label: "New Labour (1997-10)", range: { from: 1997, to: 2010 }, icon: Landmark },
        { label: "Thatcher/Major (79-97)", range: { from: 1979, to: 1997 }, icon: Landmark },
        { label: "Post-war (1945-79)", range: { from: 1945, to: 1979 }, icon: Landmark },
      ],
    },
    {
      heading: "Legislative Periods",
      icon: Scale,
      presets: [
        { label: "Devolution+ (1998-)", range: { from: 1998, to: maxYear }, icon: Scale },
        { label: "Modern (1963-)", range: { from: 1963, to: maxYear }, icon: Scale },
        { label: "Historical (1267-1962)", range: { from: 1267, to: 1962 }, icon: Globe },
        { label: "All time", range: { from: minYear, to: maxYear }, icon: Globe },
      ],
    },
  ]

  const handlePresetClick = (range: YearRange) => {
    onChange(range)
    setOpen(false)
  }

  const handleYearClick = (year: number) => {
    if (!tempFrom || (tempFrom && tempTo)) {
      // First click or reset: set as start year
      setTempFrom(year)
      setTempTo(undefined)
      setInputFrom(year.toString())
      setInputTo("")
    } else {
      // Second click: set as end year
      const from = Math.min(tempFrom, year)
      const to = Math.max(tempFrom, year)
      onChange({ from, to })
      setOpen(false)
    }
  }

  const handleManualInputChange = () => {
    const from = inputFrom ? parseInt(inputFrom, 10) : undefined
    const to = inputTo ? parseInt(inputTo, 10) : undefined

    if (from !== undefined && isNaN(from)) return
    if (to !== undefined && isNaN(to)) return
    if (from !== undefined && (from < minYear || from > maxYear)) return
    if (to !== undefined && (to < minYear || to > maxYear)) return
    if (from !== undefined && to !== undefined && from > to) return

    onChange({ from, to })
    setOpen(false)
  }

  const handleClear = () => {
    onChange({ from: undefined, to: undefined })
    setTempFrom(undefined)
    setTempTo(undefined)
    setInputFrom("")
    setInputTo("")
  }

  const handlePreviousDecade = () => {
    const newDecade = currentDecade - 10
    if (newDecade >= Math.floor(minYear / 10) * 10) {
      setCurrentDecade(newDecade)
    }
  }

  const handleNextDecade = () => {
    const newDecade = currentDecade + 10
    if (newDecade <= Math.floor(maxYear / 10) * 10) {
      setCurrentDecade(newDecade)
    }
  }

  const getDecadeYears = () => {
    const years: number[] = []
    const decadeEnd = Math.min(currentDecade + 9, maxYear)
    for (let year = currentDecade; year <= decadeEnd; year++) {
      if (year >= minYear) {
        years.push(year)
      }
    }
    return years
  }

  const isYearInRange = (year: number) => {
    if (!tempFrom && !value?.from) return false
    const from = tempFrom ?? value?.from
    const to = tempTo ?? value?.to

    if (from && !to) return year === from
    if (from && to) return year >= from && year <= to
    return false
  }

  const isYearRangeStart = (year: number) => {
    const from = tempFrom ?? value?.from
    return from === year
  }

  const isYearRangeEnd = (year: number) => {
    const to = tempTo ?? value?.to
    return to === year
  }

  const formatDisplayValue = () => {
    if (!value?.from && !value?.to) return null
    if (value.from && !value.to) return `${value.from}`
    if (!value.from && value.to) return `to ${value.to}`
    if (value.from === value.to) return `${value.from}`
    return `${value.from} - ${value.to}`
  }

  const displayValue = formatDisplayValue()

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className={cn(
            "flex p-1 min-h-10 h-auto items-center justify-between text-left font-normal",
            !displayValue && "text-muted-foreground"
          )}
        >
          <div className="flex items-center gap-2 py-[0.525rem]">
            <Calendar className="h-4 w-4" />
            <span>{displayValue || placeholder}</span>
          </div>
          {displayValue && (
            <X
              className="h-4 w-4 opacity-50 hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation()
                handleClear()
              }}
            />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex">
          {/* Left Panel - Presets */}
          <div className="border-r">
            <ScrollArea className="h-[400px] w-[220px]">
              <div className="p-4 space-y-4">
                {presetGroups.map((group) => (
                  <div key={group.heading} className="space-y-2">
                    <div className="flex items-center gap-2 px-2">
                      <group.icon className="h-3.5 w-3.5 text-muted-foreground" />
                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        {group.heading}
                      </h4>
                    </div>
                    <div className="space-y-1">
                      {group.presets.map((preset) => {
                        const isActive =
                          value?.from === preset.range.from &&
                          value?.to === preset.range.to
                        return (
                          <Button
                            key={preset.label}
                            variant="ghost"
                            size="sm"
                            onClick={() => handlePresetClick(preset.range)}
                            className={cn(
                              "w-full justify-start text-sm h-8 px-2",
                              isActive && "bg-accent font-medium"
                            )}
                          >
                            <preset.icon className="h-3.5 w-3.5 mr-2 opacity-50" />
                            {preset.label}
                          </Button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Right Panel - Year Selector */}
          <div className="w-[280px] p-4 space-y-4">
            {/* Decade Navigator */}
            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePreviousDecade}
                disabled={currentDecade <= Math.floor(minYear / 10) * 10}
                className="h-8 w-8 p-0"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="text-sm font-semibold">
                {currentDecade}s
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNextDecade}
                disabled={currentDecade >= Math.floor(maxYear / 10) * 10}
                className="h-8 w-8 p-0"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Year Grid */}
            <div className="grid grid-cols-5 gap-1">
              {getDecadeYears().map((year) => {
                const inRange = isYearInRange(year)
                const isStart = isYearRangeStart(year)
                const isEnd = isYearRangeEnd(year)

                return (
                  <Button
                    key={year}
                    variant="ghost"
                    size="sm"
                    onClick={() => handleYearClick(year)}
                    className={cn(
                      "h-9 text-sm",
                      inRange && "bg-primary/10",
                      (isStart || isEnd) && "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground"
                    )}
                  >
                    {year}
                  </Button>
                )
              })}
            </div>

            <Separator />

            {/* Manual Input */}
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="from" className="text-xs">
                    From
                  </Label>
                  <Input
                    id="from"
                    type="number"
                    placeholder={minYear.toString()}
                    value={inputFrom}
                    onChange={(e) => setInputFrom(e.target.value)}
                    min={minYear}
                    max={maxYear}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="to" className="text-xs">
                    To
                  </Label>
                  <Input
                    id="to"
                    type="number"
                    placeholder={maxYear.toString()}
                    value={inputTo}
                    onChange={(e) => setInputTo(e.target.value)}
                    min={minYear}
                    max={maxYear}
                    className="h-8 text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClear}
                  className="flex-1 h-8 text-xs"
                >
                  Clear
                </Button>
                <Button
                  size="sm"
                  onClick={handleManualInputChange}
                  disabled={!inputFrom && !inputTo}
                  className="flex-1 h-8 text-xs"
                >
                  Apply
                </Button>
              </div>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

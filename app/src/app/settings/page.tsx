"use client"

import { useState, useEffect } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Status, StatusIndicator, StatusLabel } from "@/components/ui/status"
import { Server, Trash2, AlertCircle, CheckCircle, Brain } from "lucide-react"
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

type BackendStatus = 'online' | 'offline' | 'degraded'

const RESEARCH_SETTINGS_KEY = 'lex-research-maxSteps'
const DEFAULT_MAX_STEPS = 25
const MIN_STEPS = 3
const MAX_STEPS = 50

export default function SettingsPage() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('offline')
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [clearSuccess, setClearSuccess] = useState(false)
  const [maxSteps, setMaxSteps] = useState<number>(DEFAULT_MAX_STEPS)

  const checkBackendStatus = async () => {
    setIsCheckingStatus(true)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/healthcheck`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000) // 5 second timeout
      })

      if (response.ok) {
        setBackendStatus('online')
      } else {
        setBackendStatus('degraded')
      }
      setLastChecked(new Date())
    } catch (err) {
      console.error('Backend health check failed:', err)
      setBackendStatus('offline')
      setLastChecked(new Date())
    } finally {
      setIsCheckingStatus(false)
    }
  }

  const clearBrowserStorage = () => {
    try {
      // Clear localStorage items related to Lex
      const lexKeys = Object.keys(localStorage).filter(key =>
        key.startsWith('lex-') || key.includes('search-history')
      )
      lexKeys.forEach(key => localStorage.removeItem(key))

      // Clear sessionStorage
      sessionStorage.clear()

      setClearSuccess(true)
      setTimeout(() => setClearSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to clear storage:', err)
    }
  }

  useEffect(() => {
    checkBackendStatus()
    // Check every 30 seconds
    const interval = setInterval(checkBackendStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  // Load maxSteps from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(RESEARCH_SETTINGS_KEY)
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (!isNaN(parsed) && parsed >= MIN_STEPS && parsed <= MAX_STEPS) {
        setMaxSteps(parsed)
      }
    }
  }, [])

  // Save maxSteps to localStorage when it changes
  useEffect(() => {
    localStorage.setItem(RESEARCH_SETTINGS_KEY, maxSteps.toString())
  }, [maxSteps])

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
                  <BreadcrumbPage>Settings</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-6">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">Settings</h1>
            <p className="text-sm text-muted-foreground">
              Manage your Lex application settings and system status
            </p>
          </div>

          {/* Backend Status Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                Backend Status
              </CardTitle>
              <CardDescription>
                Connection status to the Lex backend API
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Status status={backendStatus}>
                    <StatusIndicator />
                    <StatusLabel />
                  </Status>
                  {lastChecked && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Last checked: {lastChecked.toLocaleTimeString()}
                    </p>
                  )}
                </div>
                <Button
                  onClick={checkBackendStatus}
                  disabled={isCheckingStatus}
                  variant="outline"
                  size="sm"
                >
                  {isCheckingStatus ? "Checking..." : "Refresh Status"}
                </Button>
              </div>

              {backendStatus === 'offline' && (
                <div className="flex items-start gap-2 p-3 rounded-md bg-destructive/10 border border-destructive/20">
                  <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                  <div className="text-sm text-destructive">
                    <p className="font-medium">Backend is offline</p>
                    <p className="text-xs mt-1">
                      Make sure the backend server is running on port 8000
                    </p>
                  </div>
                </div>
              )}

              {backendStatus === 'degraded' && (
                <div className="flex items-start gap-2 p-3 rounded-md bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800">
                  <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5" />
                  <div className="text-sm text-amber-800 dark:text-amber-200">
                    <p className="font-medium">Backend is degraded</p>
                    <p className="text-xs mt-1">
                      The backend is responding but may have issues
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Research Settings Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Research Settings
              </CardTitle>
              <CardDescription>
                Configure default settings for deep research queries
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label htmlFor="maxSteps" className="text-sm font-medium">
                    Maximum Research Steps
                  </label>
                  <span className="text-sm text-muted-foreground">
                    {maxSteps} steps
                  </span>
                </div>
                <input
                  id="maxSteps"
                  type="range"
                  min={MIN_STEPS}
                  max={MAX_STEPS}
                  value={maxSteps}
                  onChange={(e) => setMaxSteps(parseInt(e.target.value))}
                  className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <p className="text-xs text-muted-foreground">
                  {maxSteps <= 10 ? 'Quick research (fewer tool calls)' : maxSteps <= 25 ? 'Balanced (recommended)' : maxSteps <= 35 ? 'Deep dive (thorough analysis)' : 'Comprehensive (maximum depth)'}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Browser Storage Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trash2 className="h-5 w-5" />
                Browser Storage
              </CardTitle>
              <CardDescription>
                Clear local data stored by Lex (search history, preferences)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm">
                    Clear all cached data and search history
                  </p>
                  {clearSuccess && (
                    <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle className="h-4 w-4" />
                      <span className="text-xs">Storage cleared successfully!</span>
                    </div>
                  )}
                </div>
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
                      <AlertDialogAction onClick={clearBrowserStorage}>
                        Clear Storage
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </CardContent>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

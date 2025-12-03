"use client"

import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { FileText, Search, Scale, ExternalLink } from "lucide-react"
import Link from "next/link"
import { API_CONFIG } from "@/lib/config"

export default function Home() {
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
                  <BreadcrumbPage>Home</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-8 p-4 pt-0">
          {/* Hero Section */}
          <div className="space-y-4 text-center max-w-2xl mx-auto mt-12">
            <h1 className="text-4xl font-bold tracking-tight">Lex API Demo</h1>
            <p className="text-muted-foreground text-lg">
              See what you can build with the Lex UK Legal Research API.
              Semantic search across legislation and caselaw.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <a
                href={`${API_CONFIG.backendUrl}/docs`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline" size="sm">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  API Reference
                </Button>
              </a>
              <a
                href={`${API_CONFIG.backendUrl}/`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="ghost" size="sm">
                  About Lex
                </Button>
              </a>
            </div>
          </div>

          {/* Search Options */}
          <div className="grid gap-6 md:grid-cols-2 max-w-4xl mx-auto w-full">
            <Link href="/legislation" className="group">
              <Card className="h-full transition-all hover:shadow-lg hover:border-primary/50">
                <CardHeader className="pb-4">
                  <div className="flex items-center justify-center mb-4">
                    <div className="p-3 rounded-full bg-primary/10">
                      <FileText className="h-8 w-8 text-primary" />
                    </div>
                  </div>
                  <CardTitle className="text-2xl text-center">Legislation</CardTitle>
                  <CardDescription className="text-center">
                    UK Acts, Statutory Instruments, and regulations
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button className="w-full" size="lg">
                    <Search className="mr-2 h-4 w-4" />
                    Search Legislation
                  </Button>
                </CardContent>
              </Card>
            </Link>

            <Link href="/caselaw" className="group">
              <Card className="h-full transition-all hover:shadow-lg hover:border-primary/50">
                <CardHeader className="pb-4">
                  <div className="flex items-center justify-center mb-4">
                    <div className="p-3 rounded-full bg-primary/10">
                      <Scale className="h-8 w-8 text-primary" />
                    </div>
                  </div>
                  <CardTitle className="text-2xl text-center">Caselaw</CardTitle>
                  <CardDescription className="text-center">
                    UK court judgments and tribunal decisions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button className="w-full" size="lg">
                    <Search className="mr-2 h-4 w-4" />
                    Search Caselaw
                  </Button>
                </CardContent>
              </Card>
            </Link>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

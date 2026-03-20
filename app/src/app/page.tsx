"use client"

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
import { Search, Microscope, ArrowRight } from "lucide-react"
import Link from "next/link"

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

        <div className="flex flex-1 flex-col items-center justify-center p-4 pt-0">
          <div className="space-y-6 text-center max-w-md">
            <h1 className="text-4xl font-bold tracking-tight animate-in fade-in slide-in-from-bottom-2 duration-500">Lex</h1>
            <p className="text-muted-foreground text-lg animate-in fade-in slide-in-from-bottom-2 duration-500 delay-100">
              Semantic search across 125,000+ UK laws.
            </p>

            <div className="flex flex-col gap-3 pt-2 animate-in fade-in slide-in-from-bottom-3 duration-500 delay-200">
              <Link href="/legislation">
                <Button className="w-full transition-all hover:-translate-y-0.5 hover:shadow-md" size="lg">
                  <Search className="mr-2 h-4 w-4" />
                  Search Legislation
                </Button>
              </Link>
              <Link href="/research">
                <Button variant="outline" className="w-full transition-all hover:-translate-y-0.5 hover:shadow-md" size="lg">
                  <Microscope className="mr-2 h-4 w-4" />
                  Deep Research
                  <ArrowRight className="ml-auto h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

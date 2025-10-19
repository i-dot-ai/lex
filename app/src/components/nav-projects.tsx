"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Folder, Plus, Archive, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { getAllProjects, getDocumentCount } from "@/lib/projects"
import type { Project } from "@/lib/projects"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { ProjectCreateModal } from "@/components/project-create-modal"

export function NavProjects() {
  const pathname = usePathname()
  const [projects, setProjects] = useState<Project[]>([])
  const [isOpen, setIsOpen] = useState(true)
  const [showArchived, setShowArchived] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)

  const loadProjects = () => {
    const allProjects = getAllProjects()
    setProjects(allProjects)
  }

  useEffect(() => {
    loadProjects()

    // Listen for storage events (updates from other tabs)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'lex_projects') {
        loadProjects()
      }
    }

    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  const handleProjectCreated = (projectId: string) => {
    loadProjects()
    // Navigate to the new project
    window.location.href = `/projects/${projectId}`
  }

  const activeProjects = projects.filter(p => p.status === 'active')
  const archivedProjects = projects.filter(p => p.status === 'archived')

  return (
    <>
      <SidebarMenu>
        <Collapsible
          open={isOpen}
          onOpenChange={setIsOpen}
          className="group/collapsible"
          asChild
          defaultOpen={true}
        >
          <SidebarMenuItem>
            <CollapsibleTrigger asChild>
              <SidebarMenuButton tooltip="Projects">
                <Folder />
                <span>Projects</span>
                <span
                  className="ml-auto inline-flex h-6 w-6 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation()
                    setCreateModalOpen(true)
                  }}
                  title="Create new project"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.stopPropagation()
                      e.preventDefault()
                      setCreateModalOpen(true)
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </span>
                <ChevronRight className="transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarMenuButton>
            </CollapsibleTrigger>

            <CollapsibleContent>
              <SidebarMenuSub>
                {activeProjects.length === 0 ? (
                  <div className="px-2 py-4 text-center">
                    <p className="text-sm text-muted-foreground mb-2">
                      No projects yet
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCreateModalOpen(true)}
                      className="w-full"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Create Project
                    </Button>
                  </div>
                ) : (
                  <>
                    {activeProjects.map((project) => {
                      const isActive = pathname === `/projects/${project.id}`
                      const docCount = getDocumentCount(project.id)

                      return (
                        <SidebarMenuSubItem key={project.id}>
                          <SidebarMenuSubButton asChild isActive={isActive}>
                            <Link href={`/projects/${project.id}`}>
                              <div
                                className="h-3 w-3 rounded-full shrink-0"
                                style={{ backgroundColor: project.color || '#3b82f6' }}
                              />
                              <span className="flex-1 truncate">{project.name}</span>
                              {docCount > 0 && (
                                <span className="text-xs text-muted-foreground shrink-0 ml-auto">
                                  {docCount}
                                </span>
                              )}
                            </Link>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      )
                    })}

                    {archivedProjects.length > 0 && (
                      <>
                        <SidebarMenuSubItem>
                          <SidebarMenuSubButton
                            className="w-full mt-2"
                            onClick={() => setShowArchived(!showArchived)}
                          >
                            <Archive className="h-4 w-4 shrink-0" />
                            <span className="flex-1">
                              Archived ({archivedProjects.length})
                            </span>
                            <ChevronRight
                              className={cn(
                                "h-4 w-4 transition-transform",
                                showArchived && "rotate-90"
                              )}
                            />
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>

                        {showArchived && archivedProjects.map((project) => {
                          const isActive = pathname === `/projects/${project.id}`
                          const docCount = getDocumentCount(project.id)

                          return (
                            <SidebarMenuSubItem key={project.id}>
                              <SidebarMenuSubButton asChild isActive={isActive} className="opacity-60">
                                <Link href={`/projects/${project.id}`}>
                                  <div
                                    className="h-3 w-3 rounded-full shrink-0"
                                    style={{ backgroundColor: project.color || '#6b7280' }}
                                  />
                                  <span className="flex-1 truncate">{project.name}</span>
                                  {docCount > 0 && (
                                    <span className="text-xs text-muted-foreground shrink-0 ml-auto">
                                      {docCount}
                                    </span>
                                  )}
                                </Link>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          )
                        })}
                      </>
                    )}
                  </>
                )}
              </SidebarMenuSub>
            </CollapsibleContent>
          </SidebarMenuItem>
        </Collapsible>
      </SidebarMenu>

      <ProjectCreateModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onCreated={handleProjectCreated}
      />
    </>
  )
}

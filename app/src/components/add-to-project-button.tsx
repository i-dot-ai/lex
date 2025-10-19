"use client"

import { useState, useEffect } from "react"
import { Folder, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  getAllProjects,
  addDocumentToProject,
  removeDocumentFromProject,
  isDocumentInProject,
  type ProjectDocument
} from "@/lib/projects"
import { ProjectCreateModal } from "@/components/project-create-modal"

interface AddToProjectButtonProps {
  document: Omit<ProjectDocument, 'id' | 'addedAt'>
  variant?: "default" | "outline" | "ghost"
  size?: "default" | "sm" | "lg"
  onAdded?: (projectId: string) => void
}

export function AddToProjectButton({
  document,
  variant = "outline",
  size = "sm",
  onAdded
}: AddToProjectButtonProps) {
  const [projects, setProjects] = useState(getAllProjects())
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [documentInProjects, setDocumentInProjects] = useState<Set<string>>(new Set())

  const loadProjects = () => {
    const allProjects = getAllProjects()
    setProjects(allProjects)

    // Check which projects contain this document
    const projectIds = new Set<string>()
    allProjects.forEach(project => {
      if (isDocumentInProject(project.id, document.documentId)) {
        projectIds.add(project.id)
      }
    })
    setDocumentInProjects(projectIds)
  }

  useEffect(() => {
    loadProjects()

    // Listen for storage events
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'lex_projects') {
        loadProjects()
      }
    }

    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [document.documentId])

  const handleToggleProject = (projectId: string) => {
    if (documentInProjects.has(projectId)) {
      // Remove from project
      removeDocumentFromProject(projectId, document.documentId)
    } else {
      // Add to project
      addDocumentToProject(projectId, document)
      onAdded?.(projectId)
    }

    loadProjects()
  }

  const handleProjectCreated = (projectId: string) => {
    // Add document to newly created project
    addDocumentToProject(projectId, document)
    loadProjects()
    onAdded?.(projectId)
  }

  const activeProjects = projects.filter(p => p.status === 'active')
  const hasProjects = activeProjects.length > 0

  if (!hasProjects) {
    return (
      <>
        <Button
          variant={variant}
          size={size}
          onClick={() => setCreateModalOpen(true)}
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Project
        </Button>
        <ProjectCreateModal
          open={createModalOpen}
          onOpenChange={setCreateModalOpen}
          onCreated={handleProjectCreated}
        />
      </>
    )
  }

  return (
    <>
      <TooltipProvider>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant={variant} size={size}>
              <Folder className="h-4 w-4 mr-2" />
              {documentInProjects.size > 0
                ? `In ${documentInProjects.size} project${documentInProjects.size > 1 ? 's' : ''}`
                : 'Add to Project'
              }
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-56">
            {activeProjects.map(project => {
              const isInProject = documentInProjects.has(project.id)

              return (
                <Tooltip key={project.id} delayDuration={300}>
                  <TooltipTrigger asChild>
                    <DropdownMenuItem
                      onClick={() => handleToggleProject(project.id)}
                      className={isInProject ? "bg-accent/50" : ""}
                    >
                      <div className="flex items-center gap-2 flex-1">
                        <div
                          className="h-3 w-3 rounded-full shrink-0"
                          style={{ backgroundColor: project.color || '#3b82f6' }}
                        />
                        <span className="flex-1 truncate">{project.name}</span>
                        {isInProject ? (
                          <X className="h-4 w-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <Plus className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100" />
                        )}
                      </div>
                    </DropdownMenuItem>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    {isInProject ? 'Click to remove from project' : 'Click to add to project'}
                  </TooltipContent>
                </Tooltip>
              )
            })}

            <DropdownMenuSeparator />

            <DropdownMenuItem onClick={() => setCreateModalOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create New Project
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <ProjectCreateModal
          open={createModalOpen}
          onOpenChange={setCreateModalOpen}
          onCreated={handleProjectCreated}
        />
      </TooltipProvider>
    </>
  )
}

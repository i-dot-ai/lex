"use client"

import { use, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { AppSidebar } from "@/components/app-sidebar"
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  FileText,
  Scale,
  Calendar,
  MoreVertical,
  Download,
  Trash2,
  Archive,
  ExternalLink,
} from "lucide-react"
import {
  getProject,
  updateProject,
  deleteProject,
  removeDocumentFromProject,
  downloadProjectJSON,
} from "@/lib/projects"
import type { Project } from "@/lib/projects"

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()
  const [project, setProject] = useState<Project | null>(null)
  const [searchFilter, setSearchFilter] = useState("")
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteDocId, setDeleteDocId] = useState<string | null>(null)

  const loadProject = () => {
    const p = getProject(id)
    setProject(p)
    if (!p) {
      router.push("/")
    }
  }

  useEffect(() => {
    loadProject()
  }, [id])

  const handleArchive = () => {
    if (!project) return
    updateProject(id, { status: project.status === 'archived' ? 'active' : 'archived' })
    loadProject()
  }

  const handleDelete = () => {
    deleteProject(id)
    router.push("/")
  }

  const handleRemoveDocument = (docId: string) => {
    removeDocumentFromProject(id, docId)
    loadProject()
    setDeleteDocId(null)
  }

  const handleExport = () => {
    downloadProjectJSON(id)
  }

  if (!project) {
    return (
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <div className="flex items-center justify-center h-screen">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </SidebarInset>
      </SidebarProvider>
    )
  }

  const filteredDocuments = project.documents.filter(doc =>
    doc.metadata.title.toLowerCase().includes(searchFilter.toLowerCase())
  )

  const legislationDocs = filteredDocuments.filter(d => d.type === 'legislation')
  const caselawDocs = filteredDocuments.filter(d => d.type === 'caselaw')

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
                  <BreadcrumbPage>Projects</BreadcrumbPage>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>{project.name}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          {/* Project Header */}
          <div className="flex items-start justify-between">
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-2">
                <div
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: project.color || '#3b82f6' }}
                />
                <h2 className="text-2xl font-bold tracking-tight">{project.name}</h2>
                {project.status === 'archived' && (
                  <Badge variant="secondary">Archived</Badge>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>Created {new Date(project.created).toLocaleDateString()}</span>
                <span>•</span>
                <span>Updated {new Date(project.updated).toLocaleDateString()}</span>
                <span>•</span>
                <span>{project.documents.length} documents</span>
              </div>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleExport}>
                  <Download className="h-4 w-4 mr-2" />
                  Export JSON
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleArchive}>
                  <Archive className="h-4 w-4 mr-2" />
                  {project.status === 'archived' ? 'Unarchive' : 'Archive'}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => setDeleteDialogOpen(true)}
                  className="text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Project
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Description */}
          {project.description && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {project.description}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Research Goal */}
          {project.researchGoal && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Research Goal</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {project.researchGoal}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Documents */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Documents ({project.documents.length})</CardTitle>
                  <CardDescription>
                    Legislation and caselaw in this project
                  </CardDescription>
                </div>
                <Input
                  placeholder="Search documents..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-64"
                />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {project.documents.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground mb-4">
                    No documents yet. Start searching and add documents to this project.
                  </p>
                  <div className="flex gap-2 justify-center">
                    <Button variant="outline" asChild>
                      <a href="/legislation">Search Legislation</a>
                    </Button>
                    <Button variant="outline" asChild>
                      <a href="/caselaw">Search Caselaw</a>
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  {legislationDocs.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="font-semibold text-sm flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Legislation ({legislationDocs.length})
                      </h3>
                      {legislationDocs.map((doc) => (
                        <Card key={doc.id} className="p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 space-y-1">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium text-sm">{doc.metadata.title}</h4>
                                <Badge variant="outline" className="text-xs">
                                  {doc.metadata.legislationType?.toUpperCase()}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Calendar className="h-3 w-3" />
                                <span>{doc.metadata.year}</span>
                                <span>•</span>
                                <span>Added {new Date(doc.addedAt).toLocaleDateString()}</span>
                                {doc.addedBy === 'agent' && (
                                  <>
                                    <span>•</span>
                                    <Badge variant="secondary" className="text-xs">AI Added</Badge>
                                  </>
                                )}
                              </div>
                              {doc.notes && (
                                <p className="text-sm text-muted-foreground mt-2">
                                  {doc.notes}
                                </p>
                              )}
                            </div>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                asChild
                              >
                                <a href={doc.documentId} target="_blank" rel="noopener noreferrer">
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setDeleteDocId(doc.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}

                  {caselawDocs.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="font-semibold text-sm flex items-center gap-2">
                        <Scale className="h-4 w-4" />
                        Caselaw ({caselawDocs.length})
                      </h3>
                      {caselawDocs.map((doc) => (
                        <Card key={doc.id} className="p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 space-y-1">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium text-sm">{doc.metadata.title}</h4>
                                {doc.metadata.court && (
                                  <Badge variant="outline" className="text-xs">
                                    {doc.metadata.court.toUpperCase()}
                                  </Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                {doc.metadata.citation && <span>{doc.metadata.citation}</span>}
                                {doc.metadata.year && (
                                  <>
                                    <span>•</span>
                                    <span>{doc.metadata.year}</span>
                                  </>
                                )}
                                <span>•</span>
                                <span>Added {new Date(doc.addedAt).toLocaleDateString()}</span>
                                {doc.addedBy === 'agent' && (
                                  <>
                                    <span>•</span>
                                    <Badge variant="secondary" className="text-xs">AI Added</Badge>
                                  </>
                                )}
                              </div>
                              {doc.notes && (
                                <p className="text-sm text-muted-foreground mt-2">
                                  {doc.notes}
                                </p>
                              )}
                            </div>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                asChild
                              >
                                <a href={doc.documentId} target="_blank" rel="noopener noreferrer">
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setDeleteDocId(doc.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Delete Project Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Project</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete &ldquo;{project.name}&rdquo;? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete Document Dialog */}
        <AlertDialog open={!!deleteDocId} onOpenChange={(open) => !open && setDeleteDocId(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Remove Document</AlertDialogTitle>
              <AlertDialogDescription>
                Remove this document from the project? This won&rsquo;t delete the document itself.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => deleteDocId && handleRemoveDocument(deleteDocId)}>
                Remove
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SidebarInset>
    </SidebarProvider>
  )
}

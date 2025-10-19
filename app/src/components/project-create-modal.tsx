"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { createProject, validateProject } from "@/lib/projects"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

interface ProjectCreateModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: (projectId: string) => void
}

const COLORS = [
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Green', value: '#10b981' },
  { name: 'Yellow', value: '#f59e0b' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Red', value: '#ef4444' },
  { name: 'Purple', value: '#a855f7' },
  { name: 'Pink', value: '#ec4899' },
  { name: 'Gray', value: '#6b7280' },
]

export function ProjectCreateModal({
  open,
  onOpenChange,
  onCreated
}: ProjectCreateModalProps) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [researchGoal, setResearchGoal] = useState("")
  const [selectedColor, setSelectedColor] = useState(COLORS[0]?.value ?? '#3b82f6')
  const [errors, setErrors] = useState<string[]>([])
  const [isCreating, setIsCreating] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors([])

    // Validate
    const validation = validateProject({ name, description })
    if (!validation.valid) {
      setErrors(validation.errors)
      return
    }

    setIsCreating(true)

    try {
      const project = createProject({
        name: name.trim(),
        description: description.trim(),
        color: selectedColor,
        researchGoal: researchGoal.trim() || undefined
      })

      // Reset form
      setName("")
      setDescription("")
      setResearchGoal("")
      setSelectedColor(COLORS[0]?.value ?? '#3b82f6')
      setErrors([])

      // Close modal and notify parent
      onOpenChange(false)
      onCreated?.(project.id)
    } catch (error) {
      setErrors([(error as Error).message || 'Failed to create project'])
    } finally {
      setIsCreating(false)
    }
  }

  const handleCancel = () => {
    setName("")
    setDescription("")
    setResearchGoal("")
    setSelectedColor(COLORS[0]?.value ?? '#3b82f6')
    setErrors([])
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
            <DialogDescription>
              Create a project to organize your research. You can add documents manually or use AI to populate it.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {errors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {errors.map((error, i) => (
                    <div key={i}>{error}</div>
                  ))}
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="name">
                Project Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder="e.g., GDPR Compliance Review 2025"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                required
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Optional description of your research project"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={500}
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="researchGoal">Research Goal</Label>
              <Textarea
                id="researchGoal"
                placeholder="Optional: What are you trying to research? This helps the AI understand your needs."
                value={researchGoal}
                onChange={(e) => setResearchGoal(e.target.value)}
                rows={2}
              />
              <p className="text-xs text-muted-foreground">
                e.g., &ldquo;Find all UK legislation and cases related to data protection for financial services&rdquo;
              </p>
            </div>

            <div className="space-y-2">
              <Label>Color</Label>
              <div className="flex gap-2">
                {COLORS.map((color) => (
                  <button
                    key={color.value}
                    type="button"
                    onClick={() => setSelectedColor(color.value)}
                    className={`w-8 h-8 rounded-full border-2 transition-all ${
                      selectedColor === color.value
                        ? 'border-foreground scale-110'
                        : 'border-transparent hover:border-muted-foreground'
                    }`}
                    style={{ backgroundColor: color.value }}
                    title={color.name}
                  />
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isCreating || !name.trim()}>
              {isCreating ? 'Creating...' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

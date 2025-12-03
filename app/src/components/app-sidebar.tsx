"use client"

import * as React from "react"
import {
  Scale,
  Search,
  BookOpen,
  Home,
  Microscope,
  Settings,
} from "lucide-react"

import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarGroup,
} from "@/components/ui/sidebar"
import { API_CONFIG } from "@/lib/config"

// Navigation data for Lex
const data = {
  user: {
    name: "Lex",
  },
  teams: [
    {
      name: "Lex",
      logo: Scale,
      plan: "UK Legal Search",
    },
  ],
  navMain: [
    {
      title: "Home",
      url: "/",
      icon: Home,
      isActive: false,
    },
    {
      title: "Deep Research",
      url: "/research",
      icon: Microscope,
      isActive: false,
    },
    {
      title: "Search",
      url: "#",
      icon: Search,
      isActive: true,
      items: [
        {
          title: "Legislation",
          url: "/legislation",
        },
        {
          title: "Caselaw",
          url: "/caselaw",
        },
      ],
    },
    {
      title: "Documentation",
      url: "#",
      icon: BookOpen,
      items: [
        {
          title: "About Lex",
          url: `${API_CONFIG.backendUrl}/`,
          external: true,
        },
        {
          title: "API Reference",
          url: `${API_CONFIG.backendUrl}/docs`,
          external: true,
        },
      ],
    },
    {
      title: "Settings",
      url: "/settings",
      icon: Settings,
      isActive: false,
    },
  ],
  projects: [],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const platformItems = data.navMain.filter(item => !["Documentation", "Settings"].includes(item.title))
  const documentationItems = data.navMain.filter(item => item.title === "Documentation")
  const settingsItems = data.navMain.filter(item => item.title === "Settings")

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <NavMain items={platformItems} />
          <NavMain items={documentationItems} />
          <NavMain items={settingsItems} />
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

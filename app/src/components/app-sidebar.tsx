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
      title: "Settings",
      url: "/settings",
      icon: Settings,
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
          title: "API Docs",
          url: `${API_CONFIG.baseUrl}/docs`,
        },
        {
          title: "About Lex",
          url: "#",
        },
      ],
    },
  ],
  projects: [],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const platformItems = data.navMain.filter(item => item.title !== "Documentation")
  const documentationItems = data.navMain.filter(item => item.title === "Documentation")

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <NavMain items={platformItems} />
          <NavMain items={documentationItems} />
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

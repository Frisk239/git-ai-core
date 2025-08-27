import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  HomeIcon,
  FolderIcon,
  CogIcon,
  CpuChipIcon,
  CodeBracketIcon,
  BookOpenIcon,
} from "@heroicons/react/24/outline";

const navigation = [
  { name: "Overview", href: "/", icon: HomeIcon },
  { name: "Projects", href: "/projects", icon: FolderIcon },
  {
    name: "GitHub Recommendations",
    href: "/github-recommendations",
    icon: BookOpenIcon,
  },
  { name: "GitHub Settings", href: "/github-settings", icon: CogIcon },
  { name: "AI Settings", href: "/ai-settings", icon: CogIcon },
  { name: "MCP Settings", href: "/mcp-settings", icon: CogIcon },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();

  return (
    <div className="w-64 bg-gradient-to-b from-[#f6f8fa] to-[#f3f4f6] border-r border-[#d0d7de]">
      <div className="h-full flex flex-col">
        <nav className="flex-1 px-3 py-4">
          <div className="space-y-1">
            {navigation.map((item) => {
              const isActive =
                location.pathname === item.href ||
                (item.href === "/projects" &&
                  location.pathname.startsWith("/projects/"));
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-[#ddf4ff] text-[#0969da] font-semibold"
                      : "text-[#24292f] hover:bg-[#f3f4f6] hover:text-[#0969da]"
                  }`}
                >
                  <item.icon className="h-4 w-4 mr-3" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
    </div>
  );
};

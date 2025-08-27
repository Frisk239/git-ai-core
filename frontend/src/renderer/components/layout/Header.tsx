import React from "react";
import {
  BellIcon,
  PlusIcon,
  CodeBracketIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

export const Header: React.FC = () => {
  const navigate = useNavigate();

  return (
    <header className="bg-[#ffffff] border-b border-[#d0d7de] shadow-sm">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center space-x-6">
          <div className="flex items-center group">
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-[#58a6ff] to-[#0969da] rounded-lg mr-3 shadow-sm group-hover:shadow-md transition-shadow">
              <CodeBracketIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-[#656d76] to-[#58a6ff] bg-clip-text text-transparent">
                Git-Tutor AI
              </h1>
              <p className="text-xs text-[#656d76] mt-0.5">
                AI-powered Git Assistant
              </p>
            </div>
          </div>
          <div className="h-8 w-px bg-[#e1e4e8]"></div>
          <nav className="flex space-x-1">
            <button
              onClick={() => navigate("/github-recommendations")}
              className="flex items-center px-4 py-2 text-sm font-medium text-[#656d76] hover:text-[#0969da] hover:bg-[#f6f8fa] rounded-lg transition-all duration-200 hover:scale-105 active:scale-95 transform"
            >
              <MagnifyingGlassIcon className="h-4 w-4 mr-2 hover:rotate-12 transition-transform duration-200" />
              Explore
            </button>
          </nav>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate("/projects")}
            className="flex items-center px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-[#58a6ff] to-[#0969da] rounded-lg shadow-sm hover:shadow-lg hover:scale-105 active:scale-95 transition-all duration-300 ease-in-out transform"
          >
            <PlusIcon className="h-4 w-4 mr-2 animate-pulse" />
            New repository
          </button>

          <button className="p-2 text-[#656d76] hover:text-[#0969da] hover:bg-[#f6f8fa] rounded-lg transition-all duration-200 relative hover:scale-110 active:scale-95 transform">
            <BellIcon className="h-5 w-5 hover:animate-bounce" />
          </button>

          <div className="w-9 h-9 bg-gradient-to-br from-[#58a6ff] to-[#0969da] rounded-full flex items-center justify-center text-white text-sm font-bold shadow-sm hover:shadow-lg hover:scale-110 transition-all duration-300 ease-in-out transform cursor-pointer">
            <span className="hover:rotate-12 transition-transform duration-300">
              AI
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

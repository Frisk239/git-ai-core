import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { Dashboard } from "./components/pages/Dashboard";
import { Projects } from "./components/pages/Projects";
import { AISettings } from "./components/pages/AISettings";
import { MCPSettings } from "./components/pages/MCPSettings";
import { GitHubSettings } from "./components/pages/GitHubSettings";
import { GitHubRecommendations } from "./components/pages/GitHubRecommendations";
import { ProjectDetail } from "./components/pages/ProjectDetail";
import "./styles/App.css";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="flex flex-col h-screen bg-gray-50">
          {/* 顶部导航栏 */}
          <Header />

          {/* 内容区域：左边边栏 + 右边页面 */}
          <div className="flex flex-1 overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/projects" element={<Projects />} />
                <Route path="/projects/:path" element={<ProjectDetail />} />
                <Route path="/ai-settings" element={<AISettings />} />
                <Route path="/github-settings" element={<GitHubSettings />} />
                <Route path="/mcp-settings" element={<MCPSettings />} />
                <Route
                  path="/github-recommendations"
                  element={<GitHubRecommendations />}
                />
              </Routes>
            </main>
          </div>
        </div>
        <Toaster position="top-right" />
      </Router>
    </QueryClientProvider>
  );
}

export default App;

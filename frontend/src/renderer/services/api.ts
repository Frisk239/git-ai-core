import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 增加超时时间到120秒
})

export const api = {
  // Git operations
  async cloneRepository(url: string, path?: string) {
    const response = await apiClient.post('/api/git/clone', { url, path })
    return response.data
  },

  async getProjects() {
    const response = await apiClient.get('/api/git/projects')
    return response.data
  },

  async getProjectOverview(path: string) {
    const response = await apiClient.get(`/api/git/projects/${encodeURIComponent(path)}`)
    return response.data
  },

  async getProjectStructure(path: string, maxDepth = 3) {
    const response = await apiClient.get(`/api/git/projects/${encodeURIComponent(path)}/tree?max_depth=${maxDepth}`)
    return response.data
  },

  async getFileContent(projectPath: string, filePath: string) {
    const response = await apiClient.post('/api/git/projects/file', {
      path: projectPath,
      file_path: filePath
    })
    return response.data
  },

  async getDirectoryContent(projectPath: string, subPath: string = '') {
    const response = await apiClient.get(`/api/git/projects/${encodeURIComponent(projectPath)}/tree`, {
      params: { max_depth: 10 }
    })
    return response.data
  },

  // 项目管理功能
  async deleteProject(projectPath: string) {
    const response = await apiClient.delete(`/api/git/projects/${encodeURIComponent(projectPath)}`)
    return response.data
  },

  async pullUpdates(projectPath: string) {
    const response = await apiClient.post(`/api/git/projects/${encodeURIComponent(projectPath)}/pull`)
    return response.data
  },

  async getProjectStatus(projectPath: string) {
    const response = await apiClient.get(`/api/git/projects/${encodeURIComponent(projectPath)}/status`)
    return response.data
  },

  // AI operations
  async getAIProviders() {
    const response = await apiClient.get('/api/ai/providers')
    return response.data
  },

  async testAIConnection(provider: string, apiKey: string, baseUrl?: string) {
    const response = await apiClient.post('/api/ai/test-connection', {
      provider,
      api_key: apiKey,
      base_url: baseUrl
    })
    return response.data
  },

  async chatWithAI(provider: string, model: string, messages: any[], apiKey: string, options = {}) {
    const response = await apiClient.post('/api/ai/chat', {
      provider,
      model,
      messages,
      api_key: apiKey,
      ...options
    })
    return response.data
  },

  async analyzeProject(projectPath: string, query: string, provider: string, model: string, apiKey: string, baseUrl?: string) {
    const response = await apiClient.post(`/api/projects/${encodeURIComponent(projectPath)}/analyze`, {
      project_path: projectPath,
      query,
      provider,
      model,
      api_key: apiKey,
      base_url: baseUrl
    })
    return response.data
  },

  // MCP operations
  async getMCPServers() {
    const response = await apiClient.get('/api/mcp/servers')
    return response.data
  },

  async addMCPServer(config: any) {
    const response = await apiClient.post('/api/mcp/servers', config)
    return response.data
  },

  async updateMCPServer(name: string, config: any) {
    const response = await apiClient.put(`/api/mcp/servers/${name}`, config)
    return response.data
  },

  async removeMCPServer(name: string) {
    const response = await apiClient.delete(`/api/mcp/servers/${name}`)
    return response.data
  },

  async testMCPServer(config: any) {
    const response = await apiClient.post('/api/mcp/servers/test', { config })
    return response.data
  },

  async executeMCPTool(serverName: string, toolName: string, arguments_: any) {
    const response = await apiClient.post('/api/mcp/execute', {
      server_name: serverName,
      tool_name: toolName,
      arguments: arguments_
    })
    return response.data
  },

  async getMCPTools(serverName: string) {
    const response = await apiClient.get(`/api/mcp/tools/${serverName}`)
    return response.data
  },

  // 一键触发功能
  async generateArchitectureDocumentation(projectPath: string, provider: string, model: string, apiKey: string, baseUrl?: string) {
    const response = await apiClient.post(`/api/projects/${encodeURIComponent(projectPath)}/analyze/architecture`, {
      provider,
      model,
      api_key: apiKey,
      base_url: baseUrl
    })
    return response.data
  },


  // 文件注释生成功能
  async generateFileComments(projectPath: string, filePath: string, fileContent: string, provider: string, model: string, apiKey: string, language?: string) {
    const response = await apiClient.post(`/api/projects/${encodeURIComponent(projectPath)}/generate-comments`, {
      file_path: filePath,
      file_content: fileContent,
      language: language || 'auto',
      provider,
      model,
      api_key: apiKey
    })
    return response.data
  },

  // 配置管理
  async getAIConfig() {
    const response = await apiClient.get('/api/config/ai')
    return response.data
  },

  async saveAIConfig(config: any) {
    const response = await apiClient.post('/api/config/ai', config)
    return response.data
  },

  async deleteAIConfig() {
    const response = await apiClient.delete('/api/config/ai')
    return response.data
  },

  // 智能对话功能
  async startSmartConversation(projectPath: string) {
    const response = await apiClient.post('/api/ai/smart-conversation/start', {
      project_path: projectPath
    })
    return response.data
  },

  async smartChat(conversationId: string, message: string, projectPath: string) {
    const response = await apiClient.post('/api/ai/smart-conversation/chat', {
      conversation_id: conversationId,
      message,
      project_path: projectPath
    })
    return response.data
  },

  async endSmartConversation(conversationId: string) {
    const response = await apiClient.post('/api/ai/smart-conversation/end', {
      conversation_id: conversationId
    })
    return response.data
  },

  // GitHub operations
  async getGitHubTrending() {
    const response = await apiClient.get('/api/github/trending')
    return response.data
  },

  async searchGitHubRepos(query: string, language?: string, sort?: string, order?: string, perPage?: number) {
    const response = await apiClient.post('/api/github/search', {
      query,
      language,
      sort,
      order,
      per_page: perPage
    })
    return response.data
  },

  async getGitHubRepoDetails(owner: string, repo: string) {
    const response = await apiClient.get(`/api/github/repo/${owner}/${repo}`)
    return response.data
  },

  async testGitHubConnection(accessToken: string) {
    const response = await apiClient.post('/api/github/test-connection', {
      access_token: accessToken
    })
    return response.data
  },

  async saveGitHubConfig(accessToken: string) {
    const response = await apiClient.post('/api/github/save-config', {
      access_token: accessToken
    })
    return response.data
  },

  async getGitHubConfig() {
    const response = await apiClient.get('/api/github/config')
    return response.data
  },

  async getGitHubStatus() {
    const response = await apiClient.get('/api/github/status')
    return response.data
  },

  // 增强搜索功能
  async enhancedSearchGitHubRepos(query: string, language?: string, 
                                updatedAfter?: string, sort?: string, perPage?: number) {
    const response = await apiClient.post('/api/github/enhanced-search', {
      query,
      language,
      updated_after: updatedAfter,
      sort,
      per_page: perPage
    })
    return response.data
  },

  // 个性化推荐
  async getGitHubRecommendations(userId: string = "default", limit: number = 10) {
    const response = await apiClient.get('/api/github/recommendations', {
      params: { user_id: userId, limit }
    })
    return response.data
  },

  // 记录用户行为
  async recordGitHubAction(repoFullName: string, actionType: string, 
                         searchQuery?: string, durationSeconds?: number) {
    const response = await apiClient.post('/api/github/record-action', {
      repo_full_name: repoFullName,
      action_type: actionType,
      search_query: searchQuery,
      duration_seconds: durationSeconds
    })
    return response.data
  }
}

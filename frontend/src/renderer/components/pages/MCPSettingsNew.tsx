import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { PlusIcon, TrashIcon, CogIcon, PlayIcon, DocumentDuplicateIcon, ClipboardDocumentIcon } from '@heroicons/react/24/outline'
import { api } from '../../services/api'

interface MCPServer {
  name: string
  command: string
  args?: string[]
  env?: Record<string, string>
  description?: string
  enabled?: boolean
  transportType?: string
  url?: string
  headers?: Record<string, string>
  builtin?: boolean
}

export const MCPSettingsNew: React.FC = () => {
  const [showModal, setShowModal] = useState(false)
  const [currentServer, setCurrentServer] = useState<MCPServer | null>(null)
  const [isTesting, setIsTesting] = useState(false)

  const queryClient = useQueryClient()

  const { data: servers = {} } = useQuery<Record<string, MCPServer>>({
    queryKey: ['mcp-servers'],
    queryFn: () => api.getMCPServers()
  })

  const addMutation = useMutation({
    mutationFn: (server: MCPServer) => api.addMCPServer(server),
    onSuccess: () => {
      toast.success('MCP服务器添加成功！')
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      setShowModal(false)
      setCurrentServer(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'MCP服务器添加失败')
    }
  })

  const updateMutation = useMutation({
    mutationFn: (server: MCPServer) => api.updateMCPServer(server.name, server),
    onSuccess: () => {
      toast.success('MCP服务器更新成功！')
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      setShowModal(false)
      setCurrentServer(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'MCP服务器更新失败')
    }
  })

  const removeMutation = useMutation({
    mutationFn: (name: string) => api.removeMCPServer(name),
    onSuccess: () => {
      toast.success('MCP服务器移除成功！')
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'MCP服务器移除失败')
    }
  })

  const handleAddServer = (server: MCPServer) => {
    addMutation.mutate(server)
  }

  const handleUpdateServer = (server: MCPServer) => {
    updateMutation.mutate(server)
  }

  const handleRemoveServer = (name: string) => {
    if (window.confirm('确定要删除这个MCP服务器吗？')) {
      removeMutation.mutate(name)
    }
  }

  const handleTestServer = async (config: MCPServer) => {
    setIsTesting(true)
    try {
      const result = await api.testMCPServer(config)
      if (result.success) {
        toast.success('服务器连接测试成功！')
      } else {
        toast.error(`测试失败: ${result.message}`)
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '服务器测试失败')
    } finally {
      setIsTesting(false)
    }
  }

  // 从剪贴板导入MCP服务器配置
  const handleImportFromClipboard = async () => {
    try {
      const clipboardText = await navigator.clipboard.readText()
      const json = JSON.parse(clipboardText)
      
      let serversToImport = []

      // 检查是否为Chatbox格式 (包含mcpServers键)
      if (json.mcpServers && typeof json.mcpServers === 'object') {
        // Chatbox格式: {"mcpServers": {"server-name": {config}}}
        for (const [serverName, config] of Object.entries(json.mcpServers)) {
          if (typeof config === 'object' && config !== null) {
            serversToImport.push({
              name: serverName,
              ...config
            })
          }
        }
      } else if (json.name && json.command) {
        // 简单格式: {"name": "server-name", "command": "cmd", ...}
        serversToImport.push(json)
      } else {
        toast.error('剪贴板中的配置格式不正确，缺少必要字段')
        return
      }

      if (serversToImport.length === 0) {
        toast.error('未找到有效的MCP服务器配置')
        return
      }

      // 导入所有找到的服务器
      for (const config of serversToImport) {
        addMutation.mutate({
          name: config.name,
          command: config.command,
          args: config.args || [],
          env: config.env || {},
          description: config.description || '',
          enabled: config.enabled !== false,
          transportType: config.transportType || 'stdio',
          url: config.url || '',
          headers: config.headers || {}
        })
      }

      toast.success(`成功导入 ${serversToImport.length} 个MCP服务器！`)
    } catch (error) {
      console.error('导入失败:', error)
      toast.error('导入失败：请确保剪贴板中包含有效的JSON配置')
    }
  }

  const serverList = Object.entries(servers || {}).map(([serverName, config]) => ({
    ...config,
    name: serverName
  }))

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">MCP服务器设置</h1>
          <p className="mt-1 text-gray-600">管理MCP服务器和工具配置</p>
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={handleImportFromClipboard}
            className="flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
            一键导入
          </button>
          <button
            onClick={() => {
              setCurrentServer({
                name: '',
                command: '',
                args: [],
                env: {},
                description: '',
                enabled: true,
                transportType: 'stdio',
                url: '',
                headers: {}
              })
              setShowModal(true)
            }}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            手动配置
          </button>
        </div>
      </div>

      {/* 内置服务器区域 */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">内置服务器</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {serverList.filter(s => s.builtin).map((server) => (
            <ServerCard
              key={server.name}
              server={server}
              onEdit={() => {
                setCurrentServer(server)
                setShowModal(true)
              }}
              onTest={() => handleTestServer(server)}
              onRemove={() => handleRemoveServer(server.name)}
              isBuiltin={true}
            />
          ))}
        </div>
      </div>

      {/* 自定义服务器区域 */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">自定义服务器</h2>
        {serverList.filter(s => !s.builtin).length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <CogIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">暂无自定义MCP服务器</p>
            <p className="text-sm text-gray-400 mt-1">点击上方按钮添加或导入服务器</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {serverList.filter(s => !s.builtin).map((server) => (
              <ServerCard
                key={server.name}
                server={server}
                onEdit={() => {
                  setCurrentServer(server)
                  setShowModal(true)
                }}
                onTest={() => handleTestServer(server)}
                onRemove={() => handleRemoveServer(server.name)}
                isBuiltin={false}
              />
            ))}
          </div>
        )}
      </div>

      {/* 添加/编辑服务器模态框 */}
      {showModal && currentServer && (
        <ServerConfigModal
          server={currentServer}
          onSave={(server) => {
            if (currentServer.name) {
              handleUpdateServer(server)
            } else {
              handleAddServer(server)
            }
          }}
          onClose={() => {
            setShowModal(false)
            setCurrentServer(null)
          }}
          onTest={handleTestServer}
          isTesting={isTesting}
        />
      )}
    </div>
  )
}

// 服务器卡片组件
const ServerCard: React.FC<{
  server: MCPServer
  onEdit: () => void
  onTest: () => void
  onRemove: () => void
  isBuiltin: boolean
}> = ({ server, onEdit, onTest, onRemove, isBuiltin }) => {
  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 flex items-center">
            {server.name}
            {isBuiltin && (
              <span className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                内置
              </span>
            )}
          </h3>
          {server.description && (
            <p className="text-sm text-gray-600 mt-1">{server.description}</p>
          )}
        </div>
        {!isBuiltin && (
          <button
            onClick={onRemove}
            className="p-1 text-red-600 hover:bg-red-50 rounded-md ml-2"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="space-y-2 text-sm text-gray-600 mb-4">
        <div>
          <span className="font-medium">类型:</span> {server.transportType || 'stdio'}
        </div>
        <div>
          <span className="font-medium">命令:</span> {server.command}
        </div>
        {server.args && server.args.length > 0 && (
          <div>
            <span className="font-medium">参数:</span> {server.args.join(' ')}
          </div>
        )}
      </div>

      <div className="flex space-x-2">
        <button
          onClick={onTest}
          className="flex-1 px-3 py-2 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 flex items-center justify-center"
        >
          <PlayIcon className="h-3 w-3 mr-1" />
          测试
        </button>
        <button
          onClick={onEdit}
          className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 flex items-center justify-center"
        >
          <CogIcon className="h-3 w-3 mr-1" />
          编辑
        </button>
      </div>
    </div>
  )
}

// 服务器配置模态框组件
const ServerConfigModal: React.FC<{
  server: MCPServer
  onSave: (server: MCPServer) => void
  onClose: () => void
  onTest: (server: MCPServer) => void
  isTesting: boolean
}> = ({ server, onSave, onClose, onTest, isTesting }) => {
  const [formData, setFormData] = useState<MCPServer>(server)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-4">
          {server.name ? '编辑MCP服务器' : '添加MCP服务器'}
        </h2>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  服务器名称 *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  传输类型
                </label>
                <select
                  value={formData.transportType || 'stdio'}
                  onChange={(e) => setFormData({ ...formData, transportType: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="stdio">标准输入输出 (stdio)</option>
                  <option value="http">HTTP</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                命令 *
              </label>
              <input
                type="text"
                value={formData.command}
                onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                placeholder="python -m app.core.comment_mcp_server"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                参数（空格分隔）
              </label>
              <input
                type="text"
                value={formData.args?.join(' ') || ''}
                onChange={(e) => setFormData({ 
                  ...formData, 
                  args: e.target.value.split(' ').filter(arg => arg.trim())
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="-m app.core.comment_mcp_server"
              />
            </div>

            {formData.transportType === 'http' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  URL *
                </label>
                <input
                  type="url"
                  value={formData.url || ''}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://api.example.com/mcp"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                描述
              </label>
              <input
                type="text"
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="MCP服务器描述"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={() => onTest(formData)}
              disabled={isTesting}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {isTesting ? '测试中...' : '测试连接'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
            >
              取消
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default MCPSettingsNew

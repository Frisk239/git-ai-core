import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '../../services/api'

interface AIProvider {
  name: string
  icon: string
  description: string
  models: string[]
  default_base_url: string
  requires_api_key: boolean
}

export const AISettings: React.FC = () => {
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [temperature, setTemperature] = useState<number>(0.7)
  const [maxTokens, setMaxTokens] = useState<number>(2000)
  const [topP, setTopP] = useState<number>(1.0)
  const [frequencyPenalty, setFrequencyPenalty] = useState<number>(0.0)
  const [presencePenalty, setPresencePenalty] = useState<number>(0.0)

  const { data: providers = {} } = useQuery<Record<string, AIProvider>>({
    queryKey: ['ai-providers'],
    queryFn: () => api.getAIProviders()
  })

  // 加载配置
  useQuery({
    queryKey: ['ai-config'],
    queryFn: async () => {
      const response = await api.getAIConfig()
      if (response.exists && response.config) {
        const config = response.config
        setSelectedProvider(config.ai_provider || '')
        setSelectedModel(config.ai_model || '')
        setApiKey(config.ai_api_key || '')
        setBaseUrl(config.ai_base_url || '')
        setTemperature(config.temperature || 0.7)
        setMaxTokens(config.max_tokens || 2000)
        setTopP(config.top_p || 1.0)
        setFrequencyPenalty(config.frequency_penalty || 0.0)
        setPresencePenalty(config.presence_penalty || 0.0)
      }
      return response
    }
  })

  const handleTestConnection = async () => {
    if (!selectedProvider || !apiKey) {
      toast.error('请选择提供商并输入API密钥')
      return
    }

    try {
      const result = await api.testAIConnection(selectedProvider, apiKey, baseUrl || undefined)
      if (result.success) {
        toast.success('连接成功！')
      } else {
        toast.error(result.error || '连接失败')
      }
    } catch (error) {
      toast.error('连接测试失败')
    }
  }

  const handleSave = async () => {
    // 保存设置到localStorage
    localStorage.setItem('ai-provider', selectedProvider)
    localStorage.setItem('ai-model', selectedModel)
    localStorage.setItem('ai-api-key', apiKey)
    localStorage.setItem('ai-base-url', baseUrl)
    localStorage.setItem('ai-temperature', temperature.toString())
    localStorage.setItem('ai-max-tokens', maxTokens.toString())
    localStorage.setItem('ai-top-p', topP.toString())
    localStorage.setItem('ai-frequency-penalty', frequencyPenalty.toString())
    localStorage.setItem('ai-presence-penalty', presencePenalty.toString())
    
    // 同时保存到配置文件
    try {
      await api.saveAIConfig({
        ai_provider: selectedProvider,
        ai_model: selectedModel,
        ai_api_key: apiKey,
        ai_base_url: baseUrl,
        temperature: temperature,
        max_tokens: maxTokens,
        top_p: topP,
        frequency_penalty: frequencyPenalty,
        presence_penalty: presencePenalty
      })
      toast.success('设置已保存到配置文件！')
    } catch (error) {
      toast.error('保存到配置文件失败，但已保存到本地存储')
    }
  }

  const providerList = Object.entries(providers).map(([key, provider]) => ({
    key,
    ...provider
  }))

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">AI设置</h1>
        <p className="mt-2 text-gray-600">配置您的AI提供商和模型</p>
      </div>

      <div className="max-w-2xl">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">提供商配置</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                选择提供商
              </label>
              <select
                value={selectedProvider}
                onChange={(e) => {
                  setSelectedProvider(e.target.value)
                  setSelectedModel('')
                  setBaseUrl(providers[e.target.value]?.default_base_url || '')
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">选择提供商</option>
                {providerList.map((provider) => (
                  <option key={provider.key} value={provider.key}>
                    {provider.icon} {provider.name} - {provider.description}
                  </option>
                ))}
              </select>
            </div>

            {selectedProvider && providers[selectedProvider] && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    模型
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">选择模型</option>
                    {providers[selectedProvider].models.map((model: string) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                </div>

                {providers[selectedProvider].requires_api_key && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      API密钥
                    </label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="输入您的API密钥"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    基础URL（可选）
                  </label>
                  {selectedProvider === 'moonshot' ? (
                    <select
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="international">国际版 (api.moonshot.ai)</option>
                      <option value="china">中国版 (api.moonshot.cn)</option>
                    </select>
                  ) : (
                    <input
                      type="url"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder={providers[selectedProvider].default_base_url}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>

                {/* AI参数设置 */}
                <div className="pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold mb-4">AI参数设置</h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        温度 (Temperature)
                        <span className="text-xs text-gray-500 ml-1">(0.0-2.0)</span>
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="2"
                        step="0.1"
                        value={temperature}
                        onChange={(e) => setTemperature(parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        最大令牌数 (Max Tokens)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="10000"
                        step="100"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Top-P
                        <span className="text-xs text-gray-500 ml-1">(0.0-1.0)</span>
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={topP}
                        onChange={(e) => setTopP(parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        频率惩罚 (Frequency Penalty)
                        <span className="text-xs text-gray-500 ml-1">(-2.0-2.0)</span>
                      </label>
                      <input
                        type="number"
                        min="-2"
                        max="2"
                        step="0.1"
                        value={frequencyPenalty}
                        onChange={(e) => setFrequencyPenalty(parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        存在惩罚 (Presence Penalty)
                        <span className="text-xs text-gray-500 ml-1">(-2.0-2.0)</span>
                      </label>
                      <input
                        type="number"
                        min="-2"
                        max="2"
                        step="0.1"
                        value={presencePenalty}
                        onChange={(e) => setPresencePenalty(parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex space-x-3 pt-4">
                  <button
                    onClick={handleTestConnection}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                  >
                    测试连接
                  </button>
                  <button
                    onClick={handleSave}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    保存设置
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="mt-6 bg-blue-50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-2">可用提供商</h3>
          <div className="space-y-2 text-sm text-blue-800">
            {providerList.map((provider) => (
              <div key={provider.key} className="flex items-center">
                <span className="mr-2">{provider.icon}</span>
                <span>{provider.name}: {provider.description}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

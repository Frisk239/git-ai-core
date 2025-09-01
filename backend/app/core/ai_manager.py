import os
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import openai
import anthropic
import google.generativeai as genai
import httpx
from app.core.config import settings
from app.core.ai_config_manager import ai_config_manager

class AIProvider(ABC):
    """抽象AI供应商接口"""
    
    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        pass

class OpenAIProvider(AIProvider):
    """OpenAI供应商实现"""
    
    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        client = openai.AsyncOpenAI(api_key=api_key, base_url=kwargs.get('base_url'))
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 2000),
            top_p=kwargs.get('top_p', 1.0),
            frequency_penalty=kwargs.get('frequency_penalty', 0.0),
            presence_penalty=kwargs.get('presence_penalty', 0.0)
        )
        
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    
    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        try:
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
            await client.models.list()
            return True
        except Exception:
            return False

class AnthropicProvider(AIProvider):
    """Anthropic供应商实现"""
    
    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        client = anthropic.AsyncAnthropic(api_key=api_key, base_url=kwargs.get('base_url'))
        
        # Convert messages to Anthropic format
        system_message = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]
        
        response = await client.messages.create(
            model=model,
            max_tokens=kwargs.get('max_tokens', 2000),
            temperature=kwargs.get('temperature', 0.7),
            system=system_message,
            messages=user_messages
        )
        
        return {
            "content": response.content[0].text,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }
    
    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
            await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return True
        except Exception:
            return False

class GeminiProvider(AIProvider):
    """Google Gemini供应商实现"""
    
    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        genai.configure(api_key=api_key)
        
        # Convert messages to Gemini format
        gemini_messages = []
        for message in messages:
            if message["role"] == "user":
                gemini_messages.append({"role": "user", "parts": [message["content"]]})
            elif message["role"] == "assistant":
                gemini_messages.append({"role": "model", "parts": [message["content"]]})
        
        model_instance = genai.GenerativeModel(model)
        response = await model_instance.generate_content_async(
            gemini_messages,
            generation_config={
                "temperature": kwargs.get('temperature', 0.7),
                "max_output_tokens": kwargs.get('max_tokens', 2000)
            }
        )
        
        return {
            "content": response.text,
            "usage": {
                "prompt_tokens": 0,  # Gemini doesn't provide token counts
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            response = await model.generate_content_async("Hello")
            return bool(response.text)
        except Exception:
            return False

class DeepSeekProvider(AIProvider):
    """DeepSeek供应商实现"""
    
    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=kwargs.get('base_url', 'https://api.deepseek.com/v1')
        )
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 2000),
            top_p=kwargs.get('top_p', 1.0),
            frequency_penalty=kwargs.get('frequency_penalty', 0.0),
            presence_penalty=kwargs.get('presence_penalty', 0.0)
        )
        
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    
    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        try:
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or 'https://api.deepseek.com/v1'
            )
            await client.models.list()
            return True
        except Exception:
            return False


class MoonshotProvider(AIProvider):
    """Moonshot供应商实现"""

    async def chat(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        base_url = kwargs.get('base_url')
        if base_url == 'china':
            base_url = 'https://api.moonshot.cn/v1'
        elif base_url == 'international' or base_url is None:
            base_url = 'https://api.moonshot.ai/v1'
        
        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 2000),
            top_p=kwargs.get('top_p', 1.0),
            frequency_penalty=kwargs.get('frequency_penalty', 0.0),
            presence_penalty=kwargs.get('presence_penalty', 0.0)
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

    async def test_connection(self, api_key: str, base_url: Optional[str] = None) -> bool:
        try:
            if base_url == 'china':
                base_url = 'https://api.moonshot.cn/v1'
            elif base_url == 'international' or base_url is None:
                base_url = 'https://api.moonshot.ai/v1'
            
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
            await client.models.list()
            return True
        except Exception:
            return False

class AIManager:
    """AI管理器 - 仿照Cline的设计"""
    
    def __init__(self):
        self.providers = {
            'openai': OpenAIProvider(),
            'anthropic': AnthropicProvider(),
            'gemini': GeminiProvider(),
            'deepseek': DeepSeekProvider(),
            'moonshot': MoonshotProvider()
        }
        
        self.provider_configs = {
            'openai': {
                'name': 'OpenAI',
                'icon': '🤖',
                'description': 'OpenAI GPT models',
                'models': ['gpt-4o', 'gpt-4o-mini', 'o3-mini', 'o4-mini'],
                'default_base_url': 'https://api.openai.com/v1',
                'requires_api_key': True
            },
            'anthropic': {
                'name': 'Anthropic',
                'icon': '🎭',
                'description': 'Claude models',
                'models': ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022'],
                'default_base_url': 'https://api.anthropic.com',
                'requires_api_key': True
            },
            'gemini': {
                'name': 'Google Gemini',
                'icon': '🔷',
                'description': 'Gemini models',
                'models': ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'],
                'default_base_url': 'https://generativelanguage.googleapis.com/v1beta',
                'requires_api_key': True
            },
            'deepseek': {
                'name': 'DeepSeek',
                'icon': '🦔',
                'description': 'DeepSeek models',
                'models': ['deepseek-chat', 'deepseek-reasoner'],
                'default_base_url': 'https://api.deepseek.com/v1',
                'requires_api_key': True
            },
            'moonshot': {
                'name': 'Moonshot',
                'icon': '🌙',
                'description': 'Moonshot AI models',
                'models': ['kimi-k2-0711-preview', 'kimi-k2-turbo-preview', 'moonshot-v1-128k-vision-preview'],
                'default_base_url': 'https://api.moonshot.ai/v1',
                'requires_api_key': True
            }
        }
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """获取供应商配置"""
        return self.provider_configs.get(provider, {})
    
    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """获取所有可用供应商"""
        return self.provider_configs
    
    def get_default_ai_params(self) -> Dict[str, Any]:
        """获取默认的AI参数"""
        return ai_config_manager.get_ai_params()
    
    async def chat(self, provider: str, model: str, messages: List[Dict[str, str]], 
                   api_key: str, **kwargs) -> Dict[str, Any]:
        """统一的AI调用接口"""
        if provider not in self.providers:
            raise ValueError(f"Unsupported provider: {provider}")
        
        provider_instance = self.providers[provider]
        return await provider_instance.chat(model, messages, api_key, **kwargs)
    
    async def test_connection(self, provider: str, api_key: str, 
                            base_url: Optional[str] = None) -> bool:
        """测试AI供应商连接"""
        if provider not in self.providers:
            return False
        
        provider_instance = self.providers[provider]
        return await provider_instance.test_connection(api_key, base_url)

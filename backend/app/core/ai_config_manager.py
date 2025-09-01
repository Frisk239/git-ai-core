import json
import os
from typing import Dict, Any, Optional
from app.core.config import settings

class AIConfigManager:
    """AI配置管理器，用于在应用启动时加载配置"""
    
    _instance = None
    config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIConfigManager, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance
    
    def get_config_path(self) -> str:
        """获取配置文件路径"""
        # backend/app/api目录下的AI-Config.json
        current_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(current_dir, 'api', 'AI-Config.json')
    
    def load_config(self) -> None:
        """加载AI配置"""
        config_path = self.get_config_path()
        
        if not os.path.exists(config_path):
            # 使用默认配置
            self.config = {
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 1.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 确保所有参数都有默认值
            self.config = {
                "temperature": config.get("temperature", 0.7),
                "max_tokens": config.get("max_tokens", 2000),
                "top_p": config.get("top_p", 1.0),
                "frequency_penalty": config.get("frequency_penalty", 0.0),
                "presence_penalty": config.get("presence_penalty", 0.0)
            }
            
        except Exception as e:
            print(f"加载AI配置失败: {str(e)}")
            # 使用默认配置
            self.config = {
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 1.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }
    
    def get_ai_params(self) -> Dict[str, Any]:
        """获取AI参数"""
        # 每次获取参数时重新加载配置，确保获取最新配置
        self.load_config()
        return self.config.copy()
    
    def get_temperature(self) -> float:
        """获取温度参数"""
        return self.config.get("temperature", 0.7)
    
    def get_max_tokens(self) -> int:
        """获取最大令牌数"""
        return self.config.get("max_tokens", 2000)
    
    def get_top_p(self) -> float:
        """获取Top-P参数"""
        return self.config.get("top_p", 1.0)
    
    def get_frequency_penalty(self) -> float:
        """获取频率惩罚参数"""
        return self.config.get("frequency_penalty", 0.0)
    
    def get_presence_penalty(self) -> float:
        """获取存在惩罚参数"""
        return self.config.get("presence_penalty", 0.0)

# 全局实例
ai_config_manager = AIConfigManager()

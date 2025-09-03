from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
import os
from pathlib import Path

class Settings(BaseSettings):
    # App settings
    app_name: str = "Git AI Core"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database settings
    database_url: str = "sqlite:///./git_ai_core.db"
    
    # AI Provider settings
    default_provider: str = "openai"
    
    # Git settings
    default_clone_path: str = str(Path.home() / "git-ai-projects")
    
    # MCP settings
    mcp_servers_config_path: str = str(Path(__file__).parent.parent.parent / "mcp_servers.json")
    
    # Security settings
    encryption_key: Optional[str] = None
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Create necessary directories
Path(settings.default_clone_path).mkdir(parents=True, exist_ok=True)
Path(settings.mcp_servers_config_path).parent.mkdir(parents=True, exist_ok=True)

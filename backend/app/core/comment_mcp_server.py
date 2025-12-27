import os
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from app.core.ai_manager import AIManager

class CommentMCPServer:
    """注释生成MCP服务器"""
    
    def __init__(self):
        self.ai_manager = AIManager()
        self.supported_languages = {
            'python': {'extensions': ['.py'], 'comment_prefix': '# '},
            'javascript': {'extensions': ['.js', '.jsx'], 'comment_prefix': '// '},
            'typescript': {'extensions': ['.ts', '.tsx'], 'comment_prefix': '// '},
            'java': {'extensions': ['.java'], 'comment_prefix': '// '},
            'cpp': {'extensions': ['.cpp', '.c', '.h', '.hpp'], 'comment_prefix': '// '},
            'go': {'extensions': ['.go'], 'comment_prefix': '// '},
            'rust': {'extensions': ['.rs'], 'comment_prefix': '// '},
            'php': {'extensions': ['.php'], 'comment_prefix': '// '},
            'ruby': {'extensions': ['.rb'], 'comment_prefix': '# '},
            'shell': {'extensions': ['.sh', '.bash'], 'comment_prefix': '# '},
            'sql': {'extensions': ['.sql'], 'comment_prefix': '-- '},
            'html': {'extensions': ['.html', '.htm'], 'comment_prefix': '<!-- '},
            'css': {'extensions': ['.css', '.scss', '.sass'], 'comment_prefix': '/* '},
        }
    
    def detect_language(self, file_path: str) -> Optional[str]:
        """检测文件编程语言"""
        ext = Path(file_path).suffix.lower()
        for lang, config in self.supported_languages.items():
            if ext in config['extensions']:
                return lang
        return None
    
    async def read_file(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"无法读取文件: {str(e)}")
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """写入文件内容"""
        try:
            # 创建备份文件
            backup_path = f"{file_path}.backup"
            if os.path.exists(file_path):
                os.rename(file_path, backup_path)
            
            # 写入新内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 删除备份文件
            if os.path.exists(backup_path):
                os.remove(backup_path)
                
            return True
        except Exception as e:
            # 恢复备份
            if os.path.exists(backup_path):
                os.rename(backup_path, file_path)
            raise Exception(f"无法写入文件: {str(e)}")
    
    async def generate_comments(self, file_path: str, comment_style: str = "detailed") -> Dict[str, Any]:
        """生成代码注释"""
        try:
            print(f"[DEBUG] 开始生成注释，文件路径: {file_path}")
            
            # 读取文件内容
            content = await self.read_file(file_path)
            print(f"[DEBUG] 文件读取成功，内容长度: {len(content)} 字符")
            
            # 检测编程语言
            language = self.detect_language(file_path)
            if not language:
                raise Exception("不支持的文件类型")
            print(f"[DEBUG] 检测到编程语言: {language}")
            
            # 获取AI配置
            provider = os.getenv('AI_PROVIDER', 'openai')
            model = os.getenv('AI_MODEL', 'gpt-4o')
            api_key = os.getenv('AI_API_KEY', '')
            
            # 检查是否配置了API密钥
            if not api_key:
                # 尝试从项目配置文件获取配置
                try:
                    import json
                    # 配置文件路径：backend目录下的AI-Config.json
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'AI-Config.json')
                    print(f"[DEBUG] 尝试读取配置文件: {config_path}")
                    
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            api_key = config.get('ai_api_key', '')
                            provider = config.get('ai_provider', provider)
                            model = config.get('ai_model', model)
                        print(f"[DEBUG] 配置文件读取成功，provider: {provider}, model: {model}")
                    else:
                        print(f"[DEBUG] 配置文件不存在: {config_path}")
                except Exception as e:
                    print(f"[DEBUG] 读取配置文件失败: {e}")
                    pass
                
                if not api_key:
                    raise Exception("请先配置AI API密钥")
            
            print(f"[DEBUG] 使用AI配置 - Provider: {provider}, Model: {model}")
            
            # 构建AI提示词
            prompt = self._build_prompt(content, language, comment_style)
            print(f"[DEBUG] AI提示词构建完成，长度: {len(prompt)} 字符")
            
            messages = [
                {"role": "system", "content": "你是一个专业的代码文档生成助手，专注于生成高质量的代码注释."},
                {"role": "user", "content": prompt}
            ]
            
            # 调用AI生成注释
            print(f"[DEBUG] 开始调用AI生成注释...")
            response = await self.ai_manager.chat(
                provider=provider,
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=0.3,
                max_tokens=4000
            )
            
            print(f"[DEBUG] AI调用成功，响应长度: {len(response['content'])} 字符")
            
            commented_code = response["content"]
            
            return {
                "success": True,
                "commented_code": commented_code,
                "original_code": content,
                "language": language,
                "file_path": file_path,
                "usage": response.get("usage", {})
            }
            
        except Exception as e:
            print(f"[DEBUG] 生成注释时发生错误: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def _build_prompt(self, code: str, language: str, comment_style: str) -> str:
        """构建AI提示词"""
        style_descriptions = {
            "detailed": "详细注释，包含函数说明、参数说明、返回值说明、示例等",
            "brief": "简洁注释，只包含核心功能说明",
            "documentation": "文档级注释，适合生成API文档"
        }
        
        comment_prefix = self.supported_languages[language]['comment_prefix']
        
        return f"""
你是一个专业的代码文档生成器。请为以下{language}代码生成高质量的注释。

要求：
1. 只返回注释后的完整代码，不要修改原代码逻辑
2. 使用{language}的适当注释风格
3. 注释风格：{style_descriptions[comment_style]}
4. 为函数、类、复杂逻辑添加详细注释
5. 保持注释简洁明了
6. 使用{comment_prefix}作为注释前缀

代码：
{code}

请直接返回注释后的完整代码，不要包含任何额外的解释或说明。
        """.strip()
    
    async def preview_comments(self, file_path: str, comment_style: str = "detailed") -> Dict[str, Any]:
        """预览注释生成效果"""
        try:
            # 读取文件内容
            content = await self.read_file(file_path)
            
            # 检测编程语言
            language = self.detect_language(file_path)
            if not language:
                raise Exception("不支持的文件类型")
            
            # 获取AI配置
            provider = os.getenv('AI_PROVIDER', 'openai')
            model = os.getenv('AI_MODEL', 'gpt-4o')
            api_key = os.getenv('AI_API_KEY', '')
            
            if not api_key:
                raise Exception("请先配置AI API密钥")
            
            # 构建预览提示词（只生成部分注释）
            prompt = self._build_preview_prompt(content, language, comment_style)
            
            messages = [
                {"role": "system", "content": "你是一个专业的代码文档生成助手，专注于生成高质量的代码注释。"},
                {"role": "user", "content": prompt}
            ]
            
            # 调用AI生成预览
            response = await self.ai_manager.chat(
                provider=provider,
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=0.3,
                max_tokens=2000
            )
            
            preview_content = response["content"]
            
            return {
                "success": True,
                "preview": preview_content,
                "language": language,
                "comment_style": comment_style,
                "usage": response.get("usage", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_preview_prompt(self, code: str, language: str, comment_style: str) -> str:
        """构建预览提示词"""
        style_descriptions = {
            "detailed": "详细注释",
            "brief": "简洁注释", 
            "documentation": "文档级注释"
        }
        
        comment_prefix = self.supported_languages[language]['comment_prefix']
        
        return f"""
请为以下{language}代码的前面部分生成{style_descriptions[comment_style]}的预览。

要求：
1. 只生成代码前面约20-30行的注释作为预览
2. 使用{language}的适当注释风格
3. 使用{comment_prefix}作为注释前缀
4. 展示完整的注释风格示例

代码：
{code}

请只返回预览部分的注释代码，不要包含完整的文件内容。
        """.strip()
    
    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """获取支持的编程语言列表"""
        return [
            {
                "name": lang,
                "extensions": config["extensions"],
                "comment_prefix": config["comment_prefix"]
            }
            for lang, config in self.supported_languages.items()
        ]
    
    def get_comment_styles(self) -> List[Dict[str, str]]:
        """获取可用的注释风格"""
        return [
            {"value": "detailed", "label": "详细注释", "description": "包含函数说明、参数说明、返回值说明等"},
            {"value": "brief", "label": "简洁注释", "description": "只包含核心功能说明"},
            {"value": "documentation", "label": "文档注释", "description": "适合生成API文档的详细注释"}
        ]

# 创建全局实例
comment_mcp_server = CommentMCPServer()

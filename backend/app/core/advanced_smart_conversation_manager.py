import asyncio
from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime
from app.core.ai_manager import AIManager
from app.core.mcp_server import McpServer

class IntentRecognizer:
    """意图识别器 - 基于查询内容智能选择文件"""
    
    FILE_TYPE_PATTERNS = {
        'python': ['.py', 'requirements.txt', 'setup.py', 'pyproject.toml'],
        'javascript': ['.js', '.ts', '.jsx', '.tsx', 'package.json'],
        'config': ['.json', '.yaml', '.yml', '.toml', '.ini', '.env'],
        'documentation': ['.md', '.txt', 'README', 'LICENSE', 'CHANGELOG'],
        'build': ['Dockerfile', 'Makefile', 'docker-compose.yml', '.gitignore']
    }
    
    KEYWORD_MAPPINGS = {
        '库': ['requirements.txt', 'package.json', 'pyproject.toml', 'setup.py'],
        '导入': ['.py', '.js', '.ts'],  # 源代码文件
        '依赖': ['requirements.txt', 'package.json', 'pyproject.toml'],
        '配置': ['.env', 'config/', 'settings/', '.json', '.yaml'],
        '文档': ['README.md', 'docs/', '.md'],
        '函数': ['.py', '.js', '.ts'],  # 源代码文件
        '类': ['.py', '.js', '.ts'],   # 源代码文件
        '模块': ['.py', '.js', '.ts'], # 源代码文件
        '包': ['requirements.txt', 'package.json'],
        '安装': ['requirements.txt', 'package.json', 'setup.py'],
        '代码': ['.py', '.js', '.ts', '.java', '.cpp', '.c'],
        '项目': ['README.md', 'package.json', 'pyproject.toml'],
        '架构': ['README.md', 'docs/', 'architecture.md'],
        '测试': ['test/', 'tests/', '.test.', '.spec.']
    }
    
    def __init__(self):
        from app.core.project_mcp_server import project_mcp_server
        self.project_mcp_server = project_mcp_server
    
    def extract_keywords(self, query: str) -> List[str]:
        """提取查询中的关键词"""
        # 移除标点符号
        cleaned_query = re.sub(r'[^\w\s]', ' ', query)
        # 分词并过滤停用词
        words = cleaned_query.split()
        stop_words = {'的', '了', '在', '是', '我', '你', '他', '她', '它', '这', '那', '哪些', '什么', '怎么', '如何'}
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        return keywords
    
    def identify_file_types(self, keywords: List[str]) -> List[str]:
        """根据关键词识别文件类型"""
        file_types = []
        for keyword in keywords:
            for file_type, patterns in self.FILE_TYPE_PATTERNS.items():
                if any(pattern in keyword for pattern in patterns):
                    if file_type not in file_types:
                        file_types.append(file_type)
        return file_types if file_types else ['python', 'javascript', 'config']  # 默认类型
    
    async def get_project_structure(self, project_path: str) -> Dict[str, Any]:
        """获取项目文件结构"""
        try:
            result = await self.project_mcp_server.list_project_files(project_path, max_depth=10)
            
            if result.get("success") and result.get("files"):
                # 将文件列表转换为树形结构
                return self._build_file_tree(result["files"])
            else:
                return {"name": "project", "type": "directory", "children": []}
                
        except Exception as e:
            print(f"获取项目结构失败: {str(e)}")
            return {"name": "project", "type": "directory", "children": []}
    
    def _build_file_tree(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将文件列表构建为树形结构"""
        root = {"name": "project", "type": "directory", "children": []}
        
        for item in files:
            path_parts = item["path"].split('/')
            current_level = root["children"]
            
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # 这是最后一个部分，是文件
                    current_level.append({
                        "name": part,
                        "type": "file",
                        "path": item["path"]
                    })
                else:
                    # 查找或创建目录
                    found_dir = None
                    for child in current_level:
                        if child["type"] == "directory" and child["name"] == part:
                            found_dir = child
                            break
                    
                    if not found_dir:
                        found_dir = {
                            "name": part,
                            "type": "directory",
                            "children": []
                        }
                        current_level.append(found_dir)
                    
                    current_level = found_dir["children"]
        
        return root
    
    def find_files_in_tree(self, tree: Dict[str, Any], patterns: List[str]) -> List[str]:
        """在文件树中查找匹配模式的文件"""
        files = []
        
        if tree.get("type") == "file":
            file_name = tree.get("name", "")
            if any(pattern.lower() in file_name.lower() for pattern in patterns):
                files.append(file_name)
        
        elif tree.get("type") == "directory":
            for child in tree.get("children", []):
                files.extend(self.find_files_in_tree(child, patterns))
        
        return files
    
    def match_files_to_query(self, project_structure: Dict[str, Any], keywords: List[str], file_types: List[str]) -> List[Dict[str, Any]]:
        """匹配查询到具体的文件"""
        suggested_files = []
        
        # 1. 精确文件名匹配（最高优先级）
        for keyword in keywords:
            # 检查是否包含具体的文件名关键词
            file_name_patterns = ['.py', '.js', '.ts', '.json', '.md', '.txt', '.yaml', '.yml']
            if any(pattern in keyword for pattern in file_name_patterns):
                # 尝试直接匹配文件名
                matched_files = self.find_files_in_tree(project_structure, [keyword])
                for file_path in matched_files:
                    suggested_files.append({
                        "file_path": file_path,
                        "reason": f"精确文件名匹配 '{keyword}'",
                        "priority": 20  # 最高优先级
                    })
        
        # 2. 基于关键词的直接匹配
        for keyword in keywords:
            if keyword in self.KEYWORD_MAPPINGS:
                patterns = self.KEYWORD_MAPPINGS[keyword]
                matched_files = self.find_files_in_tree(project_structure, patterns)
                for file_path in matched_files:
                    # 检查是否已经添加过
                    if not any(f["file_path"] == file_path for f in suggested_files):
                        suggested_files.append({
                            "file_path": file_path,
                            "reason": f"关键词 '{keyword}' 匹配",
                            "priority": 15  # 高优先级
                        })
        
        # 3. 基于查询意图的特殊处理
        query_context = " ".join(keywords).lower()
        
        # 如果是关于特定文件的查询
        if any(term in query_context for term in ['ai.py', 'ai文件', 'ai模块']):
            ai_files = self.find_files_in_tree(project_structure, ['ai.py', 'ai_', '_ai'])
            for file_path in ai_files:
                if not any(f["file_path"] == file_path for f in suggested_files):
                    suggested_files.append({
                        "file_path": file_path,
                        "reason": "AI相关文件",
                        "priority": 18  # 较高优先级
                    })
        
        # 如果是关于依赖的查询
        if any(term in query_context for term in ['依赖', '库', 'package', 'requirement']):
            dep_files = self.find_files_in_tree(project_structure, ['requirements.txt', 'package.json', 'pyproject.toml'])
            for file_path in dep_files:
                if not any(f["file_path"] == file_path for f in suggested_files):
                    suggested_files.append({
                        "file_path": file_path,
                        "reason": "依赖配置文件",
                        "priority": 16  # 高优先级
                    })
        
        # 4. 基于文件类型的匹配
        for file_type in file_types:
            patterns = self.FILE_TYPE_PATTERNS[file_type]
            matched_files = self.find_files_in_tree(project_structure, patterns)
            for file_path in matched_files:
                # 避免重复添加
                if not any(f["file_path"] == file_path for f in suggested_files):
                    suggested_files.append({
                        "file_path": file_path,
                        "reason": f"文件类型 '{file_type}' 匹配",
                        "priority": 10  # 中优先级
                    })
        
        # 5. 确保包含常见配置文件（最低优先级）
        common_configs = ['README.md', 'package.json', 'requirements.txt', 'pyproject.toml', 'setup.py']
        for config_file in common_configs:
            config_files = self.find_files_in_tree(project_structure, [config_file])
            for file_path in config_files:
                if not any(f["file_path"] == file_path for f in suggested_files):
                    suggested_files.append({
                        "file_path": file_path,
                        "reason": "常见项目配置文件",
                        "priority": 5  # 低优先级
                    })
        
        return suggested_files
    
    def prioritize_and_deduplicate(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优先级排序和去重"""
        # 去重
        unique_files = {}
        for file_info in files:
            file_path = file_info["file_path"]
            if file_path not in unique_files or file_info["priority"] > unique_files[file_path]["priority"]:
                unique_files[file_path] = file_info
        
        # 按优先级排序
        sorted_files = sorted(unique_files.values(), key=lambda x: x["priority"], reverse=True)
        
        return sorted_files
    
    async def analyze_query(self, project_path: str, query: str) -> List[Dict[str, Any]]:
        """分析查询并返回需要读取的文件列表"""
        print(f"🔍 分析查询: '{query}'")
        
        # 1. 关键词提取和分类
        keywords = self.extract_keywords(query.lower())
        print(f"  提取关键词: {keywords}")
        
        file_types = self.identify_file_types(keywords)
        print(f"  识别文件类型: {file_types}")
        
        # 2. 获取项目结构
        project_structure = await self.get_project_structure(project_path)
        
        # 3. 智能文件匹配
        suggested_files = self.match_files_to_query(project_structure, keywords, file_types)
        print(f"  匹配到 {len(suggested_files)} 个文件")
        
        # 4. 优先级排序和去重
        prioritized_files = self.prioritize_and_deduplicate(suggested_files)
        print(f"  去重后剩余 {len(prioritized_files)} 个文件")
        
        return prioritized_files[:8]  # 返回最多8个文件


class AutoFileReader:
    """自动文件读取器 - 无需用户批准"""
    
    def __init__(self):
        from app.core.project_mcp_server import project_mcp_server
        self.project_mcp_server = project_mcp_server
    
    async def read_files(self, project_path: str, file_requests: List[Dict[str, Any]]) -> Dict[str, str]:
        """自动读取多个文件"""
        file_contents = {}
        
        print(f"📖 开始读取 {len(file_requests)} 个文件...")
        
        for file_request in file_requests:
            file_path = file_request["file_path"]
            reason = file_request.get("reason", "")
            
            try:
                content = await self.read_file(project_path, file_path)
                if content:
                    file_contents[file_path] = content
                    print(f"   ✓ {file_path} - {reason}")
                else:
                    print(f"   ⚠️ {file_path} - 文件为空")
            except Exception as e:
                print(f"   ❌ {file_path} - 读取失败: {str(e)}")
                # 尝试路径修正
                corrected_path = await self.try_correct_path(project_path, file_path)
                if corrected_path:
                    try:
                        content = await self.read_file(project_path, corrected_path)
                        if content:
                            file_contents[corrected_path] = content
                            print(f"   ✓ {corrected_path} - 路径修正后成功读取")
                    except:
                        print(f"   ❌ {corrected_path} - 路径修正后仍然失败")
        
        print(f"✅ 成功读取 {len(file_contents)}/{len(file_requests)} 个文件")
        return file_contents
    
    async def read_file(self, project_path: str, file_path: str) -> Optional[str]:
        """读取单个文件"""
        try:
            result = await self.project_mcp_server.read_project_file(project_path, file_path)
            
            if result.get("success") and result.get("content"):
                return result["content"]
            return None
        except Exception as e:
            print(f"读取文件异常 {file_path}: {str(e)}")
            return None
    
    async def try_correct_path(self, project_path: str, original_path: str) -> Optional[str]:
        """尝试修正文件路径"""
        # 简单的路径修正逻辑
        corrections = [
            original_path,
            original_path.lower(),
            original_path.upper(),
            "./" + original_path,
            original_path.lstrip('./'),
        ]
        
        # 对于常见的配置文件，尝试标准位置
        common_files = {
            'requirements.txt': ['requirements.txt', 'reqs.txt'],
            'package.json': ['package.json', 'package-lock.json'],
            'README.md': ['README.md', 'readme.md', 'Readme.md'],
            'pyproject.toml': ['pyproject.toml'],
            'setup.py': ['setup.py']
        }
        
        if original_path in common_files:
            corrections.extend(common_files[original_path])
        
        # 测试每个修正后的路径
        for corrected_path in corrections:
            if corrected_path == original_path:
                continue
                
            try:
                result = await self.project_mcp_server.read_project_file(project_path, corrected_path)
                if result.get("success") and result.get("content"):
                    return corrected_path
            except:
                continue
        
        return None


class FileContextTracker:
    """文件上下文跟踪器"""
    
    def __init__(self):
        self.read_history = {}  # 文件读取历史
        self.project_context = {}  # 项目上下文信息
    
    def track_file_read(self, file_path: str, content: str):
        """记录文件读取历史"""
        preview = content[:200] + "..." if len(content) > 200 else content
        self.read_history[file_path] = {
            "timestamp": datetime.now().isoformat(),
            "preview": preview,
            "content_length": len(content)
        }
    
    def get_relevant_context(self, current_query: str) -> Dict[str, Any]:
        """获取相关的上下文信息"""
        relevant_files = {}
        keywords = current_query.lower().split()
        
        for file_path, info in self.read_history.items():
            # 简单的关键词匹配
            file_match = any(keyword in file_path.lower() for keyword in keywords)
            content_match = any(keyword in info["preview"].lower() for keyword in keywords)
            
            if file_match or content_match:
                relevant_files[file_path] = info
        
        return relevant_files
    
    def get_read_history(self) -> Dict[str, Any]:
        """获取完整的读取历史"""
        return self.read_history


class AdvancedSmartConversationManager:
    """高级智能对话管理器 - 类Cline架构"""
    
    def __init__(self):
        self.ai_manager = AIManager()
        self.intent_recognizer = IntentRecognizer()
        self.file_reader = AutoFileReader()
        self.file_context_tracker = FileContextTracker()
        self.conversations = {}
    
    def _get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置 - 每次调用都重新读取配置文件"""
        try:
            import json
            import os
            
            # 获取当前文件所在目录
            current_dir = os.path.dirname(__file__)
            
            # 构建正确的配置文件路径（从当前文件位置计算）
            config_paths = [
                os.path.join(current_dir, '..', 'api', 'AI-Config.json'),  # backend/app/api/AI-Config.json
                os.path.join(current_dir, '..', '..', 'api', 'AI-Config.json'),  # backend/api/AI-Config.json
                os.path.join(current_dir, '..', '..', '..', 'AI-Config.json'),   # AI-Config.json
            ]
            
            # 添加绝对路径检查并去重
            abs_config_paths = []
            for path in config_paths:
                abs_path = os.path.abspath(path)
                if abs_path not in abs_config_paths:
                    abs_config_paths.append(abs_path)
            
            # 添加调试信息
            print(f"🔍 查找AI配置文件，检查以下路径:")
            for i, path in enumerate(abs_config_paths, 1):
                exists = os.path.exists(path)
                print(f"  {i}. {path} - {'✅ 存在' if exists else '❌ 不存在'}")
            
            config = None
            config_path = None
            for path in abs_config_paths:
                if os.path.exists(path):
                    config_path = path
                    print(f"📄 读取AI配置文件: {path}")
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        print(f"✅ 成功读取配置文件")
                        break
                    except Exception as e:
                        print(f"❌ 读取配置文件失败 {path}: {str(e)}")
                        continue
            
            if config:
                print(f"🤖 使用AI配置: {config.get('ai_provider', 'unknown')}")
                # 验证必要的配置字段
                api_key = config.get("ai_api_key", "")
                if not api_key:
                    print("⚠️ 警告: AI配置文件中缺少api_key")
                
                return {
                    "provider": config.get("ai_provider", "openai"),
                    "model": config.get("ai_model", "gpt-4o-mini"),
                    "api_key": api_key,
                    "base_url": config.get("ai_base_url")
                }
            
            # 检查环境变量
            print("ℹ️ 未找到AI配置文件，使用环境变量")
            env_api_key = os.getenv("AI_API_KEY", "")
            if not env_api_key:
                print("⚠️ 警告: 环境变量中缺少AI_API_KEY")
            
            return {
                "provider": os.getenv("AI_PROVIDER", "openai"),
                "model": os.getenv("AI_MODEL", "gpt-4o-mini"),
                "api_key": env_api_key,
                "base_url": os.getenv("AI_BASE_URL")
            }
            
        except Exception as e:
            print(f"❌ 读取AI配置失败: {str(e)}")
            return {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "",
                "base_url": None
            }
    
    async def generate_response(self, project_path: str, user_query: str, file_contents: Dict[str, str], context: Dict[str, Any] = None) -> str:
        """基于文件内容生成回答"""
        # 构建文件内容摘要
        file_summary = "\n".join([
            f"文件: {file_path}\n内容:\n{content[:1000]}...\n{'-'*50}"
            for file_path, content in file_contents.items()
        ])
        
        # 添加上下文信息
        context_info = ""
        if context:
            context_info = f"\n相关上下文文件:\n" + "\n".join([
                f"- {file_path} (上次读取: {info['timestamp']})"
                for file_path, info in context.items()
            ]) + "\n"
        
        prompt = f"""你是一个专业的代码分析助手。请基于以下文件内容直接回答用户的问题。

用户问题: {user_query}
项目路径: {project_path}
{context_info}
相关文件内容:
{file_summary}

请直接针对用户的问题提供准确的答案，保持回答简洁、直接、实用。
请使用中文回答，语言自然易懂。"""

        messages = [
            {"role": "system", "content": "你是一个专业的代码分析助手，擅长基于代码文件内容提供深入的项目分析。"},
            {"role": "user", "content": prompt}
        ]
        
        ai_config = self._get_ai_config()
        
        response = await self.ai_manager.chat(
            provider=ai_config["provider"],
            model=ai_config["model"],
            messages=messages,
            api_key=ai_config["api_key"],
            base_url=ai_config.get("base_url"),
            temperature=0.7,
            max_tokens=1500
        )
        
        return response["content"]
    
    async def process_smart_chat(self, conversation_id: str, project_path: str, user_query: str) -> Dict[str, Any]:
        """处理智能对话请求"""
        print(f"\n🤖 === 高级智能分析开始 ===")
        print(f"会话ID: {conversation_id}")
        print(f"项目路径: {project_path}")
        print(f"用户查询: '{user_query}'")
        print("=" * 50)
        
        try:
            # 1. 意图分析和文件选择
            print("🔍 阶段1: 分析查询意图和选择文件...")
            file_requests = await self.intent_recognizer.analyze_query(project_path, user_query)
            
            if not file_requests:
                print("⚠️ 未找到相关文件，使用默认文件列表")
                file_requests = [
                    {"file_path": "README.md", "reason": "默认项目文档", "priority": 1},
                    {"file_path": "package.json", "reason": "默认项目配置", "priority": 1}
                ]
            
            print(f"📁 选择的文件:")
            for i, req in enumerate(file_requests, 1):
                print(f"  {i}. {req['file_path']} - {req.get('reason', '无原因')}")
            
            # 2. 自动文件读取
            print("\n📖 阶段2: 自动读取文件...")
            file_contents = await self.file_reader.read_files(project_path, file_requests)
            
            # 3. 更新上下文
            for file_path, content in file_contents.items():
                self.file_context_tracker.track_file_read(file_path, content)
            
            # 4. 获取相关上下文
            context = self.file_context_tracker.get_relevant_context(user_query)
            
            # 5. 智能回答生成
            print("\n💡 阶段3: 生成智能回答...")
            response_content = await self.generate_response(project_path, user_query, file_contents, context)
            
            # 6. 返回结果
            print("✅ 分析完成")
            
            # 构建工具调用结果
            tool_calls = []
            for req in file_requests:
                file_path = req["file_path"]
                tool_calls.append({
                    "tool_name": "read_project_file",
                    "arguments": {"project_path": project_path, "file_path": file_path},
                    "result": {
                        "success": file_path in file_contents,
                        "content": file_contents.get(file_path, ""),
                        "file_path": file_path  # 确保包含文件路径
                    },
                    "reason": req.get("reason", ""),
                    "file_path": file_path  # 添加文件路径到顶层，便于前端显示
                })
            
            return {
                "response": response_content,
                "tool_calls": tool_calls,
                "conversation_id": conversation_id,
                "analysis_context": {
                    "query": user_query,
                    "selected_files": file_requests,
                    "successful_reads": len(file_contents),
                    "context_files": list(context.keys())
                }
            }
            
        except Exception as e:
            error_msg = f"处理请求时发生错误: {str(e)}"
            print(f"❌ 错误: {error_msg}")
            print("=" * 50)
            return {
                "response": error_msg,
                "tool_calls": [],
                "conversation_id": conversation_id,
                "error": str(e)
            }


# 创建全局实例
advanced_smart_conversation_manager = AdvancedSmartConversationManager()

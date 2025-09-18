from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
from pathlib import Path

router = APIRouter()

class ProjectAnalysisRequest(BaseModel):
    project_path: str = Field(..., description="Project path")
    query: str = Field(..., description="Analysis query")
    provider: str = Field(..., description="AI provider")
    model: str = Field(..., description="AI model")
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(None, description="Base URL for AI provider")

class ProjectSummary(BaseModel):
    project_path: str = Field(..., description="Project path")
    summary_type: str = Field("overview", description="Type of summary to generate")

class GitManager:
    def get_manager(self):
        from app.main import app
        return app.state.git_manager

class AIManager:
    def get_manager(self):
        from app.main import app
        return app.state.ai_manager

@router.get("/")
async def get_all_projects() -> List[Dict[str, Any]]:
    """获取所有项目列表"""
    manager = GitManager().get_manager()
    return manager.list_projects()

@router.get("/{project_path:path}/summary")
async def get_project_summary(project_path: str) -> Dict[str, Any]:
    """获取项目摘要"""
    manager = GitManager().get_manager()
    project = manager.get_project(project_path)
    
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    info = project.get_info()
    file_tree = project.get_file_tree(max_depth=2)
    recent_commits = project.get_recent_commits(5)
    
    return {
        "info": info,
        "file_tree": file_tree,
        "recent_commits": recent_commits,
        "total_files": count_files(file_tree),
        "total_directories": count_directories(file_tree)
    }

@router.post("/{project_path:path}/analyze")
async def analyze_project(request: ProjectAnalysisRequest) -> Dict[str, Any]:
    """使用AI分析项目"""
    git_manager = GitManager().get_manager()
    ai_manager = AIManager().get_manager()
    
    project = git_manager.get_project(request.project_path)
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    # 获取项目基本信息
    info = project.get_info()
    file_tree = project.get_file_tree(max_depth=2)
    
    # 构建分析上下文
    context = f"""
    项目信息:
    - 名称: {info.get('name', 'Unknown')}
    - 路径: {info.get('path', 'Unknown')}
    - 分支: {info.get('current_branch', 'Unknown')}
    - 提交数: {info.get('commits_count', 0)}
    
    文件结构:
    {format_file_tree(file_tree)}
    
    用户查询: {request.query}
    """
    
    messages = [
        {"role": "system", "content": "你是一个专业的代码分析助手。请根据提供的项目信息，回答用户的问题。"},
        {"role": "user", "content": context}
    ]
    
    try:
        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=messages,
            api_key=request.api_key,
            base_url=request.base_url
        )
        
        return {
            "analysis": response["content"],
            "project_info": info,
            "usage": response.get("usage", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

@router.get("/{project_path:path}/structure")
async def get_project_structure(
    project_path: str,
    max_depth: int = Query(3, description="Maximum depth for file tree")
) -> Dict[str, Any]:
    """获取项目结构"""
    manager = GitManager().get_manager()
    project = manager.get_project(project_path)
    
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    return {
        "file_tree": project.get_file_tree(max_depth),
        "branches": project.get_branches(),
        "recent_commits": project.get_recent_commits(10)
    }

@router.get("/{project_path:path}/files")
async def get_project_files(
    project_path: str,
    extension: Optional[str] = Query(None, description="File extension filter")
) -> List[Dict[str, str]]:
    """获取项目文件列表"""
    manager = GitManager().get_manager()
    project = manager.get_project(project_path)
    
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    files = []
    file_tree = project.get_file_tree(max_depth=10)
    collect_files(file_tree, files, extension)
    
    return files

@router.get("/{project_path:path}/search")
async def search_in_project(
    project_path: str,
    query: str = Query(..., description="Search query"),
    file_type: Optional[str] = Query(None, description="File type filter")
) -> List[Dict[str, str]]:
    """在项目中搜索内容"""
    manager = GitManager().get_manager()
    project = manager.get_project(project_path)
    
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    # 这里可以实现实际的搜索逻辑
    # 目前返回模拟结果
    return [
        {"file": "src/main.py", "line": 10, "content": f"Found '{query}' in main.py"},
        {"file": "README.md", "line": 5, "content": f"Found '{query}' in README.md"}
    ]

class ArchitectureAnalysisRequest(BaseModel):
    provider: str = Field(..., description="AI provider")
    model: str = Field(..., description="AI model")
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(None, description="Base URL for AI provider")

@router.post("/{project_path:path}/analyze/architecture")
async def analyze_project_architecture(
    project_path: str,
    request: ArchitectureAnalysisRequest
) -> Dict[str, Any]:
    """分析项目架构并生成可视化文档"""
    git_manager = GitManager().get_manager()
    ai_manager = AIManager().get_manager()
    
    project = git_manager.get_project(project_path)
    if not project or not project.is_valid():
        raise HTTPException(status_code=404, detail="Project not found or invalid")
    
    # 获取项目信息
    info = project.get_info()
    file_tree = project.get_file_tree(max_depth=3)  # 获取更详细的结构
    
    try:
        # 调用AI分析架构
        response = await ai_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=[
                {
                    "role": "system", 
                    "content": "你是一个专业的软件架构师，擅长分析代码架构并生成详细的文档和可视化图表。"
                },
                {
                    "role": "user",
                    "content": f"""
请分析以下项目的架构并生成详细的架构文档：

项目信息：
- 路径: {project_path}
- 名称: {info.get('name', 'Unknown')}
- 分支: {info.get('current_branch', 'Unknown')}
- 提交数: {info.get('commits_count', 0)}

文件结构：
{format_file_tree_for_analysis(file_tree)}

请生成包含以下内容的架构文档：
1. 项目概述和技术栈分析
2. 主要模块和组件说明
3. 依赖关系分析
4. 架构图（使用Mermaid语法）
5. 改进建议

请使用Markdown格式返回，包含清晰的标题和结构。
                    """.strip()
                }
            ],
            api_key=request.api_key,
            base_url=request.base_url,
            temperature=0.7,
            max_tokens=3000
        )
        
        # 保存架构文档到项目目录
        architecture_doc = response["content"]
        doc_path = save_architecture_documentation(project_path, architecture_doc)
        
        return {
            "architecture_doc": architecture_doc,
            "doc_path": doc_path,
            "project_info": info,
            "usage": response.get("usage", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architecture analysis failed: {str(e)}")

# 辅助函数
def count_files(tree: Dict[str, Any]) -> int:
    """统计文件数量"""
    if tree.get("type") == "file":
        return 1
    
    count = 0
    for child in tree.get("children", []):
        count += count_files(child)
    return count

def count_directories(tree: Dict[str, Any]) -> int:
    """统计目录数量"""
    if tree.get("type") == "directory":
        count = 1
        for child in tree.get("children", []):
            count += count_directories(child)
        return count
    return 0

def format_file_tree(tree: Dict[str, Any], indent: int = 0) -> str:
    """格式化文件树为字符串"""
    if tree.get("type") == "file":
        return "  " * indent + f"- {tree['name']}\n"
    
    result = "  " * indent + f"📁 {tree['name']}/\n"
    for child in tree.get("children", []):
        result += format_file_tree(child, indent + 1)
    return result

def collect_files(tree: Dict[str, Any], files: List[Dict[str, str]], 
                  extension: Optional[str] = None, current_path: str = ""):
    """收集文件列表"""
    if tree.get("type") == "file":
        file_path = f"{current_path}/{tree['name']}" if current_path else tree['name']
        if extension is None or tree['name'].endswith(extension):
            files.append({
                "path": file_path,
                "name": tree['name'],
                "size": str(tree.get('size', 0))
            })
    elif tree.get("type") == "directory":
        dir_path = f"{current_path}/{tree['name']}" if current_path else tree['name']
        for child in tree.get("children", []):
            collect_files(child, files, extension, dir_path)

def format_file_tree_for_analysis(tree: Dict[str, Any], indent: int = 0) -> str:
    """格式化文件树为架构分析用的字符串"""
    if tree.get("type") == "file":
        return "  " * indent + f"📄 {tree['name']}\n"
    
    result = "  " * indent + f"📁 {tree['name']}/\n"
    for child in tree.get("children", []):
        result += format_file_tree_for_analysis(child, indent + 1)
    return result

def save_architecture_documentation(project_path: str, content: str) -> str:
    """保存架构文档到项目目录"""
    import os
    from datetime import datetime
    
    # 创建文档目录
    docs_dir = os.path.join(project_path, "git-ai-docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"architecture_analysis_{timestamp}.md"
    file_path = os.path.join(docs_dir, filename)
    
    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path

# 添加项目演化时间线分析路由
@router.post("/{project_path:path}/analyze/evolution-timeline")
async def analyze_project_evolution_timeline(
    project_path: str,
    analysis_depth: str = Query("medium", description="分析深度: light/medium/full")
) -> Dict[str, Any]:
    """生成项目演化时间线分析报告"""

    try:
        from app.core.project_evolution_analyzer import project_evolution_analyzer
        from pathlib import Path

        print(f"📊 开始处理项目演化时间线请求: {project_path}")

        # 检查项目路径是否存在
        if not Path(project_path).exists():
            error_msg = f"项目路径不存在: {project_path}"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)

        # 检查是否是目录
        if not Path(project_path).is_dir():
            error_msg = f"路径不是目录: {project_path}"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # 生成Markdown报告
        print(f"🔍 调用项目演化分析器，深度: {analysis_depth}")
        markdown_content = await project_evolution_analyzer.generate_evolution_timeline_md(
            project_path, analysis_depth
        )

        # 检查是否返回了错误报告
        if markdown_content.startswith("# ❌ 项目演化时间线分析失败"):
            print("❌ 分析器返回了错误报告")
            raise HTTPException(status_code=400, detail="项目演化分析失败，请检查项目是否为有效的Git仓库")

        # 保存文档并返回结果
        print("✅ 项目演化时间线分析完成")
        return {
            "success": True,
            "markdown_content": markdown_content,
            "message": "项目演化时间线分析完成"
        }

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        error_msg = f"演化分析失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

import os
import git
from pathlib import Path
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class GitProject:
    """Git项目封装类"""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.repo = None
        self._load_repo()
    
    def _load_repo(self):
        """加载Git仓库"""
        try:
            self.repo = git.Repo(self.path)
        except git.InvalidGitRepositoryError:
            self.repo = None
    
    def close(self):
        """关闭Git资源，释放文件句柄"""
        if self.repo:
            try:
                # 关闭git命令的管道
                if hasattr(self.repo, 'git') and hasattr(self.repo.git, 'clear_cache'):
                    self.repo.git.clear_cache()
                # 释放repo对象
                self.repo = None
                logger.debug(f"Closed Git resources for: {self.path}")
            except Exception as e:
                logger.warning(f"Error closing Git resources: {e}")
    
    def is_valid(self) -> bool:
        """检查是否为有效的Git仓库"""
        return self.repo is not None
    
    def get_info(self) -> Dict[str, Any]:
        """获取项目基本信息"""
        if not self.is_valid():
            return {}
        
        try:
            return {
                "path": str(self.path),
                "name": self.path.name,
                "remote_url": self.repo.remotes.origin.url if self.repo.remotes else None,
                "current_branch": self.repo.active_branch.name,
                "branches": [branch.name for branch in self.repo.branches],
                "commits_count": len(list(self.repo.iter_commits())),
                "last_commit": {
                    "hash": str(self.repo.head.commit.hexsha),
                    "message": self.repo.head.commit.message.strip(),
                    "author": str(self.repo.head.commit.author),
                    "date": self.repo.head.commit.committed_datetime.isoformat()
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_file_tree(self, max_depth: int = 3) -> Dict[str, Any]:
        """获取项目文件树"""
        if not self.is_valid():
            return {}
        
        def build_tree(path: Path, depth: int = 0) -> Dict[str, Any]:
            if depth >= max_depth:
                return {"type": "directory", "name": path.name}
            
            tree = {"type": "directory", "name": path.name, "children": []}
            
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.') and item.name != '.git':
                        continue
                    
                    if item.is_file():
                        tree["children"].append({
                            "type": "file",
                            "name": item.name,
                            "size": item.stat().st_size,
                            "extension": item.suffix
                        })
                    elif item.is_dir() and item.name != '.git':
                        tree["children"].append(build_tree(item, depth + 1))
            except PermissionError:
                pass
            
            return tree
        
        return build_tree(self.path)
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """获取文件内容"""
        if not self.is_valid():
            return None
        
        full_path = self.path / file_path
        if not full_path.exists() or not full_path.is_file():
            return None
        
        try:
            # 尝试UTF-8编码
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他常见编码
            for encoding in ['utf-8-sig', 'gbk', 'gb2312', 'cp1252', 'latin1']:
                try:
                    with open(full_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            return None
        except (PermissionError, OSError):
            return None
    
    def get_recent_commits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的提交记录"""
        if not self.is_valid():
            return []
        
        commits = []
        try:
            for commit in self.repo.iter_commits(max_count=limit):
                commits.append({
                    "hash": str(commit.hexsha),
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                    "files_changed": list(commit.stats.files.keys())
                })
        except Exception:
            pass
        
        return commits
    
    def get_branches(self) -> List[Dict[str, Any]]:
        """获取所有分支信息"""
        if not self.is_valid():
            return []
        
        branches = []
        try:
            for branch in self.repo.branches:
                branches.append({
                    "name": branch.name,
                    "is_active": branch.name == self.repo.active_branch.name,
                    "commit_hash": str(branch.commit.hexsha),
                    "commit_message": branch.commit.message.strip()
                })
        except Exception:
            pass
        
        return branches
    
    def get_diff(self, commit_hash: str = None) -> Optional[str]:
        """获取代码差异"""
        if not self.is_valid():
            return None
        
        try:
            if commit_hash:
                commit = self.repo.commit(commit_hash)
                return commit.diff(commit.parents[0]) if commit.parents else None
            else:
                # 获取工作区与最新提交的差异
                return self.repo.git.diff()
        except Exception:
            return None

class GitManager:
    """Git管理器"""
    
    def __init__(self):
        self.projects = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def add_project(self, path: str) -> bool:
        """添加项目到管理器"""
        project = GitProject(path)
        if project.is_valid():
            self.projects[str(Path(path).resolve())] = project
            return True
        return False
    
    def remove_project(self, path: str) -> bool:
        """从管理器中移除项目"""
        resolved_path = str(Path(path).resolve())
        if resolved_path in self.projects:
            del self.projects[resolved_path]
            return True
        return False
    
    def get_project(self, path: str) -> Optional[GitProject]:
        """获取项目"""
        resolved_path = str(Path(path).resolve())
        return self.projects.get(resolved_path)
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有项目"""
        projects = []
        for path, project in self.projects.items():
            if project.is_valid():
                projects.append(project.get_info())
        return projects
    
    async def clone_repository(self, url: str, path: Optional[str] = None) -> Dict[str, Any]:
        """克隆Git仓库"""
        try:
            # 提取仓库名称
            repo_name = url.split('/')[-1].replace('.git', '')
            
            if path is None:
                # 使用默认路径
                target_path = Path(settings.default_clone_path) / repo_name
            else:
                # 自定义路径下创建repo_name子目录
                target_path = Path(path).resolve().absolute() / repo_name
            
            logger.debug(f"Cloning to path: {target_path}, exists: {target_path.exists()}")
            
            if target_path.exists() and any(target_path.iterdir()):
                return {"error": "Directory already exists and is not empty"}
            
            # 异步克隆
            loop = asyncio.get_event_loop()
            repo = await loop.run_in_executor(
                self.executor,
                git.Repo.clone_from,
                url,
                str(target_path)
            )
            
            # 添加到管理器
            self.add_project(str(target_path))
            
            # 保存到数据库
            try:
                from app.core.database import SessionLocal
                from app.services.repository_service import RepositoryService
                
                db = SessionLocal()
                repo_service = RepositoryService(db)
                repo_service.add_repository(
                    local_path=str(target_path),
                    remote_url=repo.remotes.origin.url,
                    name=repo_name
                )
                db.close()
            except Exception as db_error:
                logger.warning(f"Failed to save repository to database: {db_error}")
            
            return {
                "success": True,
                "path": str(target_path),
                "remote_url": repo.remotes.origin.url
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def search_projects(self, query: str) -> List[Dict[str, Any]]:
        """搜索项目"""
        results = []
        for path, project in self.projects.items():
            if project.is_valid():
                info = project.get_info()
                if query.lower() in info.get('name', '').lower():
                    results.append(info)
        return results
    
    def get_project_overview(self, path: str) -> Dict[str, Any]:
        """获取项目概览"""
        project = self.get_project(path)
        if not project or not project.is_valid():
            return {"error": "Project not found or invalid"}
        
        return {
            "info": project.get_info(),
            "file_tree": project.get_file_tree(),
            "recent_commits": project.get_recent_commits(5),
            "branches": project.get_branches()
        }

    def load_repositories_from_database(self) -> int:
        """从数据库加载仓库路径"""
        try:
            from app.core.database import SessionLocal
            from app.services.repository_service import RepositoryService
            
            db = SessionLocal()
            repo_service = RepositoryService(db)
            
            # 清理无效路径
            cleaned = repo_service.cleanup_invalid_paths()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} invalid repository paths")
            
            # 加载有效路径
            repositories = repo_service.get_all_repositories()
            loaded_count = 0
            
            for repo in repositories:
                if self.add_project(repo.local_path):
                    loaded_count += 1
                    logger.info(f"Loaded repository from database: {repo.local_path}")
            
            db.close()
            return loaded_count
            
        except Exception as e:
            logger.error(f"Failed to load repositories from database: {e}")
            return 0

    def _is_directory_locked(self, path: Path) -> tuple[bool, str]:
        """检查目录是否被锁定，返回(是否锁定, 锁定原因)"""
        try:
            # 尝试创建一个临时文件来测试写入权限
            test_file = path / ".delete_test"
            test_file.touch()
            test_file.unlink()
            return False, ""
        except PermissionError:
            return True, "没有删除权限"
        except Exception as e:
            return True, f"目录访问错误: {str(e)}"

    async def delete_project(self, path: str) -> Dict[str, Any]:
        """删除项目（数据库记录 + 本地文件）- 增强版"""
        try:
            from app.core.database import SessionLocal
            from app.services.repository_service import RepositoryService
            import gc
            
            logger.info(f"开始删除项目: {path}")
            
            # 规范化路径
            resolved_path = str(Path(path).resolve())
            logger.debug(f"规范化路径: {resolved_path}")
            
            # 检查项目是否存在
            if resolved_path not in self.projects:
                logger.warning(f"项目未找到: {resolved_path}")
                return {"error": "Project not found"}
            
            # 获取项目对象并关闭资源
            project = self.projects[resolved_path]
            if hasattr(project, 'close'):
                project.close()
            logger.debug("已关闭Git资源")
            
            # 从管理器中移除
            del self.projects[resolved_path]
            logger.debug("已从内存管理器中移除")
            
            # 强制垃圾回收，确保文件句柄释放
            gc.collect()
            logger.debug("已执行垃圾回收")
            
            # 从数据库中移除
            db = SessionLocal()
            try:
                repo_service = RepositoryService(db)
                db_removed = repo_service.remove_repository(path)
                if db_removed:
                    logger.info("已从数据库中移除记录")
                else:
                    logger.warning("数据库中未找到记录")
            finally:
                db.close()
            
            # 删除本地文件夹
            project_path = Path(path)
            if not project_path.exists():
                logger.warning(f"本地文件夹不存在: {path}")
                return {
                    "success": True,
                    "message": f"项目记录已删除，但本地文件夹不存在: {path}"
                }
            
            # 检查目录是否被锁定
            is_locked, lock_reason = self._is_directory_locked(project_path)
            if is_locked:
                logger.error(f"目录被锁定: {lock_reason}")
                return {
                    "success": False,
                    "error": f"无法删除文件夹: {lock_reason}",
                    "details": "请确保没有其他程序正在使用该文件夹"
                }
            
            # 尝试删除文件夹
            import shutil
            import time
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"尝试删除文件夹 (尝试 {attempt + 1}/{max_retries}): {project_path}")
                    
                    # 在Windows上，有时需要一点时间让文件句柄释放
                    if os.name == 'nt':
                        time.sleep(0.5)
                    
                    def handle_remove_readonly(func, path, exc):
                        """处理只读文件的删除"""
                        import stat
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    
                    shutil.rmtree(project_path, onerror=handle_remove_readonly)
                    logger.info(f"成功删除本地项目文件夹: {path}")
                    
                    return {
                        "success": True,
                        "message": f"项目 {path} 删除成功"
                    }
                    
                except Exception as e:
                    logger.warning(f"删除尝试 {attempt + 1} 失败: {str(e)}")
                    if attempt == max_retries - 1:
                        # 最后一次尝试失败
                        logger.error(f"最终删除失败: {str(e)}")
                        return {
                            "success": False,
                            "error": f"删除文件夹失败: {str(e)}",
                            "details": "请手动删除文件夹或重启服务后重试",
                            "manual_action_needed": True
                        }
                    else:
                        # 等待后重试
                        time.sleep(1)
            
        except Exception as e:
            logger.error(f"删除项目时发生错误: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "details": "删除过程中发生未知错误"
            }

    async def pull_updates(self, path: str) -> Dict[str, Any]:
        """从远程仓库拉取最新更新"""
        try:
            resolved_path = str(Path(path).resolve())
            project = self.get_project(path)
            
            if not project or not project.is_valid():
                return {"error": "Project not found or invalid"}
            
            # 执行git pull
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                project.repo.remotes.origin.pull
            )
            
            if result and len(result) > 0:
                pull_info = result[0]
                return {
                    "success": True,
                    "message": "Updates pulled successfully",
                    "commits": len(pull_info.commit),
                    "files_changed": len(pull_info.commit.diff('HEAD~1')) if pull_info.commit.parents else 0
                }
            else:
                return {
                    "success": True,
                    "message": "Already up to date"
                }
                
        except Exception as e:
            logger.error(f"Failed to pull updates: {e}")
            return {"error": str(e)}

    def get_project_status(self, path: str) -> Dict[str, Any]:
        """获取项目状态（是否有更新等）"""
        try:
            project = self.get_project(path)
            if not project or not project.is_valid():
                return {"error": "Project not found or invalid"}
            
            repo = project.repo
            
            # 检查是否有更新
            origin = repo.remotes.origin
            origin.fetch()
            
            local_commit = repo.head.commit
            remote_commit = origin.refs[repo.active_branch.name].commit
            
            has_updates = local_commit.hexsha != remote_commit.hexsha
            
            # 检查工作区状态
            is_clean = not repo.is_dirty()
            
            return {
                "has_updates": has_updates,
                "is_clean": is_clean,
                "local_commit": str(local_commit.hexsha)[:8],
                "remote_commit": str(remote_commit.hexsha)[:8],
                "local_date": local_commit.committed_datetime.isoformat(),
                "remote_date": remote_commit.committed_datetime.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get project status: {e}")
            return {"error": str(e)}

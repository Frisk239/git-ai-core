"""
Git 相关工具处理器
"""

from typing import Dict, Any
import logging

from ..base import ToolSpec, ToolParameter, ToolContext, ToolResult
from ..handler import BaseToolHandler

logger = logging.getLogger(__name__)


class GitDiffToolHandler(BaseToolHandler):
    """Git Diff 工具处理器"""

    @property
    def name(self) -> str:
        return "git_diff"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="git_diff",
            description="查看 Git 工作区或暂存区的变更差异",
            category="git",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要查看差异的文件路径（可选，空字符串表示所有变更）",
                    required=False,
                    default=""
                ),
                "staged": ToolParameter(
                    name="staged",
                    type="boolean",
                    description="是否查看已暂存的变更（默认查看工作区变更）",
                    required=False,
                    default=False
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行 Git Diff"""
        # 这里需要使用 GitManager
        from app.core.git_manager import GitProject

        file_path = parameters.get("file_path", "")
        staged = parameters.get("staged", False)
        repo_path = context.repository_path

        try:
            git_project = GitProject(repo_path)

            if file_path:
                # 获取单个文件的 diff
                diff_output = git_project.get_diff(
                    file_path=file_path,
                    staged=staged
                )
            else:
                # 获取所有变更的 diff
                diff_output = git_project.get_diff(
                    file_path=None,
                    staged=staged
                )

            return {
                "file_path": file_path or "(所有文件)",
                "staged": staged,
                "diff": diff_output,
                "repo_path": repo_path
            }

        except Exception as e:
            logger.error(f"Git diff 执行失败: {e}")
            raise


class GitLogToolHandler(BaseToolHandler):
    """Git Log 工具处理器"""

    @property
    def name(self) -> str:
        return "git_log"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="git_log",
            description="查看 Git 提交历史",
            category="git",
            parameters={
                "limit": ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回的提交数量限制",
                    required=False,
                    default=10
                ),
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="指定文件的提交历史（可选）",
                    required=False,
                    default=""
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行 Git Log"""
        from app.core.git_manager import GitProject

        limit = parameters.get("limit", 10)
        file_path = parameters.get("file_path", "")
        repo_path = context.repository_path

        try:
            git_project = GitProject(repo_path)

            if file_path:
                # 获取单个文件的日志
                commits = git_project.get_file_log(
                    file_path=file_path,
                    limit=limit
                )
            else:
                # 获取所有提交历史
                commits = git_project.get_recent_commits(limit=limit)

            return {
                "file_path": file_path or "(所有文件)",
                "limit": limit,
                "commits": commits,
                "total_count": len(commits)
            }

        except Exception as e:
            logger.error(f"Git log 执行失败: {e}")
            raise


class GitStatusToolHandler(BaseToolHandler):
    """Git Status 工具处理器"""

    @property
    def name(self) -> str:
        return "git_status"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="git_status",
            description="查看 Git 工作区状态",
            category="git",
            parameters={}
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行 Git Status"""
        from app.core.git_manager import GitProject

        repo_path = context.repository_path

        try:
            git_project = GitProject(repo_path)
            status = git_project.get_status()

            return {
                "repo_path": repo_path,
                "status": status
            }

        except Exception as e:
            logger.error(f"Git status 执行失败: {e}")
            raise


class GitBranchToolHandler(BaseToolHandler):
    """Git Branch 工具处理器"""

    @property
    def name(self) -> str:
        return "git_branch"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="git_branch",
            description="列出或切换 Git 分支",
            category="git",
            parameters={
                "action": ToolParameter(
                    name="action",
                    type="string",
                    description="操作类型: list（列出分支）, current（当前分支）, create（创建分支）, switch（切换分支）",
                    required=False,
                    default="list"
                ),
                "branch_name": ToolParameter(
                    name="branch_name",
                    type="string",
                    description="分支名称（create 或 switch 时需要）",
                    required=False,
                    default=""
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行 Git Branch 操作"""
        from app.core.git_manager import GitProject

        action = parameters.get("action", "list")
        branch_name = parameters.get("branch_name", "")
        repo_path = context.repository_path

        try:
            git_project = GitProject(repo_path)

            if action == "list":
                branches = git_project.list_branches()
                return {
                    "action": action,
                    "branches": branches
                }

            elif action == "current":
                current = git_project.get_current_branch()
                return {
                    "action": action,
                    "current_branch": current
                }

            elif action == "create":
                if not branch_name:
                    raise ValueError("创建分支需要提供 branch_name")
                git_project.create_branch(branch_name)
                return {
                    "action": action,
                    "branch_name": branch_name,
                    "message": f"分支 {branch_name} 创建成功"
                }

            elif action == "switch":
                if not branch_name:
                    raise ValueError("切换分支需要提供 branch_name")
                git_project.switch_branch(branch_name)
                return {
                    "action": action,
                    "branch_name": branch_name,
                    "message": f"已切换到分支 {branch_name}"
                }

            else:
                raise ValueError(f"未知操作: {action}")

        except Exception as e:
            logger.error(f"Git branch 执行失败: {e}")
            raise

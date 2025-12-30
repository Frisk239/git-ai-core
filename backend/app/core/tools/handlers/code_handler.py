"""
代码分析工具处理器
借鉴 Cline 的 list_code_definition_names 工具
"""

import os
import re
from typing import Dict, Any, List
import logging

from ..base import ToolSpec, ToolParameter, ToolContext
from ..handler import BaseToolHandler


logger = logging.getLogger(__name__)


class ListCodeDefinitionsToolHandler(BaseToolHandler):
    """列出代码定义名称工具处理器"""

    @property
    def name(self) -> str:
        return "list_code_definitions"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_code_definitions",
            description="列出文件中的代码定义（类、函数、方法等）",
            category="analysis",
            parameters={
                "file_path": ToolParameter(
                    name="file_path",
                    type="string",
                    description="要分析的文件路径（相对于仓库根目录）",
                    required=True
                )
            }
        )

    async def execute(self, parameters: Any, context: ToolContext) -> Any:
        """执行代码定义提取"""
        file_path = parameters["file_path"]
        repo_path = context.repository_path

        # 构建完整文件路径
        full_path = os.path.join(repo_path, file_path)

        # 安全检查
        if not os.path.abspath(full_path).startswith(os.path.abspath(repo_path)):
            raise ValueError(f"非法文件路径: {file_path}")

        if not os.path.exists(full_path):
            raise ValueError(f"文件不存在: {file_path}")

        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)

        # 根据语言选择解析器
        definitions = self._extract_definitions(full_path, ext)

        return {
            "file_path": file_path,
            "language": self._get_language(ext),
            "definitions": definitions,
            "total_count": len(definitions)
        }

    def _get_language(self, ext: str) -> str:
        """根据扩展名获取语言"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala'
        }
        return language_map.get(ext.lower(), 'unknown')

    def _extract_definitions(self, file_path: str, ext: str) -> List[Dict[str, Any]]:
        """提取代码定义"""
        # 读取文件内容
        content = None
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return []

        # 根据语言选择提取方法
        ext_lower = ext.lower()

        if ext_lower == '.py':
            return self._extract_python_definitions(content)
        elif ext_lower in ['.js', '.ts', '.jsx', '.tsx']:
            return self._extract_javascript_definitions(content)
        elif ext_lower in ['.java', '.c', '.cpp', '.cc', '.h', '.hpp']:
            return self._extract_c_style_definitions(content)
        elif ext_lower == '.go':
            return self._extract_go_definitions(content)
        else:
            # 通用方法：尝试匹配常见模式
            return self._extract_generic_definitions(content)

    def _extract_python_definitions(self, content: str) -> List[Dict[str, Any]]:
        """提取 Python 代码定义"""
        definitions = []
        lines = content.split('\n')

        # Python 定义模式
        class_pattern = re.compile(r'^\s*(class)\s+(\w+)(?:\s*\([^)]*\))?:')
        function_pattern = re.compile(r'^\s*(def)\s+(\w+)\s*\([^)]*\):')
        decorator_pattern = re.compile(r'^@\w+')

        indent_stack = [0]  # 缩进栈，用于判断顶级定义
        current_decorators = []

        for line_num, line in enumerate(lines, 1):
            # 检查装饰器
            decorator_match = decorator_pattern.match(line)
            if decorator_match:
                current_decorators.append(line.strip())
                continue

            # 检查类定义
            class_match = class_pattern.match(line)
            if class_match:
                indent = len(line) - len(line.lstrip())

                # 只收集顶级定义（缩进为 0 或最小）
                if indent == 0:
                    definitions.append({
                        "type": "class",
                        "name": class_match.group(2),
                        "line": line_num,
                        "decorators": current_decorators.copy()
                    })

                current_decorators.clear()
                continue

            # 检查函数定义
            function_match = function_pattern.match(line)
            if function_match:
                indent = len(line) - len(line.lstrip())

                # 只收集顶级定义和类方法（缩进为 0 或 4/8）
                if indent == 0 or indent in [4, 8]:
                    def_type = "method" if indent > 0 else "function"
                    definitions.append({
                        "type": def_type,
                        "name": function_match.group(2),
                        "line": line_num,
                        "decorators": current_decorators.copy()
                    })

                current_decorators.clear()

        return definitions

    def _extract_javascript_definitions(self, content: str) -> List[Dict[str, Any]]:
        """提取 JavaScript/TypeScript 代码定义"""
        definitions = []
        lines = content.split('\n')

        # JS/TS 定义模式
        patterns = [
            # class MyClass
            re.compile(r'^\s*(class)\s+(\w+)'),
            # function myFunction() 或 const myFunction = () => {
            re.compile(r'^\s*(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>)'),
            # export function/method
            re.compile(r'^\s*export\s+(?:function|const|class)\s+(\w+)'),
            # myMethod() {  或  async myMethod() {
            re.compile(r'^\s*(async\s+)?(\w+)\s*\([^)]*\)\s*\{'),
        ]

        for line_num, line in lines:
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    name = match.group(2) if match.group(2) else match.group(1)
                    if name and not name.startswith('_'):  # 跳过私有成员
                        definitions.append({
                            "type": "function",
                            "name": name,
                            "line": line_num
                        })
                    break

        return definitions

    def _extract_c_style_definitions(self, content: str) -> List[Dict[str, Any]]:
        """提取 C/C++/Java 代码定义"""
        definitions = []
        lines = content.split('\n')

        # C 风格定义模式
        patterns = [
            # class MyClass
            re.compile(r'^\s*(class|struct|interface)\s+(\w+)'),
            # public/private/protected static void myMethod()
            re.compile(r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*\{?'),
            # void myFunction()
            re.compile(r'^\s*\w+\s+(\w+)\s*\([^)]*\)\s*\{?'),
        ]

        for line_num, line in lines:
            # 跳过注释和预处理器指令
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            if stripped.startswith('#'):
                continue

            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    def_type = match.group(1)
                    name = match.group(2)

                    if def_type in ['class', 'struct', 'interface']:
                        definitions.append({
                            "type": def_type,
                            "name": name,
                            "line": line_num
                        })
                    elif name and not name.startswith('~'):  # 跳过析构函数
                        definitions.append({
                            "type": "function",
                            "name": name,
                            "line": line_num
                        })
                    break

        return definitions

    def _extract_go_definitions(self, content: str) -> List[Dict[str, Any]]:
        """提取 Go 代码定义"""
        definitions = []
        lines = content.split('\n')

        # Go 定义模式
        patterns = [
            # type MyStruct struct
            re.compile(r'^\s*type\s+(\w+)\s+(struct|interface)'),
            # func myFunction() 或 func (r *Receiver) myMethod()
            re.compile(r'^\s*func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('),
        ]

        for line_num, line in lines:
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    def_type = match.group(2) if match.group(2) else "function"
                    name = match.group(1)

                    if not name.startswith('_'):  # 跳过私有
                        definitions.append({
                            "type": def_type,
                            "name": name,
                            "line": line_num
                        })
                    break

        return definitions

    def _extract_generic_definitions(self, content: str) -> List[Dict[str, Any]]:
        """通用代码定义提取（使用简单模式）"""
        definitions = []
        lines = content.split('\n')

        # 通用模式
        keywords = ['class', 'function', 'def', 'func', 'interface', 'struct']
        keyword_pattern = re.compile(r'\b(' + '|'.join(keywords) + r')\s+(\w+)')

        for line_num, line in lines:
            # 跳过注释行
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('#') or stripped.startswith('/*'):
                continue

            match = keyword_pattern.search(line)
            if match:
                def_type = match.group(1)
                name = match.group(2)

                if name:
                    definitions.append({
                        "type": def_type,
                        "name": name,
                        "line": line_num
                    })

        return definitions

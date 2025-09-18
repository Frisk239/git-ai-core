import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics
from collections import defaultdict
import re
import json
from pathlib import Path
from app.core.ai_manager import AIManager
from app.core.git_manager import GitProject
from app.core.chart_generator import chart_generator

class ProjectEvolutionAnalyzer:
    """项目演化时间线分析器 - 带数据可视化"""

    def __init__(self):
        self.ai_manager = AIManager()

    def _load_ai_config(self) -> Dict[str, Any]:
        """动态加载AI配置文件 - 每次调用都重新读取"""
        try:
            # 直接读取AI配置文件 - 从backend目录开始查找
            config_path = Path(__file__).parent.parent.parent / "AI-Config.json"

            if not config_path.exists():
                print(f"⚠️ AI配置文件不存在: {config_path}")
                return self._get_default_ai_config()

            with open(config_path, 'r', encoding='utf-8') as f:
                ai_config = json.load(f)

            # 验证必要的配置字段
            required_fields = ["ai_provider", "ai_model", "ai_api_key"]
            missing_fields = [field for field in required_fields if not ai_config.get(field)]

            if missing_fields:
                print(f"⚠️ AI配置缺少必要字段: {missing_fields}")
                return self._get_default_ai_config()

            print(f"✅ 成功加载AI配置: {ai_config['ai_provider']} - {ai_config['ai_model']}")
            return ai_config

        except json.JSONDecodeError as e:
            print(f"❌ AI配置文件JSON格式错误: {e}")
            return self._get_default_ai_config()
        except Exception as e:
            print(f"❌ 读取AI配置失败: {e}")
            return self._get_default_ai_config()

    def _get_default_ai_config(self) -> Dict[str, Any]:
        """获取默认AI配置"""
        return {
            "ai_provider": "openai",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
            "ai_base_url": None,
            "temperature": 0.7,
            "max_tokens": 2000
        }

    async def generate_evolution_timeline_md(self, project_path: str,
                                           analysis_depth: str = "medium") -> str:
        """生成带有图片嵌入的项目演化时间线Markdown文档"""

        print(f"🔍 开始分析项目演化历史... 项目路径: {project_path}")

        # 1. 获取项目基本信息 - 使用GitManager而不是直接创建
        from app.core.git_manager import GitManager
        git_manager = GitManager()
        project = git_manager.get_project(project_path)

        if not project:
            error_msg = f"项目未找到: {project_path}"
            print(f"❌ {error_msg}")
            return self._generate_error_report(error_msg)

        if not project.is_valid():
            error_msg = f"无效的Git仓库: {project_path}"
            print(f"❌ {error_msg}")
            # 检查路径是否存在
            from pathlib import Path
            if not Path(project_path).exists():
                error_msg += f" (路径不存在)"
            else:
                error_msg += f" (路径存在但不是Git仓库)"
            return self._generate_error_report(error_msg)

        project_info = project.get_info()

        # 2. 获取提交历史
        commits = await self._get_commit_history(project, analysis_depth)
        if not commits:
            return self._generate_error_report("无法获取提交历史")

        # 3. 分析时间线数据
        timeline_data = await self._analyze_timeline_data(commits)

        # 4. 分析贡献者数据
        contributor_data = await self._analyze_contributor_activity(commits)

        # 5. 生成AI洞察
        ai_insights = await self._generate_ai_insights(timeline_data, contributor_data)

        # 6. 生成完整Markdown文档（纯文本版本）
        markdown_content = self._generate_text_markdown_report(
            project_info, timeline_data, contributor_data, ai_insights, len(commits)
        )

        # 8. 保存文档
        doc_path = self._save_evolution_document(project_path, markdown_content)

        return markdown_content

    def _generate_error_report(self, error_msg: str) -> str:
        """生成错误报告"""
        return f"""# ❌ 项目演化时间线分析失败

## 错误信息
{error_msg}

## 可能的原因
- 项目不是有效的Git仓库
- 没有提交历史
- 文件权限问题

---
*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    async def _get_commit_history(self, project: GitProject, depth: str) -> List[Dict[str, Any]]:
        """获取提交历史"""
        max_commits = {"light": 100, "medium": 500, "full": 2000}.get(depth, 500)

        commits = []
        try:
            for commit in project.repo.iter_commits(max_count=max_commits):
                commit_data = {
                    "hash": str(commit.hexsha),
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "email": commit.author.email,
                    "date": commit.committed_datetime.isoformat(),
                    "stats": {"insertions": 0, "deletions": 0, "lines": 0},
                    "files_changed": []
                }

                # 获取统计信息
                if hasattr(commit, 'stats') and commit.stats.total:
                    commit_data["stats"] = {
                        "insertions": commit.stats.total.get("insertions", 0),
                        "deletions": commit.stats.total.get("deletions", 0),
                        "lines": commit.stats.total.get("lines", 0)
                    }
                    commit_data["files_changed"] = list(commit.stats.files.keys())

                commits.append(commit_data)

        except Exception as e:
            print(f"获取提交历史失败: {e}")

        return commits

    async def _analyze_timeline_data(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析时间线数据"""

        # 按月份分组
        monthly_stats = defaultdict(lambda: {
            "commits": 0, "insertions": 0, "deletions": 0,
            "authors": set(), "file_types": defaultdict(int)
        })

        for commit in commits:
            date = datetime.fromisoformat(commit["date"])
            month_key = f"{date.year}-{date.month:02d}"

            monthly_stats[month_key]["commits"] += 1
            monthly_stats[month_key]["insertions"] += commit["stats"].get("insertions", 0)
            monthly_stats[month_key]["deletions"] += commit["stats"].get("deletions", 0)
            monthly_stats[month_key]["authors"].add(commit["author"])

            # 统计文件类型
            for file_path in commit["files_changed"]:
                ext = file_path.split('.')[-1] if '.' in file_path else 'other'
                monthly_stats[month_key]["file_types"][ext] += 1

        # 转换为列表格式
        timeline = []
        for month, stats in sorted(monthly_stats.items()):
            timeline.append({
                "month": month,
                "commits": stats["commits"],
                "lines_changed": stats["insertions"] + stats["deletions"],
                "active_contributors": len(stats["authors"]),
                "file_types": dict(stats["file_types"])
            })

        return {
            "timeline": timeline,
            "total_months": len(timeline),
            "avg_commits_per_month": round(statistics.mean([m["commits"] for m in timeline]), 1) if timeline else 0,
            "most_active_month": max(timeline, key=lambda x: x["commits"]) if timeline else None,
            "total_lines_changed": sum([m["lines_changed"] for m in timeline])
        }

    async def _analyze_contributor_activity(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析贡献者活跃度"""

        contributor_stats = defaultdict(lambda: {
            "total_commits": 0,
            "first_commit": None,
            "last_commit": None,
            "lines_changed": 0,
            "file_types": defaultdict(int),
            "monthly_activity": defaultdict(int)
        })

        for commit in commits:
            author = commit["author"]
            date = datetime.fromisoformat(commit["date"])
            month_key = f"{date.year}-{date.month:02d}"

            contributor_stats[author]["total_commits"] += 1
            contributor_stats[author]["lines_changed"] += (
                commit["stats"].get("insertions", 0) + commit["stats"].get("deletions", 0)
            )
            contributor_stats[author]["monthly_activity"][month_key] += 1

            # 更新时间范围
            if contributor_stats[author]["first_commit"] is None:
                contributor_stats[author]["first_commit"] = commit["date"]
            contributor_stats[author]["last_commit"] = commit["date"]

            # 统计文件类型偏好
            for file_path in commit["files_changed"]:
                ext = file_path.split('.')[-1] if '.' in file_path else 'other'
                contributor_stats[author]["file_types"][ext] += 1

        # 排序贡献者
        top_contributors = sorted(
            contributor_stats.items(),
            key=lambda x: x[1]["lines_changed"],
            reverse=True
        )[:10]

        return {
            "contributor_stats": dict(contributor_stats),
            "top_contributors": top_contributors,
            "total_contributors": len(contributor_stats)
        }

    async def _generate_image_charts(self, timeline_data: Dict[str, Any],
                                   contributor_data: Dict[str, Any],
                                   project_path: str) -> Dict[str, str]:
        """生成图片图表并返回图片路径"""

        # 设置assets目录
        chart_generator.setup_assets_dir(project_path)

        # 生成所有图表
        return chart_generator.generate_all_charts(timeline_data, contributor_data)

    async def _generate_ai_insights(self, timeline_data: Dict[str, Any],
                                  contributor_data: Dict[str, Any]) -> str:
        """生成AI洞察分析 - 动态读取配置"""

        # 构建AI分析提示词
        prompt = f"""
基于以下项目数据，提供项目演化趋势的专业分析：

📊 时间线数据:
- 总月份数: {timeline_data['total_months']}
- 月均提交数: {timeline_data['avg_commits_per_month']}
- 最活跃月份: {timeline_data['most_active_month']['month'] if timeline_data['most_active_month'] else '无'}
- 总代码变更: {timeline_data['total_lines_changed']:,} 行

👥 贡献者数据:
- 总贡献者数: {contributor_data['total_contributors']}
- Top贡献者: {', '.join([f"{name}({stats['total_commits']}次)" for name, stats in contributor_data['top_contributors'][:3]])}

请从以下方面进行深度分析：
1. 项目发展阶段评估（萌芽期/成长期/成熟期/维护期）
2. 团队协作模式分析
3. 技术栈演化趋势
4. 项目健康度评估
5. 未来发展建议

请用专业、数据驱动的语言进行分析，包含具体的指标和趋势判断。
"""

        try:
            # 🔄 每次调用都重新读取AI配置
            ai_config = self._load_ai_config()

            print(f"🤖 使用AI配置: {ai_config['ai_provider']} - {ai_config['ai_model']}")

            # 使用类中已初始化的AI管理器实例
            response = await self.ai_manager.chat(
                provider=ai_config["ai_provider"],
                model=ai_config["ai_model"],
                messages=[
                    {"role": "system", "content": "你是一位资深的项目分析师，擅长从Git历史数据中提取洞察并预测发展趋势。请用专业、数据驱动的方式进行分析。"},
                    {"role": "user", "content": prompt}
                ],
                api_key=ai_config["ai_api_key"],
                base_url=ai_config.get("ai_base_url"),
                temperature=ai_config.get("temperature", 0.7),
                max_tokens=ai_config.get("max_tokens", 1500)
            )

            print("✅ AI洞察分析完成")
            return response["content"]

        except Exception as e:
            error_msg = f"AI分析暂时不可用: {str(e)}"
            print(f"❌ AI洞察分析失败: {e}")
            return error_msg

    def _generate_visual_markdown_report(self, project_info: Dict[str, Any],
                                       timeline_data: Dict[str, Any],
                                       contributor_data: Dict[str, Any],
                                       charts: Dict[str, str],
                                       ai_insights: str,
                                       total_commits: int) -> str:
        """生成带有图片嵌入的Markdown报告"""

        # 获取当前AI配置信息用于报告显示
        ai_config = self._load_ai_config()

        report = f"""# 📊 项目演化时间线分析报告

## 📋 项目概览

- **项目名称**: {project_info.get('name', 'Unknown')}
- **Git仓库**: {project_info.get('remote_url', '本地仓库')}
- **当前分支**: {project_info.get('current_branch', 'main')}
- **总提交数**: {total_commits:,}
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📈 时间线统计

### 月度活跃度概览

| 月份 | 提交数 | 代码变更 | 活跃贡献者 |
|------|--------|----------|------------|
"""

        # 添加时间线表格（最近12个月）
        for item in timeline_data["timeline"][-12:]:
            report += f"| {item['month']} | {item['commits']} | {item['lines_changed']:,} | {item['active_contributors']} |\n"

        report += f"""

### 📊 关键指标

- 📅 **活跃月份**: {timeline_data['total_months']} 个月
- 🚀 **月均提交**: {timeline_data['avg_commits_per_month']} 次/月
- 👥 **贡献者总数**: {contributor_data['total_contributors']} 人
- 🏆 **最活跃月份**: {timeline_data['most_active_month']['month'] if timeline_data['most_active_month'] else '无数据'}
- 📝 **总代码变更**: {timeline_data['total_lines_changed']:,} 行

---

## 📊 数据可视化图表

### 提交活跃度时间线
![提交活跃度时间线]({charts['commit_timeline']})

### 贡献者活跃度排名
![贡献者活跃度排名]({charts['contributor_chart']})

### 文件类型分布
![文件类型分布]({charts['file_type_chart']})

### 月度活跃度热力图
![月度活跃度热力图]({charts['activity_heatmap']})

---

## 👥 贡献者深度分析

### Top 10 贡献者详细数据

| 排名 | 贡献者 | 提交数 | 代码变更 | 主要文件类型 | 贡献时长 |
|------|--------|--------|----------|--------------|----------|
"""

        # 添加贡献者详细表格
        for i, (name, stats) in enumerate(contributor_data['top_contributors'][:10], 1):
            top_file_type = max(stats['file_types'].items(), key=lambda x: x[1]) if stats['file_types'] else ('无', 0)

            # 计算贡献时长
            if stats['first_commit'] and stats['last_commit']:
                first_date = datetime.fromisoformat(stats['first_commit'])
                last_date = datetime.fromisoformat(stats['last_commit'])
                duration_days = (last_date - first_date).days
                duration_str = f"{duration_days}天" if duration_days > 0 else "单次"
            else:
                duration_str = "未知"

            report += f"| {i} | {name} | {stats['total_commits']} | {stats['lines_changed']:,} | {top_file_type[0]} | {duration_str} |\n"

        report += f"""

---

## 🔍 AI智能洞察分析

{ai_insights}

---

## 📋 技术栈演化趋势

### 文件类型变更统计

"""

        # 统计文件类型分布
        file_type_totals = defaultdict(int)
        for item in timeline_data["timeline"]:
            for ext, count in item["file_types"].items():
                file_type_totals[ext] += count

        # 生成文件类型统计
        for ext, count in sorted(file_type_totals.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / sum(file_type_totals.values())) * 100
            report += f"- **{ext}**: {count:,} 次变更 ({percentage:.1f}%)\n"

        report += f"""

---

## 🎯 项目健康度评估

### 健康度雷达图
![项目健康度雷达图]({charts['health_radar']})

### 健康度评分详情
"""

        # 计算各项评分
        activity_score = chart_generator._calculate_activity_score(timeline_data)
        diversity_score = chart_generator._calculate_diversity_score(contributor_data)
        maturity_score = chart_generator._calculate_maturity_score(timeline_data, total_commits)

        report += f"""
- **活跃度评分**: {activity_score}/100
- **贡献者多样性**: {diversity_score}/100
- **项目成熟度**: {maturity_score}/100

---

*📊 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*🔍 分析提交数: {total_commits:,}*
*📈 分析深度: 最近{timeline_data['total_months']}个月*
*🤖 AI分析提供商: {ai_config.get('ai_provider', 'Unknown')} ({ai_config.get('ai_model', 'Unknown')})*

---

"""

        return report

    def _generate_text_markdown_report(self, project_info: Dict[str, Any],
                                      timeline_data: Dict[str, Any],
                                      contributor_data: Dict[str, Any],
                                      ai_insights: str,
                                      total_commits: int) -> str:
        """生成纯文本Markdown报告（不包含图片）"""

        # 获取当前AI配置信息用于报告显示
        ai_config = self._load_ai_config()

        report = f"""# 📊 项目演化时间线分析报告

## 📋 项目概览

- **项目名称**: {project_info.get('name', 'Unknown')}
- **Git仓库**: {project_info.get('remote_url', '本地仓库')}
- **当前分支**: {project_info.get('current_branch', 'main')}
- **总提交数**: {total_commits:,}
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📈 时间线统计

### 月度活跃度概览

| 月份 | 提交数 | 代码变更 | 活跃贡献者 |
|------|--------|----------|------------|
"""

        # 添加时间线表格（最近12个月）
        for item in timeline_data["timeline"][-12:]:
            report += f"| {item['month']} | {item['commits']} | {item['lines_changed']:,} | {item['active_contributors']} |\n"

        report += f"""

### 📊 关键指标

- 📅 **活跃月份**: {timeline_data['total_months']} 个月
- 🚀 **月均提交**: {timeline_data['avg_commits_per_month']} 次/月
- 👥 **贡献者总数**: {contributor_data['total_contributors']} 人
- 🏆 **最活跃月份**: {timeline_data['most_active_month']['month'] if timeline_data['most_active_month'] else '无数据'}
- 📝 **总代码变更**: {timeline_data['total_lines_changed']:,} 行

---

## 📊 数据可视化（文本形式）

### 提交活跃度时间线
```
"""

        # 生成简单的文本图表
        max_commits = max([item['commits'] for item in timeline_data["timeline"]], default=0)
        for item in timeline_data["timeline"][-12:]:
            bar_length = int((item['commits'] / max_commits) * 20) if max_commits > 0 else 0
            bar = "█" * bar_length
            report += f"{item['month']}: {bar} ({item['commits']}次)\n"

        report += f"""```

### 贡献者活跃度排名
"""

        # 生成贡献者排名文本
        for i, (name, stats) in enumerate(contributor_data['top_contributors'][:10], 1):
            bar_length = int((stats['lines_changed'] / contributor_data['top_contributors'][0][1]['lines_changed']) * 20) if contributor_data['top_contributors'] else 0
            bar = "█" * bar_length
            report += f"{i}. {name}: {bar} ({stats['lines_changed']:,}行)\n"

        report += f"""

### 文件类型分布
"""

        # 统计文件类型分布
        file_type_totals = defaultdict(int)
        for item in timeline_data["timeline"]:
            for ext, count in item["file_types"].items():
                file_type_totals[ext] += count

        # 生成文件类型文本图表
        max_count = max(file_type_totals.values(), default=0)
        for ext, count in sorted(file_type_totals.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / sum(file_type_totals.values())) * 100 if file_type_totals else 0
            bar_length = int((count / max_count) * 20) if max_count > 0 else 0
            bar = "█" * bar_length
            report += f"{ext.upper()}: {bar} ({count:,}次, {percentage:.1f}%)\n"

        report += f"""

---

## 👥 贡献者深度分析

### Top 10 贡献者详细数据

| 排名 | 贡献者 | 提交数 | 代码变更 | 主要文件类型 | 贡献时长 |
|------|--------|--------|----------|--------------|----------|
"""

        # 添加贡献者详细表格
        for i, (name, stats) in enumerate(contributor_data['top_contributors'][:10], 1):
            top_file_type = max(stats['file_types'].items(), key=lambda x: x[1]) if stats['file_types'] else ('无', 0)

            # 计算贡献时长
            if stats['first_commit'] and stats['last_commit']:
                first_date = datetime.fromisoformat(stats['first_commit'])
                last_date = datetime.fromisoformat(stats['last_commit'])
                duration_days = (last_date - first_date).days
                duration_str = f"{duration_days}天" if duration_days > 0 else "单次"
            else:
                duration_str = "未知"

            report += f"| {i} | {name} | {stats['total_commits']} | {stats['lines_changed']:,} | {top_file_type[0]} | {duration_str} |\n"

        report += f"""

---

## 🔍 AI智能洞察分析

{ai_insights}

---

## 📋 技术栈演化趋势

### 文件类型变更统计

"""

        # 生成文件类型统计
        for ext, count in sorted(file_type_totals.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / sum(file_type_totals.values())) * 100 if file_type_totals else 0
            report += f"- **{ext}**: {count:,} 次变更 ({percentage:.1f}%)\n"

        report += f"""

---

## 🎯 项目健康度评估

### 健康度评分详情
"""

        # 计算各项评分（使用简单的计算方法）
        activity_score = min(100, int(timeline_data['avg_commits_per_month'] * 5))
        diversity_score = min(100, int(contributor_data['total_contributors'] * 8))
        maturity_score = min(100, int((timeline_data['total_months'] * 2) + (timeline_data['avg_commits_per_month'] * 3)))

        report += f"""
- **活跃度评分**: {activity_score}/100
- **贡献者多样性**: {diversity_score}/100
- **项目成熟度**: {maturity_score}/100

---

*📊 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*🔍 分析提交数: {total_commits:,}*
*📈 分析深度: 最近{timeline_data['total_months']}个月*
*🤖 AI分析提供商: {ai_config.get('ai_provider', 'Unknown')} ({ai_config.get('ai_model', 'Unknown')})*

---

"""

        return report

    def _save_evolution_document(self, project_path: str, content: str) -> str:
        """保存演化分析文档"""

        # 创建文档目录
        docs_dir = Path(project_path) / "git-ai-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evolution_timeline_{timestamp}.md"
        file_path = docs_dir / filename

        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ 演化时间线文档已保存: {file_path}")
        return str(file_path)

# 创建全局实例
project_evolution_analyzer = ProjectEvolutionAnalyzer()

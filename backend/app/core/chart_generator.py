import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from datetime import datetime

class ChartGenerator:
    """图表生成器 - 生成PNG图片用于Markdown嵌入"""

    def __init__(self):
        # 设置matplotlib中文字体
        self._setup_chinese_font()

        # 创建assets目录
        self.assets_dir = None

    def _setup_chinese_font(self):
        """设置中文字体支持"""
        try:
            # 尝试使用系统字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            # 如果字体不存在，使用默认字体
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False

    def setup_assets_dir(self, project_path: str) -> str:
        """设置assets目录"""
        self.assets_dir = Path(project_path) / "git-ai-docs" / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        return str(self.assets_dir)

    def generate_commit_timeline_chart(self, timeline_data: List[Dict[str, Any]],
                                     filename: str = "commit_timeline.png") -> str:
        """生成提交时间线图表"""

        if not timeline_data:
            return self._generate_placeholder_chart("暂无提交数据", filename, project_path)

        # 提取数据
        months = [item['month'] for item in timeline_data]
        commits = [item['commits'] for item in timeline_data]
        lines_changed = [item['lines_changed'] for item in timeline_data]

        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # 提交数图表
        ax1.plot(months, commits, marker='o', linewidth=2, markersize=6, color='#2563eb')
        ax1.fill_between(months, commits, alpha=0.3, color='#2563eb')
        ax1.set_title('提交活跃度时间线', fontsize=14, fontweight='bold', pad=20)
        ax1.set_ylabel('提交数量', fontsize=12)
        ax1.grid(True, alpha=0.3)

        # 代码变更图表
        ax2.bar(months, lines_changed, color='#10b981', alpha=0.7)
        ax2.set_title('代码变更量统计', fontsize=14, fontweight='bold', pad=20)
        ax2.set_ylabel('代码行数', fontsize=12)
        ax2.set_xlabel('月份', fontsize=12)

        # 旋转x轴标签
        for ax in [ax1, ax2]:
            ax.tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def generate_contributor_chart(self, top_contributors: List[tuple],
                                filename: str = "contributor_chart.png") -> str:
        """生成贡献者图表"""

        if not top_contributors:
            return self._generate_placeholder_chart("暂无贡献者数据", filename, project_path)

        # 提取数据
        names = [name[:15] + "..." if len(name) > 15 else name for name, _ in top_contributors[:10]]
        commits = [stats['total_commits'] for _, stats in top_contributors[:10]]
        lines_changed = [stats['lines_changed'] for _, stats in top_contributors[:10]]

        # 创建图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # 提交数图表
        bars1 = ax1.barh(names, commits, color='#f59e0b', alpha=0.8)
        ax1.set_title('贡献者提交数排名', fontsize=14, fontweight='bold')
        ax1.set_xlabel('提交数量')

        # 添加数值标签
        for bar, value in zip(bars1, commits):
            ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{value}', ha='left', va='center', fontweight='bold')

        # 代码变更图表
        bars2 = ax2.barh(names, lines_changed, color='#ef4444', alpha=0.8)
        ax2.set_title('贡献者代码变更量排名', fontsize=14, fontweight='bold')
        ax2.set_xlabel('代码行数')

        # 添加数值标签
        for bar, value in zip(bars2, lines_changed):
            ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{value:,}', ha='left', va='center', fontweight='bold')

        plt.tight_layout()

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def generate_file_type_pie_chart(self, timeline_data: List[Dict[str, Any]],
                                   filename: str = "file_type_chart.png") -> str:
        """生成文件类型饼图"""

        # 统计文件类型
        file_type_totals = {}
        for item in timeline_data:
            for ext, count in item["file_types"].items():
                file_type_totals[ext] = file_type_totals.get(ext, 0) + count

        if not file_type_totals:
            return self._generate_placeholder_chart("暂无文件类型数据", filename, project_path)

        # 只显示前8种文件类型
        sorted_types = sorted(file_type_totals.items(), key=lambda x: x[1], reverse=True)[:8]
        labels = [ext.upper() for ext, _ in sorted_types]
        sizes = [count for _, count in sorted_types]

        # 创建饼图
        fig, ax = plt.subplots(figsize=(10, 8))

        # 使用颜色映射
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                         colors=colors, startangle=90)

        ax.set_title('文件类型分布', fontsize=16, fontweight='bold', pad=20)
        ax.axis('equal')  # 确保饼图是圆的

        # 设置标签样式
        for text in texts:
            text.set_fontsize(12)
            text.set_fontweight('bold')

        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        plt.tight_layout()

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def generate_activity_heatmap(self, timeline_data: List[Dict[str, Any]],
                                filename: str = "activity_heatmap.png") -> str:
        """生成活跃度热力图"""

        if not timeline_data:
            return self._generate_placeholder_chart("暂无活跃度数据", filename, project_path)

        # 准备热力图数据
        recent_data = timeline_data[-12:]  # 最近12个月

        months = [item['month'] for item in recent_data]
        commits_data = np.array([[item['commits']] for item in recent_data])

        # 创建热力图
        fig, ax = plt.subplots(figsize=(12, 4))

        # 生成热力图
        im = ax.imshow(commits_data.T, cmap='YlOrRd', aspect='auto')

        # 设置标签
        ax.set_xticks(range(len(months)))
        ax.set_xticklabels([m[-2:] for m in months], rotation=0)
        ax.set_yticks([])
        ax.set_title('月度活跃度热力图', fontsize=14, fontweight='bold', pad=20)

        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('提交数量', rotation=270, labelpad=15)

        # 在每个单元格上添加数值
        for i, commits in enumerate([item['commits'] for item in recent_data]):
            ax.text(i, 0, str(commits), ha='center', va='center',
                   color='black' if commits < max([item['commits'] for item in recent_data]) * 0.7 else 'white',
                   fontweight='bold')

        plt.tight_layout()

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def generate_health_radar_chart(self, activity_score: int, diversity_score: int,
                                  maturity_score: int, filename: str = "health_radar.png") -> str:
        """生成健康度雷达图"""

        # 雷达图数据
        categories = ['活跃度', '多样性', '成熟度']
        values = [activity_score, diversity_score, maturity_score]

        # 创建雷达图
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))

        # 计算角度
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        values += values[:1]  # 闭合图形
        angles += angles[:1]

        # 绘制雷达图
        ax.fill(angles, values, color='#10b981', alpha=0.3)
        ax.plot(angles, values, 'o-', linewidth=2, color='#059669')

        # 设置标签
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=12, fontweight='bold')
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=10)

        ax.set_title('项目健康度雷达图', fontsize=16, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def _generate_placeholder_chart(self, message: str, filename: str, project_path: str = None) -> str:
        """生成占位符图表"""

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        # 保存图片
        filepath = self.assets_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        # 如果没有提供project_path，使用默认路径
        if project_path is None:
            return f"http://localhost:8000/static/placeholder/{filepath.name}"

        # 使用相对于项目根目录的路径
        try:
            # 获取项目根目录路径
            project_root = Path(project_path)
            relative_path = filepath.relative_to(project_root)
            return f"http://localhost:8000/static/{project_root.name}/git-ai-docs/assets/{filepath.name}"
        except ValueError:
            # 如果相对路径失败，使用项目名称 + 文件名
            return f"http://localhost:8000/static/{Path(project_path).name}/git-ai-docs/assets/{filepath.name}"

    def generate_all_charts(self, timeline_data: Dict[str, Any],
                          contributor_data: Dict[str, Any]) -> Dict[str, str]:
        """生成所有图表"""

        charts = {}

        try:
            # 生成时间线图表
            charts['commit_timeline'] = self.generate_commit_timeline_chart(
                timeline_data["timeline"], "commit_timeline.png"
            )

            # 生成贡献者图表
            charts['contributor_chart'] = self.generate_contributor_chart(
                contributor_data["top_contributors"], "contributor_chart.png"
            )

            # 生成文件类型饼图
            charts['file_type_chart'] = self.generate_file_type_pie_chart(
                timeline_data["timeline"], "file_type_chart.png"
            )

            # 生成活跃度热力图
            charts['activity_heatmap'] = self.generate_activity_heatmap(
                timeline_data["timeline"], "activity_heatmap.png"
            )

            # 生成健康度雷达图
            activity_score = self._calculate_activity_score(timeline_data)
            diversity_score = self._calculate_diversity_score(contributor_data)
            maturity_score = self._calculate_maturity_score(timeline_data, 1000)  # 示例值

            charts['health_radar'] = self.generate_health_radar_chart(
                activity_score, diversity_score, maturity_score, "health_radar.png"
            )

        except Exception as e:
            print(f"生成图表失败: {e}")
            # 返回占位符
            charts = {
                'commit_timeline': self._generate_placeholder_chart("图表生成失败", "commit_timeline.png", None),
                'contributor_chart': self._generate_placeholder_chart("图表生成失败", "contributor_chart.png", None),
                'file_type_chart': self._generate_placeholder_chart("图表生成失败", "file_type_chart.png", None),
                'activity_heatmap': self._generate_placeholder_chart("图表生成失败", "activity_heatmap.png", None),
                'health_radar': self._generate_placeholder_chart("图表生成失败", "health_radar.png", None)
            }

        return charts

    def _calculate_activity_score(self, timeline_data: Dict[str, Any]) -> int:
        """计算活跃度评分"""
        if not timeline_data["timeline"]:
            return 0

        avg_commits = timeline_data["avg_commits_per_month"]
        total_months = timeline_data["total_months"]

        score = min(100, int((avg_commits * 5) + (total_months * 2)))
        return max(0, score)

    def _calculate_diversity_score(self, contributor_data: Dict[str, Any]) -> int:
        """计算贡献者多样性评分"""
        total_contributors = contributor_data["total_contributors"]
        if total_contributors == 0:
            return 0

        score = min(100, int(total_contributors * 8))
        return score

    def _calculate_maturity_score(self, timeline_data: Dict[str, Any], total_commits: int) -> int:
        """计算项目成熟度评分"""
        months = timeline_data["total_months"]
        avg_commits = timeline_data["avg_commits_per_month"]

        maturity = (months * 2) + (avg_commits * 3) + (total_commits / 100)
        return min(100, int(maturity))

# 创建全局实例
chart_generator = ChartGenerator()

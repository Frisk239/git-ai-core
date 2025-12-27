import httpx
import asyncio
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from fastapi import HTTPException
from app.core.github_recommendation_db import github_recommendation_db

class GitHubService:
    def __init__(self, access_token: str = None):
        self.access_token = access_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Git-AI-Core"
        }
        if access_token:
            self.headers["Authorization"] = f"token {access_token}"

    async def get_weekly_trending(self) -> List[Dict]:
        """获取过去一周最火的项目"""
        # 获取30天前的日期，扩大搜索范围
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        # 使用更简单的查询条件
        query = f"stars:>1000 pushed:>={since_date}"

        try:
            return await self.search_repos(query, sort="stars", order="desc", per_page=10)
        except Exception as e:
            print(f"获取trending项目失败: {e}")
            return []

    async def search_repos(self, query: str, sort: str = "stars", order: str = "desc", per_page: int = 10) -> List[Dict]:
        """搜索GitHub仓库"""
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search/repositories",
                    params=params,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()["items"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise HTTPException(status_code=429, detail="GitHub API速率限制，请稍后再试")
            elif e.response.status_code == 401:
                raise HTTPException(status_code=401, detail="GitHub认证失败，请检查access token是否正确或已过期")
            raise HTTPException(status_code=e.response.status_code, detail=f"GitHub API错误: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

    async def get_repo_details(self, owner: str, repo: str) -> Dict:
        """获取仓库详细信息"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="仓库不存在")
            raise HTTPException(status_code=e.response.status_code, detail=f"GitHub API错误: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取仓库详情失败: {str(e)}")

    async def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """获取README内容"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/readme",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                # 解码base64内容
                if data.get("content"):
                    return base64.b64decode(data["content"]).decode('utf-8')
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None  # README不存在
            raise HTTPException(status_code=e.response.status_code, detail=f"GitHub API错误: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取README失败: {str(e)}")

    async def test_connection(self) -> Dict:
        """测试GitHub连接"""
        if not self.access_token:
            return {"success": False, "error": "未提供access token"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                user_data = response.json()
                return {
                    "success": True,
                    "user": {
                        "login": user_data.get("login"),
                        "name": user_data.get("name"),
                        "avatar_url": user_data.get("avatar_url")
                    }
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {"success": False, "error": "Access token无效"}
            return {"success": False, "error": f"GitHub API错误: {e}"}
        except Exception as e:
            return {"success": False, "error": f"连接测试失败: {str(e)}"}

    async def enhanced_search_repos(self, query: str, language: str = None, 
                                  updated_after: str = None, sort: str = None, 
                                  per_page: int = 20) -> List[Dict]:
        """增强搜索功能，支持高级筛选和排序"""
        # 构建高级搜索查询
        search_query = query
        if language and language.strip():
            search_query += f" language:{language.strip()}"
        if updated_after:
            search_query += f" pushed:>={updated_after}"
        
        # 设置排序参数
        sort_by = "stars"
        order = "desc"
        
        if sort == "stars-asc":
            sort_by = "stars"
            order = "asc"
        elif sort == "stars-desc":
            sort_by = "stars"
            order = "desc"
        
        # 获取基础搜索结果
        print(f"增强搜索查询: {search_query}, 排序: {sort_by}, 顺序: {order}")  # 调试信息
        repos = await self.search_repos(search_query, sort_by, order, min(per_page * 2, 50))
        
        # 应用智能排序（如果是默认排序）
        if not sort:
            scored_repos = []
            for repo in repos:
                score = self._calculate_relevance_score(repo, query)
                scored_repos.append((score, repo))
            
            # 按相关性排序并限制结果数量
            scored_repos.sort(key=lambda x: x[0], reverse=True)
            result_repos = [repo for score, repo in scored_repos[:per_page]]
        else:
            # 直接使用GitHub API的排序结果
            result_repos = repos[:per_page]
        
        # 记录搜索行为
        for repo in result_repos:
            github_recommendation_db.record_user_action(
                "default", repo["full_name"], "search", query
            )
            github_recommendation_db.cache_repo_features(repo)
        
        return result_repos

    def _calculate_relevance_score(self, repo: Dict, query: str) -> float:
        """计算项目与查询的相关性评分"""
        score = 0.0
        query_lower = query.lower()
        
        # 名称匹配权重最高 (40%)
        name = repo.get("name", "").lower()
        if query_lower in name:
            score += 0.4
        
        # 完整名称匹配 (额外30%)
        full_name = repo.get("full_name", "").lower()
        if query_lower in full_name:
            score += 0.3
        
        # 描述匹配权重 (20%)
        description = repo.get("description", "").lower()
        if description and query_lower in description:
            score += 0.2
        
        # 语言匹配权重 (10%)
        repo_language = repo.get("language", "").lower()
        if repo_language and query_lower == repo_language:
            score += 0.1
        
        # 质量加成 (基于星标和更新时间的综合评分)
        quality_bonus = self._calculate_quality_bonus(repo)
        score += quality_bonus * 0.2  # 质量最多贡献20%
        
        return min(score, 1.0)  # 确保不超过1.0

    def _calculate_quality_bonus(self, repo: Dict) -> float:
        """计算质量加成分数"""
        bonus = 0.0
        
        # 星标数加成
        stars = repo.get("stargazers_count", 0)
        bonus += min(stars / 5000, 0.5)  # 每5000星加0.5分，最多0.5分
        
        # 更新活跃度加成
        if repo.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(repo["updated_at"].replace('Z', '+00:00'))
                days_since_update = (datetime.now() - updated_at).days
                if days_since_update <= 30:  # 30天内更新
                    bonus += 0.3
                elif days_since_update <= 90:  # 90天内更新
                    bonus += 0.1
            except:
                pass
        
        return min(bonus, 0.7)  # 质量加成最多0.7分

    async def get_personalized_recommendations(self, user_id: str = "default", limit: int = 10) -> List[Dict]:
        """获取个性化推荐"""
        # 获取用户历史行为
        user_actions = github_recommendation_db.get_user_actions(user_id)
        
        recommendations = []
        
        # 策略1: 基于热度的推荐 (30%)
        trending_recs = await self.get_weekly_trending()
        if trending_recs:
            recommendations.extend([(0.3, rec, "trending") for rec in trending_recs[:3]])
        
        # 策略2: 基于内容的推荐 (40%)
        if user_actions:
            content_recs = await self._get_content_based_recommendations(user_actions, limit=4)
            if content_recs:
                recommendations.extend([(0.4, rec, "personalized") for rec in content_recs])
        
        # 策略3: 探索性推荐 (30%)
        explore_recs = await self._get_exploratory_recommendations(user_actions, limit=3)
        if explore_recs:
            recommendations.extend([(0.3, rec, "explore") for rec in explore_recs])
        
        # 如果没有推荐结果，返回空列表
        if not recommendations:
            return []
        
        # 去重、排序和限制结果
        final_recommendations = self._deduplicate_and_sort_recommendations(recommendations, limit)
        
        # 记录推荐历史
        for repo in final_recommendations:
            github_recommendation_db.record_recommendation(
                user_id, repo["full_name"], 0.8, "personalized"
            )
        
        return final_recommendations

    async def _get_content_based_recommendations(self, user_actions: List[Dict], limit: int = 4) -> List[Dict]:
        """基于用户历史行为的推荐"""
        if not user_actions:
            return []
        
        # 分析用户偏好
        user_preferences = self._analyze_user_preferences(user_actions)
        
        recommendations = []
        
        # 基于语言的推荐
        if user_preferences.get('languages'):
            for language in user_preferences['languages'][:3]:  # 取前3个最常用的语言
                language_repos = await self.search_repos(
                    f"stars:>100 language:{language}", 
                    sort="stars", 
                    order="desc", 
                    per_page=5
                )
                recommendations.extend(language_repos)
        
        # 基于主题的推荐
        if user_preferences.get('topics'):
            for topic in user_preferences['topics'][:2]:  # 取前2个最感兴趣的主题
                topic_repos = await self.search_repos(
                    f"stars:>50 topic:{topic}", 
                    sort="stars", 
                    order="desc", 
                    per_page=3
                )
                recommendations.extend(topic_repos)
        
        # 去重
        seen = set()
        unique_recommendations = []
        for repo in recommendations:
            if repo["full_name"] not in seen:
                seen.add(repo["full_name"])
                unique_recommendations.append(repo)
        
        return unique_recommendations[:limit]

    def _analyze_user_preferences(self, user_actions: List[Dict]) -> Dict:
        """分析用户偏好"""
        preferences = {
            'languages': {},
            'topics': {},
            'action_types': {}
        }
        
        for action in user_actions:
            repo_full_name = action['repo_full_name']
            cached_repo = github_recommendation_db.get_cached_repo(repo_full_name)
            
            if cached_repo:
                # 分析语言偏好
                language = cached_repo.get('language')
                if language:
                    preferences['languages'][language] = preferences['languages'].get(language, 0) + 1
                
                # 分析主题偏好
                topics = cached_repo.get('topics', []) or []
                for topic in topics:
                    preferences['topics'][topic] = preferences['topics'].get(topic, 0) + 1
            
            # 分析行为类型偏好
            action_type = action['action_type']
            preferences['action_types'][action_type] = preferences['action_types'].get(action_type, 0) + 1
        
        # 排序并返回前几个
        return {
            'languages': sorted(preferences['languages'].keys(), 
                               key=lambda x: preferences['languages'][x], reverse=True)[:5],
            'topics': sorted(preferences['topics'].keys(), 
                            key=lambda x: preferences['topics'][x], reverse=True)[:5],
            'action_types': preferences['action_types']
        }

    async def _get_exploratory_recommendations(self, user_actions: List[Dict], limit: int = 3) -> List[Dict]:
        """探索性推荐（新项目、不同技术栈等）"""
        recommendations = []
        
        # 获取用户偏好
        user_preferences = self._analyze_user_preferences(user_actions) if user_actions else {}
        user_languages = set(user_preferences.get('languages', []))
        
        # 推荐新兴技术项目
        emerging_techs = ['rust', 'typescript', 'go', 'kotlin', 'swift']
        for tech in emerging_techs:
            if tech not in user_languages:  # 推荐用户未使用的新技术
                tech_repos = await self.search_repos(
                    f"stars:>500 language:{tech} created:>2023-01-01", 
                    sort="stars", 
                    order="desc", 
                    per_page=2
                )
                recommendations.extend(tech_repos)
        
        # 推荐高质量的新项目
        new_repos = await self.search_repos(
            "stars:>100 created:>2024-01-01", 
            sort="stars", 
            order="desc", 
            per_page=3
        )
        recommendations.extend(new_repos)
        
        # 推荐热门但用户可能没接触过的项目
        if user_languages:
            # 推荐其他热门语言的项目
            popular_languages = ['python', 'javascript', 'java', 'c++', 'c#']
            for lang in popular_languages:
                if lang not in user_languages:
                    lang_repos = await self.search_repos(
                        f"stars:>1000 language:{lang}", 
                        sort="stars", 
                        order="desc", 
                        per_page=2
                    )
                    recommendations.extend(lang_repos)
        
        # 去重
        seen = set()
        unique_recommendations = []
        for repo in recommendations:
            if repo["full_name"] not in seen:
                seen.add(repo["full_name"])
                unique_recommendations.append(repo)
        
        return unique_recommendations[:limit]

    def _deduplicate_and_sort_recommendations(self, recommendations: List, limit: int) -> List[Dict]:
        """去重和排序推荐结果"""
        if not recommendations:
            return []
            
        seen = set()
        unique_recommendations = []
        
        for weight, repo, rec_type in recommendations:
            if repo["full_name"] not in seen:
                seen.add(repo["full_name"])
                unique_recommendations.append((weight, repo))
        
        # 按权重排序
        unique_recommendations.sort(key=lambda x: x[0], reverse=True)
        return [repo for weight, repo in unique_recommendations[:limit]]

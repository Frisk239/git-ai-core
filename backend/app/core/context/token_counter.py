"""
Token 计数器 - 估算消息和工具结果的 token 数量

参考 Cline 的实现：
1. 从 AI 响应中解析实际 token 使用量
2. 粗略估算：中文约 2 chars/token，英文约 4 chars/token
3. 考虑工具结果、系统提示词等
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    Token 计数器

    用于估算对话历史的 token 使用量，支持：
    1. 精确计数（如果 AI 返回了 usage 信息）
    2. 粗略估算（基于字符数）

    模型上下文窗口数据参考 Cline 项目
    """

    # 粗略估算系数
    CHARS_PER_TOKEN_ZH = 2  # 中文：约 2 字符/token
    CHARS_PER_TOKEN_EN = 4  # 英文：约 4 字符/token
    CHARS_PER_TOKEN_MIXED = 3  # 混合：约 3 字符/token

    # 模型上下文窗口大小（参考 Cline）
    CONTEXT_WINDOWS = {
        # OpenAI
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "gpt-4-turbo": 128_000,
        "gpt-4-turbo-2024-04-09": 128_000,
        "gpt-3.5-turbo": 16_000,
        "gpt-3.5-turbo-0125": 16_000,
        "o1-preview": 128_000,
        "o1-mini": 128_000,
        "o3": 200_000,
        "o3-mini": 200_000,
        "o4-mini": 200_000,

        # Anthropic Claude
        "claude-sonnet-4-5-20250929": 200_000,
        "claude-sonnet-4-5-20250929:1m": 1_000_000,
        "claude-haiku-4-5-20251001": 200_000,
        "claude-sonnet-4-20250514": 200_000,
        "claude-sonnet-4-20250514:1m": 1_000_000,
        "claude-opus-4-5-20251101": 200_000,
        "claude-opus-4-1-20250805": 200_000,
        "claude-opus-4-20250514": 200_000,
        "claude-3-7-sonnet-20250219": 200_000,
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-3-5-haiku-20241022": 200_000,
        "claude-3-opus-20240229": 200_000,
        "claude-3-haiku-20240307": 200_000,
        "claude-sonnet": 200_000,
        "claude-haiku": 200_000,
        "claude-opus": 200_000,

        # Google Gemini
        "gemini-2.0-flash-exp": 1_000_000,
        "gemini-2.5-pro": 1_000_000,
        "gemini-2.5-flash": 1_000_000,
        "gemini-1.5-pro": 1_000_000,
        "gemini-1.5-flash": 1_000_000,
        "gemini-pro": 1_000_000,
        "gemini-flash": 1_000_000,

        # DeepSeek
        "deepseek-chat": 64_000,
        "deepseek-reasoner": 64_000,
        "deepseek-r1": 64_000,
        "deepseek-r1-local": 64_000,

        # Moonshot
        "moonshot-v1-8k": 8_000,
        "moonshot-v1-32k": 32_000,
        "moonshot-v1-128k": 128_000,

        # 智谱 GLM (所有模型都是 200k 上下文)
        "glm-4.7": 200_000,
        "glm-4.0": 200_000,
        "glm-4-plus": 200_000,
        "glm-4-air": 200_000,
        "glm-4-flash": 200_000,
        "glm-4.5": 200_000,
        "glm-4": 200_000,
        "glm-4-all-tools": 200_000,
        "glm-4-airx": 200_000,
        "glm-4-flashx": 200_000,

        # OpenRouter (常见模型)
        "meta-llama/llama-3.1-70b-instruct": 128_000,
        "meta-llama/llama-3.1-405b-instruct": 128_000,
        "microsoft/wizardlm-2-8x22b": 256_000,

        # AWS Bedrock
        "amazon.nova-pro-v1:0": 300_000,
        "amazon.nova-lite-v1:0": 300_000,
        "amazon.nova-micro-v1:0": 128_000,

        # 默认值
        "default": 128_000,
    }

    # 缓冲区大小（参考 Cline 的 getContextWindowInfo）
    BUFFER_SIZES = {
        64_000: 27_000,    # DeepSeek
        128_000: 30_000,  # 大多数模型
        200_000: 40_000,  # Claude
        256_000: 50_000,  # 更大的模型
        300_000: 60_000,  # Amazon Nova
        1_000_000: 100_000,  # 1M 上下文
    }

    def __init__(self):
        self.total_tokens_used = 0
        self.cached_read_tokens = 0
        self.cached_write_tokens = 0

    def get_context_window(self, model: str) -> int:
        """获取模型的上下文窗口大小"""
        # 标准化模型名称（小写化）
        model_key = model.lower().strip()

        # 精确匹配
        if model_key in self.CONTEXT_WINDOWS:
            return self.CONTEXT_WINDOWS[model_key]

        # 模糊匹配（处理模型名称变体）
        for key, value in self.CONTEXT_WINDOWS.items():
            if key != "default" and key in model_key:
                return value

        # 默认返回 128k
        logger.warning(f"未知模型 '{model}'，使用默认上下文窗口 128k")
        return 128_000

    def get_max_allowed_size(self, model: str) -> int:
        """
        获取允许的最大 token 使用量

        完全参考 Cline 的 getContextWindowInfo 实现：
        - 64k 窗口：留出 27k 缓冲
        - 128k 窗口：留出 30k 缓冲
        - 200k 窗口：留出 40k 缓冲
        - 其他：max(contextWindow - 40k, contextWindow * 0.8)
        """
        context_window = self.get_context_window(model)

        # 查找预定义的缓冲区
        for size, buffer in self.BUFFER_SIZES.items():
            if context_window == size:
                return context_window - buffer

        # 默认公式：max(contextWindow - 40k, contextWindow * 0.8)
        return max(context_window - 40_000, int(context_window * 0.8))

    def estimate_text_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量

        策略：
        - 检测中英文比例
        - 按混合比例计算
        """
        if not text:
            return 0

        total_chars = len(text)

        # 检测中文字符数量
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = total_chars - chinese_chars

        # 计算中英文比例
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0

        # 根据比例选择系数
        if chinese_ratio > 0.7:
            # 主要是中文
            chars_per_token = self.CHARS_PER_TOKEN_ZH
        elif chinese_ratio < 0.3:
            # 主要是英文
            chars_per_token = self.CHARS_PER_TOKEN_EN
        else:
            # 混合
            chars_per_token = self.CHARS_PER_TOKEN_MIXED

        estimated = max(1, int(total_chars / chars_per_token))

        return estimated

    def count_message_tokens(self, message: Dict[str, Any]) -> int:
        """
        估算单条消息的 token 数量

        Args:
            message: 消息对象，格式：{"role": "user", "content": "..."}

        Returns:
            估算的 token 数量
        """
        content = message.get("content", "")

        if isinstance(content, str):
            return self.estimate_text_tokens(content)
        elif isinstance(content, list):
            # 多模态内容（例如图片 + 文本）
            total = 0
            for item in content:
                if item.get("type") == "text":
                    total += self.estimate_text_tokens(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # 图片通常占用较多 token（约为 85-1000+ token）
                    total += 500  # 保守估计
            return total

        return 0

    def count_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        估算消息列表的总 token 数量

        Args:
            messages: 消息列表

        Returns:
            估算的总 token 数量
        """
        total = 0
        for msg in messages:
            total += self.count_message_tokens(msg)
        return total

    def count_tool_result_tokens(self, tool_name: str, result: Dict[str, Any]) -> int:
        """
        估算工具结果的 token 数量

        Args:
            tool_name: 工具名称
            result: 工具执行结果

        Returns:
            估算的 token 数量
        """
        # 工具名称和状态
        base_tokens = 50  # 基础开销

        # 结果数据
        if result.get("success"):
            data = result.get("data")
            if data:
                # 将数据转换为 JSON 字符串来估算
                json_str = json.dumps(data, ensure_ascii=False)
                return base_tokens + self.estimate_text_tokens(json_str)
        else:
            # 错误信息通常较短
            error = result.get("error", "")
            return base_tokens + self.estimate_text_tokens(str(error))

        return base_tokens

    def parse_usage_from_response(self, response: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        从 AI 响应中解析实际的 token 使用量

        Args:
            response: AI 响应对象

        Returns:
            使用量字典，格式：{"tokens_in": int, "tokens_out": int, "total": int}
        """
        usage = response.get("usage")
        if not usage:
            return None

        try:
            # OpenAI 格式
            if "prompt_tokens" in usage:
                return {
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                    "cache_read_tokens": usage.get("prompt_cache_hit_tokens", 0),
                    "cache_write_tokens": usage.get("prompt_cache_miss_tokens", 0),
                }
        except Exception as e:
            logger.warning(f"解析 usage 失败: {e}")

        return None

    def update_token_usage(self, usage: Dict[str, int]):
        """
        更新总 token 使用量

        Args:
            usage: 使用量字典
        """
        if usage:
            self.total_tokens_used = usage.get("total", 0)
            self.cached_read_tokens = usage.get("cache_read_tokens", 0)
            self.cached_write_tokens = usage.get("cache_write_tokens", 0)

    def should_compress(self, current_tokens: int, model: str, threshold: float = 0.8) -> bool:
        """
        判断是否需要压缩上下文

        Args:
            current_tokens: 当前 token 使用量
            model: 模型名称
            threshold: 压缩阈值（0.8 表示使用 80% 时压缩）

        Returns:
            是否需要压缩
        """
        max_allowed = self.get_max_allowed_size(model)

        # 检查是否超过阈值
        return current_tokens >= max_allowed * threshold

    def get_compression_info(self, messages: List[Dict[str, Any]], model: str) -> Dict[str, Any]:
        """
        获取压缩决策信息

        Args:
            messages: 当前消息列表
            model: 模型名称

        Returns:
            压缩信息字典
        """
        estimated_tokens = self.count_messages_tokens(messages)
        context_window = self.get_context_window(model)
        max_allowed = self.get_max_allowed_size(model)

        return {
            "estimated_tokens": estimated_tokens,
            "context_window": context_window,
            "max_allowed": max_allowed,
            "usage_percentage": estimated_tokens / context_window if context_window > 0 else 0,
            "should_compress": estimated_tokens >= max_allowed * 0.8,
            "must_compress": estimated_tokens >= max_allowed * 0.95,
        }

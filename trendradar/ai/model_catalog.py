# coding=utf-8
"""
AI 模型清单聚合模块

从两个数据源拉取模型名：
1. LiteLLM 内置 catalog（litellm.model_cost，过滤 provider/*）
2. Provider API 的 /models 端点（OpenAI 兼容）

合并去重后返回。Provider API 失败不应阻塞 LiteLLM 部分。
"""

from typing import List, Optional, Set, Tuple

import litellm
import requests


# 精简后的 7 项 provider 清单（按协议家族筛选）
# 覆盖 99% 用例：openai 兼容（DeepSeek/Moonshot/MiniMax/Qwen 等）+ Anthropic + Gemini + AWS + Google Cloud + Azure + 本地 Ollama
CURATED_PROVIDERS = [
    "openai",
    "anthropic",
    "gemini",
    "bedrock",
    "vertex_ai",
    "azure",
    "ollama",
]


FETCH_TIMEOUT = 15


class ProviderAPIError(Exception):
    """Provider API 调用错误，含 user_message 给前端展示"""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class ModelCatalog:
    """AI 模型清单聚合（LiteLLM catalog + provider API）"""

    @staticmethod
    def list_providers() -> Set[str]:
        """返回 LiteLLM 支持的所有 provider slug 集合"""
        try:
            return {p.value for p in litellm.provider_list}
        except Exception:
            return set()

    @staticmethod
    def list_curated_providers() -> List[str]:
        """返回精简后的 7 项 provider 清单（按协议家族筛选）

        与 list_providers() 不同：list_providers 返回 LiteLLM 全部 130+ provider，
        list_curated_providers 仅返回供前端下拉用的 7 项核心 adapter。
        """
        return list(CURATED_PROVIDERS)

    @staticmethod
    def get_merged(provider: str, api_key: str = "", api_base: str = "") -> List[str]:
        """
        返回 provider 的合并模型列表（去重、按字母序）。
        详细统计请用 get_merged_with_counts。
        """
        models, _, _, _ = ModelCatalog.get_merged_with_counts(provider, api_key, api_base)
        return models

    @staticmethod
    def get_merged_with_counts(
        provider: str, api_key: str = "", api_base: str = ""
    ) -> Tuple[List[str], int, int, Optional[str]]:
        """
        返回 (models, lite_count, provider_count, provider_error)。

        - lite_count：来自 LiteLLM catalog 的模型数
        - provider_count：来自 provider API 的新模型数（不含已在 LiteLLM 中的）
        - provider_error：provider API 错误消息（None 表示成功或未调用）
        """
        # 1. 从 LiteLLM catalog 过滤
        lite_models = ModelCatalog._from_litellm(provider)

        # 2. 尝试从 provider API 拉，捕获错误
        provider_models: List[str] = []
        provider_error: Optional[str] = None
        if api_base and api_key:
            try:
                provider_models = ModelCatalog._fetch_provider_models(
                    provider=provider, api_key=api_key, api_base=api_base
                )
            except ProviderAPIError as e:
                # 失败不影响 LiteLLM 部分；记录错误供调用方决定如何处理
                provider_error = e.user_message

        # 3. 合并去重，LiteLLM 在前
        seen = set(lite_models)
        merged = list(lite_models)
        new_from_provider = 0
        for m in provider_models:
            if m not in seen:
                merged.append(m)
                seen.add(m)
                new_from_provider += 1

        # 4. 排序
        merged_sorted = sorted(set(merged), key=lambda x: x.lower())
        return merged_sorted, len(lite_models), new_from_provider, provider_error

    @staticmethod
    def _from_litellm(provider: str) -> List[str]:
        """从 litellm.model_cost 过滤出 provider/* 去掉前缀"""
        result = []
        prefix = f"{provider}/"
        for key in litellm.model_cost:
            if key.startswith(prefix):
                result.append(key[len(prefix):])
        return result

    @staticmethod
    def _fetch_provider_models(
        provider: str, api_key: str, api_base: str
    ) -> List[str]:
        """
        调用 provider 的 /models 端点，解析 OpenAI 格式。

        Raises:
            ProviderAPIError: 网络/HTTP/超时错误，已归一为 user_message
        """
        # 归一化 base：去末尾斜杠
        base = api_base.rstrip("/")
        url = f"{base}/models"

        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=FETCH_TIMEOUT,
            )
        except requests.Timeout:
            raise ProviderAPIError(f"请求 provider 超时（{FETCH_TIMEOUT}s）")
        except requests.ConnectionError:
            host = api_base or "默认端点"
            raise ProviderAPIError(f"网络连接失败：{host}")
        except requests.RequestException as e:
            raise ProviderAPIError(f"请求失败: {type(e).__name__}")

        if resp.status_code in (401, 403):
            raise ProviderAPIError("Provider API 鉴权失败，请检查 API Key")
        if resp.status_code == 404:
            raise ProviderAPIError("Provider API 不支持 /models 端点")
        if resp.status_code >= 500:
            raise ProviderAPIError(f"Provider API 异常 ({resp.status_code})")
        if resp.status_code >= 400:
            raise ProviderAPIError(f"Provider API 返回错误 ({resp.status_code})")

        # 解析 OpenAI 格式 {data: [{id: "model-name"}]}
        try:
            data = resp.json()
        except (ValueError, requests.JSONDecodeError):
            return []  # 非 JSON 静默忽略

        if not isinstance(data, dict) or "data" not in data:
            return []  # 非 OpenAI 格式静默忽略

        items = data.get("data", [])
        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = item.get("id")
            if not isinstance(mid, str) or not mid:
                continue
            # 如果 id 含 "provider/" 前缀则切掉
            if "/" in mid:
                mid = mid.split("/", 1)[1]
            result.append(mid)
        return result

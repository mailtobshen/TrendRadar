# coding=utf-8
"""
AI 模型连通性测试模块

最小 ping：用 LiteLLM 同步 completion() 发送 "hi" + max_tokens=1，
独立于 AIClient 业务调用链，避免被业务默认 timeout/重试拖慢反馈。
"""

import time
from typing import Tuple

from litellm import completion
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    NotFoundError,
    Timeout,
)


class AITester:
    """AI 模型连通性测试器（ping 风格）"""

    PING_PROMPT = "hi"
    PING_MAX_TOKENS = 1
    PING_TIMEOUT = 30
    PING_NUM_RETRIES = 0

    def __init__(
        self,
        model: str,
        provider: str = "openai",
        api_key: str = "",
        api_base: str = "",
        timeout: int = PING_TIMEOUT,
    ):
        # 运行时向后兼容：老调用传 model="provider/model" 拼接字符串。
        # 当 provider 是默认值且 model 含 "/" 时自动拆分。
        if "/" in model and provider == "openai":
            provider, model = model.split("/", 1)
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout

    def test(self) -> Tuple[bool, str, int]:
        """
        同步 ping 模型。

        Returns:
            (ok, message, latency_ms)
            - ok=True  时 message 固定为 "连接成功"
            - ok=False 时 message 是友好错误（截断 <=200 字）
            - latency_ms 总是返回（即使失败也返回已耗时）
        """
        start = time.monotonic()
        try:
            params = {
                "model": f"{self.provider}/{self.model}",
                "messages": [{"role": "user", "content": self.PING_PROMPT}],
                "max_tokens": self.PING_MAX_TOKENS,
                "timeout": self.timeout,
                "num_retries": self.PING_NUM_RETRIES,
            }
            if self.api_key:
                params["api_key"] = self.api_key
            if self.api_base:
                params["api_base"] = self.api_base

            response = completion(**params)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if not response.choices:
                return False, "模型返回空响应", elapsed_ms
            return True, "连接成功", elapsed_ms

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return False, _friendly_message(e, self.model, self.api_base), elapsed_ms


def _looks_like_auth_error(exc: Exception) -> bool:
    """
    当 LiteLLM 把 401/403 auth 错误包装为非标准异常类型时（常见于 MiniMax、
    自建网关等），通过消息内容判断是否为鉴权错误。
    """
    msg = str(exc).lower()
    strong = [
        "login fail",
        "authorized_error",
        "unauthorized",
        "invalid api key",
    ]
    if any(s in msg for s in strong):
        return True
    if '"http_code":"401"' in msg or '"http_code":"403"' in msg:
        return True
    if " status 401" in msg or " status 403" in msg or " status: 401" in msg or " status: 403" in msg:
        return True
    if "http 401" in msg or "http 403" in msg:
        return True
    return False


def _friendly_message(exc: Exception, model: str, api_base: str) -> str:
    """
    把 LiteLLM/网络/未知异常归一为用户可读的中文短句。

    优先级：鉴权 > 模型不存在 > 超时 > 网络 > 其它
    """
    if isinstance(exc, AuthenticationError) or _looks_like_auth_error(exc):
        return "鉴权失败：API Key 无效或已过期"
    if isinstance(exc, NotFoundError):
        return f"模型不存在：{model}"
    if isinstance(exc, Timeout):
        return f"请求超时（{AITester.PING_TIMEOUT}s）"
    if isinstance(exc, APIConnectionError):
        host = api_base or "默认端点"
        return f"网络连接失败：{host}"
    raw = str(exc).strip() or exc.__class__.__name__
    return f"测试失败: {type(exc).__name__}: {raw[:200]}"

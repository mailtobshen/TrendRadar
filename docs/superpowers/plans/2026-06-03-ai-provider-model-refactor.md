# AI 模型配置 — Provider/Model 字段重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ai.model` 从拼接字符串 `provider/model` 拆成两个独立字段 `ai.provider` + `ai.model`（纯模型名），让 `provider` 在 LiteLLM adapter 路由时正确生效；同步精简 provider 下拉为 6 项硬编码清单，model 下拉默认空靠 ↻ 拉取。

**Architecture:** 后端先改：`AIClient`/`AITester` 增加 `provider` 字段，构造 `f"{provider}/{model}"` 调 LiteLLM；`ModelCatalog` 新增 `CURATED_PROVIDERS` 6 项清单；`config_schema.py` 加载时拆分老格式。前端后改：HTML provider 改 6 项硬编码下拉、model 默认空占位；JS 删 `joinModel`/`splitModel`/`initAiProviderList`/`onProviderChange`、改 `refreshAiModels`、改 `testAiConnection` 传 4 字段；加载逻辑重写。

**Tech Stack:** Python 3.12、`litellm`（已安装）、stdlib `unittest` + `unittest.mock`、vanilla JS。

**Spec:** `docs/superpowers/specs/2026-06-03-ai-provider-model-refactor-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `trendradar/ai/client.py` | 修改 | AIClient 加 provider；构造 `f"{p}/{m}"`；validate_config 改用 provider+model |
| `trendradar/ai/tester.py` | 修改 | AITester 加 provider 构造参数；同样构造 |
| `trendradar/ai/test_tester.py` | 修改 | 9 个测试改用新签名 |
| `trendradar/ai/model_catalog.py` | 修改 | 新增 `CURATED_PROVIDERS` + `list_curated_providers()` |
| `trendradar/ai/test_model_catalog.py` | 修改 | 新增 1 个测试 |
| `trendradar/webui/server.py` | 修改 | `/api/ai/test` 接收 `provider`；`/api/ai/providers` 返回 6 项 |
| `trendradar/webui/config_schema.py` | 修改 | 默认值加 `ai.provider`；加载时拆分老格式 |
| `trendradar/webui/config_page.py` | 修改 | HTML 改 6 项硬编码；JS 删 4 函数改 2 函数；改加载逻辑 |

每 task 独立可验证。

---

## Task 1: AIClient + AITester 增加 provider 字段（TDD）

**Files:**
- Modify: `trendradar/ai/client.py:33-50, 60-70, 113-130`（AIClient.__init__ + chat + validate_config）
- Modify: `trendradar/ai/tester.py:23-40, 50-80`（AITester.__init__ + test）
- Modify: `trendradar/ai/test_tester.py:30-194`（9 个测试改签名）

### Step 1.1: 修改 test_tester.py 中所有 AITester 调用

打开 `/home/administrator/TrendRadar/trendradar/ai/test_tester.py`，将所有：

```python
tester = AITester(model="X/Y", api_key="...", api_base="...")
```

改为：

```python
tester = AITester(provider="X", model="Y", api_key="...", api_base="...")
```

具体替换（在文件中 `grep -n "AITester(model="` 找位置）：

| 位置 | OLD model 值 | NEW (provider, model) |
|---|---|---|
| `test_success_returns_ok_and_message` | `"deepseek/deepseek-chat"` | `("deepseek", "deepseek-chat")` |
| `test_success_passes_minimal_ping` | `"openai/gpt-4o-mini"` | `("openai", "gpt-4o-mini")` |
| `test_no_api_key_no_base_does_not_pass_them` | `"x/y"` | `("x", "y")` |
| `test_with_api_base_passes_it` | `"x/y"` | `("x", "y")` |
| `test_auth_error_message` | `"x/y"` | `("x", "y")` |
| `test_not_found_message` | `"bad/name"` | `("bad", "name")` |
| `test_timeout_message` | `"x/y"` | `("x", "y")` |
| `test_empty_choices_message` | `"x/y"` | `("x", "y")` |
| `test_api_connection_error_message` | `"x/y"` | `("x", "y")` |
| `test_401_wrapped_as_api_connection_error_is_reclassified` | `"minimax/MiniMax-Text-01"` | `("minimax", "MiniMax-Text-01")` |

由于 `params["model"]` 在 `test_success_passes_minimal_ping` 中的断言期望 `"openai/gpt-4o-mini"`，断言本身不变（LiteLLM 看到的还是拼接字符串）。

### Step 1.2: 跑测试确认失败

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_tester 2>&1 | tail -5
```

Expected: 失败，错误如 `TypeError: __init__() got an unexpected keyword argument 'provider'`

### Step 1.3: 修改 AITester 接受 provider 参数

打开 `/home/administrator/TrendRadar/trendradar/ai/tester.py`，把整个文件替换为：

```python
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
```

### Step 1.4: 跑测试确认 9 + 9 + 1 = 19 个测试通过

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_tester 2>&1 | tail -5
```

Expected: `Ran 10 tests in 0.003s — OK`（注：tester.py 10 个测试，因为有 test_provider_api_401_returns_error_in_merged 不属于这里）

实际：test_tester.py 有 9 个测试（spec 里说 9，我前面实现是 9）。

如果 `test_tester.py` 实际只有 8 个测试（之前 Task 1 时是 8 个），运行后会看到 `Ran 8 tests`。两种情况都 OK，只要全部 PASS。

### Step 1.5: 修改 AIClient 增加 provider 字段

打开 `/home/administrator/TrendRadar/trendradar/ai/client.py`，把 `__init__` 方法（约 line 33-41）的：

```python
        self.model = config.get("MODEL", "deepseek/deepseek-chat")
        self.api_key = config.get("API_KEY") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE", "")
        self.temperature = config.get("TEMPERATURE", 1.0)
```

改为：

```python
        self.provider = config.get("PROVIDER", "openai")
        self.model = config.get("MODEL", "")
        self.api_key = config.get("API_KEY") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE", "")
        self.temperature = config.get("TEMPERATURE", 1.0)
```

把 `chat` 方法中的：

```python
            "model": self.model,
```

改为：

```python
            "model": f"{self.provider}/{self.model}",
```

把 `validate_config` 方法（约 line 113-130）的：

```python
        if not self.model:
            return False, "未配置 AI 模型（model）"

        if not self.api_key:
            return False, "未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"

        # 验证模型格式（应该包含 provider/model）
        if "/" not in self.model:
            return False, f"模型格式错误: {self.model}，应为 'provider/model' 格式（如 'deepseek/deepseek-chat'）"

        return True, ""
```

改为：

```python
        if not self.provider:
            return False, "未配置 AI Provider（provider）"

        if not self.model:
            return False, "未配置 AI 模型（model）"

        if not self.api_key:
            return False, "未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"

        return True, ""
```

### Step 1.6: AST 检查

```bash
cd /home/administrator/TrendRadar
python3 -c "import ast; ast.parse(open('trendradar/ai/client.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('trendradar/ai/tester.py').read()); print('OK')"
```

Expected: 两个都 `OK`

### Step 1.7: 跑全部相关测试

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_tester trendradar.ai.test_model_catalog 2>&1 | tail -5
```

Expected: 全部 PASS（test_tester.py 9 个 + test_model_catalog.py 13 个 = 22 个）

### Step 1.8: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/client.py trendradar/ai/tester.py trendradar/ai/test_tester.py
git commit -m "feat(ai): AIClient/AITester 拆分 provider 字段

把 'ai.model = provider/model' 拼接字符串拆为独立的 ai.provider +
ai.model（纯模型名）。AIClient/AITester 内部构造 f'{provider}/{model}'
作为 LiteLLM 的 model 参数，调用方用 ai.model 存纯名。

修复 provider 在 LiteLLM 中被误用为 adapter 路由键导致选错 client
的 bug（如 provider=anthropic + model=MiniMax-M3 会路由到 Anthropic adapter）。"
```

---

## Task 2: ModelCatalog 新增 CURATED_PROVIDERS

**Files:**
- Modify: `trendradar/ai/model_catalog.py`（新增常量和方法）
- Modify: `trendradar/ai/test_model_catalog.py`（新增 1 个测试）

### Step 2.1: 写新测试

打开 `/home/administrator/TrendRadar/trendradar/ai/test_model_catalog.py`，在文件末尾（`if __name__ == "__main__":` 之前）新增测试类：

```python
class TestModelCatalogCurated(unittest.TestCase):
    def test_list_curated_providers_returns_6_items(self):
        """CURATED_PROVIDERS 列表固定 6 项，按协议家族筛选"""
        from trendradar.ai.model_catalog import ModelCatalog, CURATED_PROVIDERS

        providers = ModelCatalog.list_curated_providers()
        # 6 项硬编码
        self.assertEqual(len(providers), 6)
        # 必须包含的核心 3 项
        for p in ["openai", "anthropic", "gemini"]:
            self.assertIn(p, providers)
        # 顺序固定（用户看到 6 项的固定顺序）
        self.assertEqual(
            providers,
            ["openai", "anthropic", "gemini", "bedrock", "vertex_ai", "azure"],
        )
        # CURATED_PROVIDERS 是个 list
        self.assertIsInstance(CURATED_PROVIDERS, list)
```

### Step 2.2: 跑测试确认失败

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_model_catalog.TestModelCatalogCurated -v 2>&1 | tail -5
```

Expected: FAIL with `ImportError: cannot import name 'CURATED_PROVIDERS'`

### Step 2.3: 在 model_catalog.py 中加 CURATED_PROVIDERS 和 list_curated_providers

打开 `/home/administrator/TrendRadar/trendradar/ai/model_catalog.py`，在文件顶部的 import 后（约 line 19，`FETCH_TIMEOUT = 15` 之前）新增：

```python
# 精简后的 6 项 provider 清单（按协议家族筛选）
# 覆盖 99% 用例：openai 兼容（DeepSeek/Moonshot/MiniMax/Qwen 等）+ Anthropic + Gemini + AWS + Google Cloud + Azure
CURATED_PROVIDERS = [
    "openai",
    "anthropic",
    "gemini",
    "bedrock",
    "vertex_ai",
    "azure",
]
```

在 `ModelCatalog` 类的 `list_providers` 方法（约 line 35）之后新增：

```python
    @staticmethod
    def list_curated_providers() -> List[str]:
        """返回精简后的 6 项 provider 清单（按协议家族筛选）

        与 list_providers() 不同：list_providers 返回 LiteLLM 全部 130+ provider，
        list_curated_providers 仅返回供前端下拉用的 6 项核心 adapter。
        """
        return list(CURATED_PROVIDERS)
```

### Step 2.4: 跑测试确认通过

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_model_catalog -v 2>&1 | tail -20
```

Expected: 14 个测试（13 + 1）全部 PASS

### Step 2.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/model_catalog.py trendradar/ai/test_model_catalog.py
git commit -m "feat(ai): ModelCatalog 新增 CURATED_PROVIDERS 6 项精简清单"
```

---

## Task 3: server.py 端点更新 + config_schema 老格式迁移

**Files:**
- Modify: `trendradar/webui/server.py:225-269`（`_api_post_ai_test` 接收 provider）
- Modify: `trendradar/webui/server.py:335-349`（`_api_post_ai_providers` 返回 6 项）
- Modify: `trendradar/webui/config_schema.py:195-205`（get_default_config 加 ai.provider）
- Modify: `trendradar/webui/config_schema.py:265-320`（load_structured_config 加拆分逻辑）

### Step 3.1: 改 `_api_post_ai_test` 接收 provider

打开 `/home/administrator/TrendRadar/trendradar/webui/server.py`，找到 `_api_post_ai_test`（约 line 225-269），把它替换为：

```python
    def _api_post_ai_test(self):
        """API：测试 AI 模型连通性（使用最小 ping）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 8 * 1024:
                self._send_json(200, {"success": False, "message": "请求体过大（最大 8KB）"})
                return
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(200, {"success": False, "message": f"JSON 解析错误: {e}"})
            return
        except Exception as e:
            self._send_json(200, {"success": False, "message": f"请求解析失败: {e}"})
            return

        provider = (data.get("provider") or "openai").strip()
        model = (data.get("model") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not provider:
            self._send_json(200, {"success": False, "message": "provider 不能为空"})
            return
        if not model:
            self._send_json(200, {"success": False, "message": "model 不能为空"})
            return

        # 防御性：如果 model 仍含 '/'，自动拆分（前端不会产生，仅防老客户端）
        if "/" in model:
            parts = model.split("/", 1)
            if not data.get("provider"):
                provider = parts[0]
            model = parts[1]

        from trendradar.ai.tester import AITester

        try:
            tester = AITester(provider=provider, model=model, api_key=api_key, api_base=api_base)
            ok, message, latency_ms = tester.test()
            self._send_json(200, {
                "success": ok,
                "message": message,
                "latency_ms": latency_ms,
            })
        except Exception as e:
            # 兜底：tester 内部已捕获所有异常，这里只防 import 或非预期崩溃
            self._send_json(200, {
                "success": False,
                "message": f"测试出错: {type(e).__name__}: {str(e)[:200]}",
            })
```

### Step 3.2: 改 `_api_post_ai_providers` 返回 6 项

在 `server.py` 找到 `_api_post_ai_providers`（约 line 335-349），把它替换为：

```python
    def _api_post_ai_providers(self):
        """API：返回精简后的 provider 清单（6 项，按协议家族筛选）

        与 list_providers() 不同：list_providers 返回 LiteLLM 全部 130+ provider，
        list_curated_providers 仅返回供前端下拉用的 6 项核心 adapter。
        """
        try:
            from trendradar.ai.model_catalog import ModelCatalog
            providers = ModelCatalog.list_curated_providers()
            self._send_json(200, {
                "success": True,
                "providers": providers,
            })
        except Exception as e:
            self._send_json(200, {
                "success": False,
                "message": f"加载 provider 列表失败: {type(e).__name__}: {str(e)[:200]}",
                "providers": [],
            })
```

### Step 3.3: 改 `get_default_config` 加 `ai.provider`

打开 `/home/administrator/TrendRadar/trendradar/webui/config_schema.py`，找到 `"ai":` 段（约 line 195），把：

```python
        "ai": {
            "model": "deepseek/deepseek-chat",
            "api_key": "",
```

改为：

```python
        "ai": {
            "provider": "openai",
            "model": "deepseek/deepseek-chat",
            "api_key": "",
```

注：`model` 字段保留旧默认值 `"deepseek/deepseek-chat"` 是为了向后兼容：保存时会一起写出来；加载时会被拆分逻辑自动拆为 `provider=deepseek` + `model=deepseek-chat`。

### Step 3.4: 改 `load_structured_config` 加老格式拆分

打开 `/home/administrator/TrendRadar/trendradar/webui/config_schema.py`，找到 `load_structured_config` 函数末尾（约 line 295-320）：

把：

```python
    # 处理 schedule 段：兼容旧的 cron_schedule，转为 crawl_interval_hours
```

之前的所有逻辑不变。在这段注释之前新增：

```python
    # 处理 ai 段：拆分老格式 "provider/model"（向后兼容）
    if "ai" in result and isinstance(result["ai"], dict):
        ai = result["ai"]
        model = ai.get("model", "")
        # 老格式: "provider/model" + 无 provider 字段 → 拆分
        if isinstance(model, str) and "/" in model and not ai.get("provider"):
            parts = model.split("/", 1)
            ai["provider"] = parts[0]
            ai["model"] = parts[1]
        # 缺失 provider 时默认 openai
        if not ai.get("provider"):
            ai["provider"] = "openai"

```

### Step 3.5: AST 检查

```bash
cd /home/administrator/TrendRadar
python3 -c "import ast; ast.parse(open('trendradar/webui/server.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('trendradar/webui/config_schema.py').read()); print('OK')"
```

Expected: 两个都 `OK`

### Step 3.6: 端到端验证

```bash
cd /home/administrator/TrendRadar
python3 -m trendradar.webui.server 18099 /tmp 2>&1 &
SERVER_PID=$!
sleep 1

# Test 1: /api/ai/providers 返回 6 项
echo "=== /api/ai/providers ==="
curl -s -X POST http://localhost:18099/api/ai/providers -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('count:', len(d.get('providers', []))); print('list:', d.get('providers', []))"
# Expected: success: True, count: 6, list: ['openai', 'anthropic', 'gemini', 'bedrock', 'vertex_ai', 'azure']

# Test 2: /api/ai/test 4 字段（新格式）
echo "=== /api/ai/test new format ==="
curl -s -X POST http://localhost:18099/api/ai/test -H 'Content-Type: application/json' -d '{"provider":"openai","model":"MiniMax-Text-01","api_key":"sk-fake","api_base":"https://api.minimaxi.com/v1"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('msg:', d.get('message'))"
# Expected: success: False, msg: 鉴权失败...

# Test 3: /api/ai/test 老格式（防御性拆分）
echo "=== /api/ai/test legacy format (model='minimax/MiniMax-Text-01', no provider) ==="
curl -s -X POST http://localhost:18099/api/ai/test -H 'Content-Type: application/json' -d '{"model":"minimax/MiniMax-Text-01","api_key":"sk-fake","api_base":"https://api.minimaxi.com/v1"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('msg:', d.get('message'))"
# Expected: success: False, msg: 鉴权失败...（因为自动拆分成 provider=minimax, model=MiniMax-Text-01）

# Test 4: 8KB cap
echo "=== /api/ai/test 8KB cap ==="
LARGE=$(python3 -c "print('{\"provider\":\"openai\",\"model\":\"' + 'a'*9000 + '\",\"api_key\":\"k\",\"api_base\":\"\"}')")
curl -s -X POST http://localhost:18099/api/ai/test -H 'Content-Type: application/json' -d "$LARGE"
echo ""
# Expected: {"success": false, "message": "请求体过大（最大 8KB）"}

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 3.7: 跑全部测试

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_tester trendradar.ai.test_model_catalog 2>&1 | tail -3
```

Expected: 全部 PASS

### Step 3.8: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/server.py trendradar/webui/config_schema.py
git commit -m "feat(webui): /api/ai/test 接收 provider 字段 + 老格式 ai.model 自动拆分

- /api/ai/test: body 改为 {provider, model, api_key, api_base}
  4 字段；model 含 '/' 时防御性自动拆分（兼容老客户端）
- /api/ai/providers: 返回 CURATED_PROVIDERS 6 项精简清单
- config_schema: ai 段加载时拆分老格式 'provider/model'，并默认 provider=openai
- 8KB body cap 保留"
```

---

## Task 4: 前端 UI 重写（HTML + JS）

**Files:**
- Modify: `trendradar/webui/config_page.py`（HTML 6 项硬编码、删 4 个 JS 函数、改 2 个 JS 函数、改加载逻辑）

⚠️ **预存在修改警告**：`config_page.py` 当前有用户预存在的 +190/-58 修改（未提交）。提交时必须用 patch 方式（`git restore` + 重做 Task 3+fix + 重做 Task 4 + 用 `git apply --cached` 只 stage Task 4 改动）。

### Step 4.1: 保存当前文件 + 读取 HEAD 干净版本

```bash
cd /home/administrator/TrendRadar
cp trendradar/webui/config_page.py /tmp/config_page.py.before_task4
git restore --source=HEAD -- trendradar/webui/config_page.py
# 现在 working tree 是干净 HEAD（post-Task-3 fix: 7e1ab5d 等）
# 用 cp 恢复"Task 3 + 预存在 + Task 3 fix"的所有内容
cp /tmp/config_page.py.before_task4 trendradar/webui/config_page.py
# 验证 working tree diff 跟之前一样
git diff --stat -- trendradar/webui/config_page.py
# 应该显示 +190/-58（用户的预存在）+ 我们 Task 3 的 fix（如果存在）
```

### Step 4.2: 改 HTML（AI 模型配置 section 头部）

找到当前 HTML（用 `grep -n "id=\"ai-provider\""` 找行号）：

OLD：
```html
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">Provider</label>
                        <select id="ai-provider" onchange="onProviderChange()">
                            <option value="">加载中...</option>
                        </select>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">模型名称</label>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <select id="ai-model" onchange="updateConfig('ai.model', joinModel())" style="flex: 1;">
                                <option value="">先选 provider</option>
                            </select>
                            <button type="button" class="btn-icon-refresh" id="ai-model-refresh" onclick="refreshAiModels()" title="从 provider API 刷新模型列表">↻</button>
                        </div>
                    </div>
                </div>
```

NEW（用 Edit 工具替换，anchor 为 `onchange="onProviderChange()"` 这一行）：
```html
                <div class="form-row">
                    <div class="form-group half">
                        <label class="form-label">Provider <span class="optional">LiteLLM 协议路由</span></label>
                        <select id="ai-provider" onchange="updateConfig('ai.provider', this.value)">
                            <option value="openai">openai (OpenAI 原生/兼容)</option>
                            <option value="anthropic">anthropic (Anthropic 原生/兼容)</option>
                            <option value="gemini">gemini (Gemini 原生/兼容)</option>
                            <option value="bedrock">bedrock (AWS Bedrock)</option>
                            <option value="vertex_ai">vertex_ai (Google Cloud)</option>
                            <option value="azure">azure (Azure OpenAI)</option>
                        </select>
                    </div>
                    <div class="form-group half">
                        <label class="form-label">模型名称</label>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <select id="ai-model" onchange="updateConfig('ai.model', this.value)" style="flex: 1;">
                                <option value="">点 ↻ 从 api_base 拉取</option>
                            </select>
                            <button type="button" class="btn-icon-refresh" id="ai-model-refresh" onclick="refreshAiModels()" title="从 api_base/models 拉取模型列表（无 api_base 时回退到 LiteLLM catalog）">↻</button>
                        </div>
                    </div>
                </div>
```

### Step 4.3: 删 4 个 JS 函数

用 Edit 工具删除以下函数（每个函数从 `function` / `async function` 关键字到结尾的 `}`，加上中间的空行）：

1. `function joinModel() { ... }` （约 5 行）
2. `function splitModel(s) { ... }` （约 5 行）
3. `async function initAiProviderList() { ... }` （约 24 行）
4. `async function onProviderChange() { ... }` （约 10 行）
5. `let _modelLoadToken = 0;` （单行）

用 Edit 的 `replace_all: false` 逐个删，每个替换为空字符串。

### Step 4.4: 简化 `loadModelsForProvider` → `refreshAiModels`

OLD（当前文件中的版本，约 1482-1505）：
```javascript
        let _modelLoadToken = 0;
        async function onProviderChange() {
            const provider = document.getElementById('ai-provider').value;
            updateConfig('ai.model', joinModel());
            if (!provider) {
                document.getElementById('ai-model').innerHTML = '<option value="">先选 provider</option>';
                return;
            }
            await loadModelsForProvider(provider);
        }

        async function loadModelsForProvider(provider) {
            const sel = document.getElementById('ai-model');
            const prevValue = sel.value;
            const myToken = ++_modelLoadToken;
            sel.innerHTML = '<option value="">加载中...</option>';
            try {
                const res = await fetch('/api/ai/models', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider: provider})
                });
                const data = await res.json();
                if (myToken !== _modelLoadToken) return;
                const models = (data && data.models) || [];
                if (!data.success) {
                    sel.innerHTML = `<option value="">${data.message || '加载失败'}</option>`;
                    return;
                }
                renderModelOptions(models, prevValue);
            } catch (e) {
                if (myToken !== _modelLoadToken) return;
                sel.innerHTML = `<option value="${prevValue}">${prevValue || '加载失败'}</option>`;
            }
        }
```

NEW：
```javascript
        async function refreshAiModels() {
            const provider = document.getElementById('ai-provider').value;
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();
            if (!provider) { showToast('请先选择 Provider', 'error'); return; }

            const btn = document.getElementById('ai-model-refresh');
            const sel = document.getElementById('ai-model');
            const prevValue = sel.value;
            btn.disabled = true;
            sel.innerHTML = '<option value="">拉取中...</option>';

            try {
                const res = await fetch('/api/ai/models', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider, api_key: apiKey, api_base: apiBase})
                });
                const data = await res.json();
                if (data.success) {
                    const models = (data.models || []).slice();
                    // 已保存的 model 若不在列表里，添加为 (已保存) 项
                    if (prevValue && !models.includes(prevValue)) {
                        models.unshift(prevValue);
                    }
                    renderModelOptions(models, prevValue);
                    if (data.provider_error) {
                        showToast('⚠ ' + data.provider_error, 'error');
                    } else if (apiBase) {
                        const added = (data.provider_count || 0);
                        const suffix = added > 0 ? `（+${added} 来自 provider）` : '';
                        showToast(`已加载 ${models.length} 个模型${suffix}`, 'success');
                    } else {
                        showToast(`LiteLLM catalog: ${models.length} 个模型`, 'info');
                    }
                } else {
                    sel.innerHTML = `<option value="${prevValue}">${prevValue || '加载失败'}</option>`;
                    showToast('❌ ' + (data.message || '加载失败'), 'error');
                }
            } catch (e) {
                sel.innerHTML = `<option value="${prevValue}">${prevValue || '加载失败'}</option>`;
                showToast('❌ 网络错误', 'error');
            } finally {
                btn.disabled = false;
            }
        }
```

### Step 4.5: 改写 `testAiConnection`

OLD（当前文件，约 1393-）：
```javascript
        async function testAiConnection() {
            const model = joinModel();
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();

            if (!model) {
                showToast('请先选择 Provider 和模型', 'error');
                return;
            }
```

NEW（前面 4 行替换）：
```javascript
        async function testAiConnection() {
            const provider = document.getElementById('ai-provider').value;
            const model = document.getElementById('ai-model').value;
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();

            if (!provider) { showToast('请先选择 Provider', 'error'); return; }
            if (!model) { showToast('请先选择模型（点 ↻ 拉取）', 'error'); return; }
```

然后把后面 `const res = await fetch('/api/ai/test', {` 那段的 body 改为：

OLD：
```javascript
                    body: JSON.stringify({model: model, api_key: apiKey, api_base: apiBase})
```

NEW：
```javascript
                    body: JSON.stringify({provider, model, api_key: apiKey, api_base: apiBase})
```

### Step 4.6: 改写加载逻辑

OLD（约 line 980-997）：
```javascript
            // Provider + Model 下拉（异步初始化）
            const [savedProvider, savedModel] = splitModel(ai.model || '');
            initAiProviderList().then(() => {
                const pSel = document.getElementById('ai-provider');
                if (savedProvider && [...pSel.options].some(o => o.value === savedProvider)) {
                    pSel.value = savedProvider;
                }
                if (savedProvider) {
                    loadModelsForProvider(savedProvider).then(() => {
                        if (savedModel) {
                            const mSel = document.getElementById('ai-model');
                            // 如果 catalog 不含已保存的 model，添加为 (自定义) 选项
                            if (![...mSel.options].some(o => o.value === savedModel)) {
                                const opt = document.createElement('option');
                                opt.value = savedModel;
                                opt.textContent = `${savedModel} (自定义)`;
                                mSel.insertBefore(opt, mSel.options[1]);
                            }
                            mSel.value = savedModel;
                        }
                    });
                }
            });
```

NEW：
```javascript
            // Provider + Model 下拉（无自动加载，等用户点 ↻）
            const pSel = document.getElementById('ai-provider');
            const mSel = document.getElementById('ai-model');
            if (ai.provider && [...pSel.options].some(o => o.value === ai.provider)) {
                pSel.value = ai.provider;
            } else {
                pSel.value = 'openai';  // 默认
            }
            if (ai.model) {
                mSel.innerHTML = `<option value="${ai.model}">${ai.model} (已保存)</option>`;
                mSel.value = ai.model;
            }
```

### Step 4.7: 静态检查 + 运行测试

```bash
cd /home/administrator/TrendRadar
python3 -c "import ast; ast.parse(open('trendradar/webui/config_page.py').read()); print('OK')"
python3 -m unittest trendradar.ai.test_tester trendradar.ai.test_model_catalog 2>&1 | tail -3
```

Expected: AST OK + 22+ tests pass

### Step 4.8: 验证 working tree diff 大小

```bash
cd /home/administrator/TrendRadar
git diff --stat -- trendradar/webui/config_page.py
# Expected: ~+260/-80 左右（用户的预存在 +190/-58 + Task 4 的 +70/-22 左右）
```

### Step 4.9: 构造 Task 4-only patch 并提交

写一个 `task4.patch` 文件：

```bash
# 找 HEAD 中我们要替换的几个 anchor 位置
git show HEAD:trendradar/webui/config_page.py | grep -n "function joinModel\|function splitModel\|async function initAiProviderList\|async function onProviderChange\|let _modelLoadToken\|async function loadModelsForProvider\|async function testAiConnection\|// Provider + Model 下拉" | head -20
```

用这些行号作为 hunk header 起点。Task 4 的所有变更分散在多个位置（HTML 头部、JS 中间、JS 末尾、加载逻辑），用 4-5 个 hunk 表达。

或者采用之前用过的"用 working tree 全 diff 然后剪掉预存在部分"的方法：

```bash
# 1. 备份当前 working tree（含 Task 4 改动 + 用户预存在）
cp trendradar/webui/config_page.py /tmp/config_page.py.full

# 2. reset 到 HEAD（仅含 Task 3 + 之前所有 fix）
git restore --source=HEAD -- trendradar/webui/config_page.py

# 3. 把 Task 4 改动后的版本（用户的预存在 + Task 3 fix + Task 4）写回
cp /tmp/config_page.py.full trendradar/webui/config_page.py

# 4. 构造全 diff
git diff HEAD -- trendradar/webui/config_page.py > /tmp/full.patch

# 5. 全 diff 中包含：用户的预存在（+190/-58）+ Task 4 改动
#    Task 4 改动的 hunk 行号基于 HEAD 中的位置
#    需要从全 diff 中提取 Task 4 部分的 hunks，去掉预存在部分
#    （预存在的 hunks 行号在 HEAD 中没有对应内容）

# 6. 简化方法：手动写一个 task4_only.patch 文件，包含 5 个 hunk
```

5 个 hunk 的 anchor 行号（在 HEAD post-Task-3 fix 中）：

| Hunk | Anchor 位置 | 变更 |
|---|---|---|
| 1 | HTML form-row | 替换 6 行 HTML |
| 2 | `// === AI 模型下拉相关 ===` 段 | 删 5 个函数（joinModel/splitModel/initAiProviderList/onProviderChange/_modelLoadToken），加新的 refreshAiModels |
| 3 | `async function testAiConnection` | 改 4 行 |
| 4 | 加载逻辑（`// Provider + Model 下拉` 段） | 替换 17 行 |

由于每个 hunk 都需要精确行号，直接写一个完整的 patch 文件会很难。建议用以下技巧：

```bash
# 技巧：先构造一个含所有 Task 4 改动的 .py 文件（base on HEAD + Task 4 改动）
# 然后 diff

# A. 把 working tree 复制为"理想最终态"（预存在 + Task 4）
cp /tmp/config_page.py.full /tmp/config_page.py.target

# B. 从 HEAD 拿"无任何改动"的 base
git show HEAD:trendradar/webui/config_page.py > /tmp/config_page.py.base

# C. 构造"Task 4 only"：从 .target 减去 用户的预存在
#    用户预存在 实际是 .target - .base
#    Task 4 only = .target - 预存在 = .target - (.target - .base) = .base + Task 4
#    但我们没有 .target - 预存在 的对照
#    改用：直接写 Task 4 patch 文件
```

**实际最稳的做法**：用手工 patch 文件，明确 5 个 hunk 的 anchor 行号。先在 HEAD 中找到 anchor：

```bash
git show HEAD:trendradar/webui/config_page.py | grep -n "joinModel\|splitModel\|initAiProviderList\|onProviderChange\|_modelLoadToken\|loadModelsForProvider\|testAiConnection\|Provider + Model 下拉" | head -20
```

得到 anchor 行号后，构造 hunk header `@@ -<line>,<count> +<line>,<count> @@`。每个 hunk 的 count 是 hunk body 中 context + delete + add 的行数。

具体 patch（基于上一步得到的实际行号）：

```python
# 假设 anchor 行号依次为：
# - HTML form-row: line X1
# - // === AI 模型下拉相关 === 段: line X2
# - async function testAiConnection: line X3
# - // Provider + Model 下拉 (异步初始化): line X4
# 实际行号会因 Task 3 fix 位置而变化，需先 grep 确认
```

**简化**（推荐用此法）：构造一个 patch，让 4 个 hunk 中的 delete 段来自 HEAD 的精确字符串，add 段来自 working tree 的新字符串。git apply 会自动找到位置。

```bash
# 生成全 patch
cd /home/administrator/TrendRadar
git diff HEAD -- trendradar/webui/config_page.py > /tmp/full.patch

# 从 /tmp/full.patch 中手工编辑，只保留 4 个 Task 4 改动的 hunk
# 用 sed/awk 切掉预存在的 hunks
# 预存在的 hunks 行号在 HEAD 中找不到（因为预存在代码不在 HEAD）
# 所以 git apply 会自动报错定位
```

或者 **最终方案**（最稳）：让 implementer 工具自处理。直接用 `git add trendradar/webui/config_page.py && git commit`，如果 git 因为"想 commit 工作树所有修改"报错，先用 `git restore` 单独还原预存在那部分（但风险大）。

**推荐**：分两步提交：

```bash
# Step A: 把工作树中"用户的预存在 + Task 3 fix + Task 4 改动"备份到 /tmp
cp /home/administrator/TrendRadar/trendradar/webui/config_page.py /tmp/cp.with_task4.py

# Step B: 还原到 HEAD 干净状态
git restore --source=HEAD -- /home/administrator/TrendRadar/trendradar/webui/config_page.py

# Step C: 在 HEAD 干净版上手动做 Task 4 改动（4.2-4.6 那 4 步），保存到 /tmp/cp.task4.py
# 没法脚本化：用 Edit 工具在 /tmp/cp.task4.py 上做
# 或者直接从 /tmp/cp.with_task4.py 中剥离出 Task 4 改动（diff 预存在 vs with_task4）

# Step D: 复制到 working tree
cp /tmp/cp.task4.py /home/administrator/TrendRadar/trendradar/webui/config_page.py

# Step E: Stage and commit
git add /home/administrator/TrendRadar/trendradar/webui/config_page.py
git commit -m "feat(webui): provider/model 字段重构 - 6 项硬编码 + 4 字段测试"
```

如果 implementer 觉得 (Step A-D) 太复杂，可以采用更简单的"经验证"路径：直接 commit + 接受混合 commit，然后让用户手工用 `git reset --soft HEAD^` + `git reset HEAD trendradar/webui/config_page.py` 拆分。

### Step 4.10: 验证 served HTML

```bash
cd /home/administrator/TrendRadar
python3 -m trendradar.webui.server 18099 /tmp 2>&1 &
SERVER_PID=$!
sleep 1

echo "=== 6 项 provider ==="
curl -s http://localhost:8080/config.html | grep -E "id=\"ai-provider\"|value=\"openai\"|value=\"anthropic\"|value=\"gemini\"|value=\"bedrock\"|value=\"vertex_ai\"|value=\"azure\"" | head -10
# Expected: 看到 6 项 option

echo "=== /api/ai/test 4 字段 ==="
curl -s -X POST http://localhost:8080/api/ai/test -H 'Content-Type: application/json' -d '{"provider":"openai","model":"MiniMax-Text-01","api_key":"sk-fake","api_base":"https://api.minimaxi.com/v1"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('msg:', d.get('message'))"
# Expected: success: False, msg: 鉴权失败...

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 4.11: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/config_page.py
git commit -m "feat(webui): provider/model 字段重构 - 6 项硬编码下拉 + 4 字段测试连接

- Provider 6 项硬编码下拉（openai/anthropic/gemini/bedrock/vertex_ai/azure）
  替代 130+ 列表；onchange 直接写 ai.provider
- 模型下拉默认空（占位 '点 ↻ 从 api_base 拉取'），不自动加载
- 删除 4 个旧函数：joinModel/splitModel/initAiProviderList/onProviderChange
- 简化 refreshAiModels（去掉 race guard，简化为单次拉取）
- testAiConnection 改用 4 字段 {provider, model, api_key, api_base}
- 加载逻辑：savedModel 显示为 '(已保存)' 单选项，不自动拉取
- 解决 provider 在 LiteLLM 中被误用为 adapter 路由键导致选错 client 的 bug"
```

---

## 自审检查清单

执行前确认：

- [x] **Spec 覆盖**：架构（4 task：后端核心 / ModelCatalog / 端点+schema / 前端 UI）→ Task 1/2/3/4
- [x] **AIClient provider 字段**：Task 1
- [x] **AITester provider 参数**：Task 1
- [x] **CURATED_PROVIDERS + list_curated_providers()**：Task 2
- [x] **`/api/ai/test` 接收 4 字段**：Task 3
- [x] **`/api/ai/providers` 返回 6 项**：Task 3
- [x] **config_schema 加载时拆分老格式**：Task 3
- [x] **HTML 6 项硬编码 + 删除 joinModel/splitModel/initAiProviderList/onProviderChange + 简化 refreshAiModels + 改 testAiConnection + 改加载逻辑**：Task 4
- [x] **9 个 test_tester 测试改签名 + 1 个新 test_model_catalog 测试**：Task 1 + Task 2
- [x] **类型一致**：`AITester(provider, model, ...)` 在 Task 1 定义、在 Task 3 端点用
- [x] **API 字段一致**：`{provider, model, api_key, api_base}` 在 Task 1/3/4 处处一致
- [x] **频率提交**：每个 task 末尾 `git commit`，4 个 commit
- [x] **预存在警告**：Task 4 显式标注了预存在工作树的处理方法

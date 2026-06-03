# AI 模型配置 — 两级下拉 + Provider API 刷新 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 AI 模型配置区的手工 `provider/model` 文本输入替换为 provider + model 两级下拉，下拉数据从 LiteLLM catalog + provider API 合并获取，并提供 ↻ 按钮实时从 provider API 刷新。

**Architecture:** 三层：(1) 新建 `trendradar/ai/model_catalog.py` 的 `ModelCatalog` 类，封装 LiteLLM `model_cost` + provider API 合并逻辑；(2) 新增 `POST /api/ai/models` + `POST /api/ai/providers` 两个端点；(3) 前端用两个 `<select>` + 刷新按钮替换 free-text input，复用现有 toast/select 样式。`config schema` 不动，`ai.model` 仍是单字符串。

**Tech Stack:** Python 3.12、`litellm`（已安装，含 `model_cost` / `provider_list`）、`requests`（已在 RSS test 端点用）、stdlib `unittest` + `unittest.mock`、vanilla JS + 现有 CSS 模式。

**Spec:** `docs/superpowers/specs/2026-06-03-ai-config-dropdown-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `trendradar/ai/model_catalog.py` | 新建 | `ModelCatalog` 类 + `ProviderAPIError` 异常；纯逻辑 |
| `trendradar/ai/test_model_catalog.py` | 新建 | `unittest.TestCase` 单测，mock `litellm.model_cost` + `requests.get` |
| `trendradar/webui/server.py` | 修改 | 新增 `_api_post_ai_models()` + `_api_post_ai_providers()` + `do_POST` 注册两个路由 |
| `trendradar/webui/config_page.py` | 修改 | CSS 加 `.btn-icon`；HTML 替换 model 名称 input；JS 加 7 个函数；改 `setInput` 加载逻辑 |

**依赖关系**：Task 1（ModelCatalog）→ Task 2（端点调用它）→ Task 3（前端调用端点）。每 task 独立可验证。

---

## Task 1: 新建 `ModelCatalog` 模块（TDD：12 个单测 + 实现）

**Files:**
- Create: `trendradar/ai/model_catalog.py`
- Create: `trendradar/ai/test_model_catalog.py`

### Step 1.1: 写失败的单测

写入 `trendradar/ai/test_model_catalog.py`：

```python
# coding=utf-8
"""
ModelCatalog 单测

使用 unittest + unittest.mock 隔离 litellm.model_cost 和 requests.get。
"""

import unittest
from unittest.mock import patch, MagicMock

import requests

from litellm.exceptions import APIConnectionError


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, raise_json=False, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self._raise_json = raise_json
        self.text = text

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


class TestModelCatalogProviders(unittest.TestCase):
    def test_list_providers_returns_set_of_slugs(self):
        """list_providers 返回 litellm.provider_list 中所有 slug 的集合"""
        from trendradar.ai.model_catalog import ModelCatalog

        providers = ModelCatalog.list_providers()
        # 至少包含一些知名 provider
        for p in ["openai", "anthropic", "gemini", "deepseek", "minimax"]:
            self.assertIn(p, providers)
        # 是 set 或 list 都可以；只要求可迭代 & 包含上述
        self.assertGreaterEqual(len(providers), 50)


class TestModelCatalogLiteLLMOnly(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_litellm_only_when_no_api_base(self, mock_get):
        """无 api_base → 只返回 LiteLLM catalog 过滤后的列表，不发 HTTP 请求"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {
                "openai/gpt-4o": {"litellm_provider": "openai"},
                "openai/gpt-4o-mini": {"litellm_provider": "openai"},
                "anthropic/claude-3-5-sonnet": {"litellm_provider": "anthropic"},
            },
            clear=False,
        ):
            models = ModelCatalog.get_merged(provider="openai", api_key="", api_base="")

        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4o-mini", models)
        self.assertNotIn("claude-3-5-sonnet", models)
        mock_get.assert_not_called()

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_litellm_only_when_no_api_key(self, mock_get):
        """无 api_key → 不发 HTTP 请求（避免无鉴权调用）"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=False,
        ):
            models = ModelCatalog.get_merged(provider="openai", api_key="", api_base="https://x")

        self.assertIn("gpt-4o", models)
        mock_get.assert_not_called()

    def test_unknown_provider_returns_empty_litellm(self):
        """provider 不在 catalog → 返回空 list（不抛错）"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=False,
        ):
            models = ModelCatalog.get_merged(provider="mycompany-internal", api_key="", api_base="")

        self.assertEqual(models, [])


class TestModelCatalogMerge(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_success_merges_and_dedupes(self, mock_get):
        """provider API 返回的 models 与 LiteLLM 合并去重"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"data": [{"id": "gpt-4o"}, {"id": "gpt-5-new"}]},
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {
                "openai/gpt-4o": {"litellm_provider": "openai"},
                "openai/gpt-4o-mini": {"litellm_provider": "openai"},
            },
            clear=False,
        ):
            models, lite_count, provider_count = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://api.openai.com/v1"
            )

        self.assertEqual(lite_count, 2)
        self.assertEqual(provider_count, 2)
        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4o-mini", models)
        self.assertIn("gpt-5-new", models)
        # 去重：gpt-4o 只出现一次
        self.assertEqual(models.count("gpt-4o"), 1)

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_returns_dotted_ids(self, mock_get):
        """provider API 返回的 id 含 `provider/` 前缀时被切掉"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"data": [{"id": "openai/gpt-4o"}]},
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {},
            clear=False,
        ):
            models, _, provider_count = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://api.openai.com/v1"
            )

        self.assertEqual(provider_count, 1)
        self.assertEqual(models, ["gpt-4o"])

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_non_openai_format_silently_ignored(self, mock_get):
        """body 不是 {data:[...]} 格式 → 静默忽略，不影响 LiteLLM 部分"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"models": ["foo", "bar"]},  # 错误字段名
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=False,
        ):
            models, lite_count, provider_count = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://x"
            )

        self.assertEqual(lite_count, 1)
        self.assertEqual(provider_count, 0)
        self.assertIn("gpt-4o", models)

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_invalid_json_silently_ignored(self, mock_get):
        """200 + 非 JSON body → 静默忽略"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200, raise_json=True, text="<html>not json</html>"
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=False,
        ):
            models, lite_count, provider_count = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://x"
            )

        self.assertEqual(lite_count, 1)
        self.assertEqual(provider_count, 0)
        self.assertIn("gpt-4o", models)


class TestModelCatalogErrors(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_401_message(self, mock_get):
        """401 → 抛 ProviderAPIError 含鉴权提示"""
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.return_value = FakeResponse(status_code=401, text="Unauthorized")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="bad", api_base="https://x"
            )
        self.assertIn("鉴权失败", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_404_message(self, mock_get):
        """404 → ProviderAPIError 含"不支持 /models 端点" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.return_value = FakeResponse(status_code=404, text="Not Found")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="custom", api_key="k", api_base="https://x"
            )
        self.assertIn("/models 端点", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_timeout_message(self, mock_get):
        """Timeout → ProviderAPIError 含"请求 provider 超时" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.side_effect = requests.Timeout("timed out")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="k", api_base="https://x"
            )
        self.assertIn("超时", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_connection_error_message(self, mock_get):
        """ConnectionError → ProviderAPIError 含"网络连接失败" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.side_effect = requests.ConnectionError("dns fail")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="k", api_base="https://x"
            )
        self.assertIn("网络连接失败", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

### Step 1.2: 跑测试确认失败

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_model_catalog -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'trendradar.ai.model_catalog'`

### Step 1.3: 实现 `ModelCatalog`

写入 `trendradar/ai/model_catalog.py`：

```python
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
    def get_merged(provider: str, api_key: str = "", api_base: str = "") -> List[str]:
        """
        返回 provider 的合并模型列表（去重、按字母序）。
        详细统计请用 get_merged_with_counts。
        """
        models, _, _ = ModelCatalog.get_merged_with_counts(provider, api_key, api_base)
        return models

    @staticmethod
    def get_merged_with_counts(
        provider: str, api_key: str = "", api_base: str = ""
    ) -> Tuple[List[str], int, int]:
        """
        返回 (models, lite_count, provider_count)。

        - lite_count：来自 LiteLLM catalog 的模型数
        - provider_count：来自 provider API 的新模型数（不含已在 LiteLLM 中的）
        """
        # 1. 从 LiteLLM catalog 过滤
        lite_models = ModelCatalog._from_litellm(provider)
        lite_set = set(lite_models)

        # 2. 尝试从 provider API 拉
        provider_models: List[str] = []
        if api_base and api_key:
            try:
                provider_models = ModelCatalog._fetch_provider_models(
                    provider=provider, api_key=api_key, api_base=api_base
                )
            except ProviderAPIError:
                # 失败不影响 LiteLLM 部分
                pass

        # 3. 合并去重，LiteLLM 在前
        seen = set(lite_models)
        merged = list(lite_models)
        new_from_provider = 0
        for m in provider_models:
            if m not in seen:
                merged.append(m)
                seen.add(m)
                new_from_provider += 1

        # 4. 排序（保留主列表顺序，但内部稳定排序）
        merged_sorted = sorted(set(merged), key=lambda x: x.lower())
        return merged_sorted, len(lite_models), new_from_provider

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
        except requests.ConnectionError as e:
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
```

### Step 1.4: 跑测试确认通过

```bash
cd /home/administrator/TrendRadar
python3 -m unittest trendradar.ai.test_model_catalog -v 2>&1 | tail -25
```

Expected: 12 个 test_xxx 全部 PASS，OK 12 / FAILED 0。

### Step 1.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/model_catalog.py trendradar/ai/test_model_catalog.py
git commit -m "feat(ai): 新增 ModelCatalog 模块 - LiteLLM + provider API 合并"
```

---

## Task 2: 注册 HTTP 端点 `/api/ai/models` + `/api/ai/providers`

**Files:**
- Modify: `trendradar/webui/server.py:97-100`（在 `do_POST` 增加两个路由分支）
- Modify: `trendradar/webui/server.py:265`（在 `_api_post_ai_test` 之后新增两个方法）

### Step 2.1: 在 `do_POST` 增加路由分支

打开 `trendradar/webui/server.py`，找到 `do_POST` 方法中已有的 `/api/ai/test` 行（~line 95-96）。在它之后插入两行：

OLD：
```python
        elif path == "/api/ai/test":
            self._api_post_ai_test()
        else:
```

NEW：
```python
        elif path == "/api/ai/test":
            self._api_post_ai_test()
        elif path == "/api/ai/models":
            self._api_post_ai_models()
        elif path == "/api/ai/providers":
            self._api_post_ai_providers()
        else:
```

### Step 2.2: 新增 `_api_post_ai_models` 方法

在 `_api_post_ai_test` 之后插入新方法。找到 `_api_post_ai_test` 结尾：

```python
        except Exception as e:
            # 兜底：tester 内部已捕获所有异常，这里只防 import 或非预期崩溃
            self._send_json(200, {
                "success": False,
                "message": f"测试出错: {type(e).__name__}: {str(e)[:200]}",
            })

    def _api_get_tags(self):
```

把 `测试出错...` 那个 `except` 块后面、`def _api_get_tags(self):` 前面，插入两个新方法：

```python
    def _api_post_ai_models(self):
        """API：返回 provider 的模型清单（LiteLLM catalog + provider API 合并）"""
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

        provider = (data.get("provider") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not provider:
            self._send_json(200, {"success": False, "message": "provider 不能为空"})
            return

        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        try:
            models, lite_count, provider_count = ModelCatalog.get_merged_with_counts(
                provider=provider, api_key=api_key, api_base=api_base
            )
            import time
            self._send_json(200, {
                "success": True,
                "models": models,
                "lite_count": lite_count,
                "provider_count": provider_count,
                "fetched_at": int(time.time()),
            })
        except ProviderAPIError as e:
            self._send_json(200, {
                "success": False,
                "message": e.user_message,
                "models": [],
            })
        except Exception as e:
            self._send_json(200, {
                "success": False,
                "message": f"查询出错: {type(e).__name__}: {str(e)[:200]}",
                "models": [],
            })

    def _api_post_ai_providers(self):
        """API：返回 LiteLLM 支持的所有 provider slug 列表"""
        try:
            from trendradar.ai.model_catalog import ModelCatalog
            providers = sorted(ModelCatalog.list_providers())
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

    def _api_get_tags(self):
```

### Step 2.3: 语法检查

```bash
cd /home/administrator/TrendRadar
python3 -c "import ast; ast.parse(open('trendradar/webui/server.py').read()); print('OK')"
```

Expected: `OK`

### Step 2.4: 端到端验证

```bash
cd /home/administrator/TrendRadar
python3 -m trendradar.webui.server 18099 /tmp 2>&1 &
SERVER_PID=$!
sleep 1

# Test 1: providers 列表
curl -s -X POST http://localhost:18099/api/ai/providers \
  -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('count:', len(d.get('providers', []))); print('sample:', d.get('providers', [])[:5])"
# Expected: success: True, count: 100+, sample: ['some', 'slugs', ...]

# Test 2: 空 provider → 400-style error
curl -s -X POST http://localhost:18099/api/ai/models \
  -H 'Content-Type: application/json' -d '{"provider": ""}'
# Expected: {"success": false, "message": "provider 不能为空", ...}

# Test 3: 已知 provider，无 api_key/api_base → 只返回 LiteLLM catalog
curl -s -X POST http://localhost:18099/api/ai/models \
  -H 'Content-Type: application/json' -d '{"provider": "openai"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('count:', len(d.get('models', []))); print('sample:', d.get('models', [])[:5])"
# Expected: success: True, count: N (N >= 10), sample: ['gpt-4o', 'gpt-4o-mini', ...]

# Test 4: 真实 provider API（用真 deepseek key 测；不指定 = 触发真实网络）
# 跳过此测试如果不在线
# curl -s --max-time 20 -X POST http://localhost:18099/api/ai/models \
#   -H 'Content-Type: application/json' \
#   -d '{"provider":"deepseek","api_key":"sk-real","api_base":"https://api.deepseek.com/v1"}'
# Expected: success: True, models: [...], provider_count: M

# Test 5: 假 host → 触发 connection error
curl -s -X POST http://localhost:18099/api/ai/models \
  -H 'Content-Type: application/json' \
  -d '{"provider":"x","api_key":"k","api_base":"https://this-host-does-not-exist-xyz123.invalid/v1"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('success:', d['success']); print('message:', d.get('message'))"
# Expected: success: False, message 含"网络连接失败"

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 2.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/server.py
git commit -m "feat(webui): 新增 /api/ai/models 和 /api/ai/providers 端点"
```

---

## Task 3: 替换 UI 为两级下拉 + 刷新按钮

**Files:**
- Modify: `trendradar/webui/config_page.py`（CSS 加 `.btn-icon`、HTML 替换 input、JS 加 7 个函数、改 `setInput` 加载逻辑）

### Step 3.1: 加 CSS `.btn-icon`

在 `config_page.py` 的 `<style>` 块中，找到合适的插入点（紧挨着 `.rss-test-status` 系列样式的下方，约 line 273 附近）。在 `.toast.info` 之前或之后插入：

```css
        .btn-icon {
            width: 28px; height: 28px; padding: 0;
            border-radius: 6px; font-size: 14px;
            background: #f3f4f6; border: 1px solid #e5e5e5;
            cursor: pointer;
            display: inline-flex; align-items: center; justify-content: center;
        }
        .btn-icon:hover { background: #e5e7eb; }
        .btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }
```

### Step 3.2: HTML 替换

打开 `config_page.py` 找到 AI 模型配置 section 的"模型名称"行（约 line 380-383，结构：

```html
                <div class="form-row">
                    <div class="form-group full">
                        <label class="form-label">模型名称 <span class="optional">格式: provider/model_name</span></label>
                        <input type="text" id="ai-model" placeholder="deepseek/deepseek-chat"
                            onchange="updateConfig('ai.model', this.value)">
                    </div>
                </div>
```

把整个 form-row 替换为：

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
                            <button type="button" class="btn-icon" id="ai-model-refresh" onclick="refreshAiModels()" title="从 provider API 刷新模型列表">↻</button>
                        </div>
                    </div>
                </div>
```

### Step 3.3: JS 函数追加

找到 `testAiConnection` 函数结尾（约 line 1400，`}` 之后空行）。在它之后、`// 显示区域` 注释之前，插入以下 7 个函数：

```javascript
        // === AI 模型下拉相关 ===

        function joinModel() {
            const p = document.getElementById('ai-provider').value;
            const m = document.getElementById('ai-model').value;
            return p && m ? `${p}/${m}` : '';
        }

        function splitModel(s) {
            if (!s || !s.includes('/')) return ['', s || ''];
            const idx = s.indexOf('/');
            return [s.substring(0, idx), s.substring(idx + 1)];
        }

        async function initAiProviderList() {
            try {
                const res = await fetch('/api/ai/providers');
                const data = await res.json();
                const sel = document.getElementById('ai-provider');
                if (!data.success) {
                    sel.innerHTML = '<option value="">加载失败</option>';
                    return;
                }
                const top = ['openai','anthropic','gemini','deepseek','minimax','qwen','moonshot','mistral','xai','groq'];
                const all = data.providers;
                const topInAll = top.filter(p => all.includes(p));
                const rest = all.filter(p => !topInAll.includes(p)).sort();
                const ordered = [...topInAll, ...rest];
                sel.innerHTML = '<option value="">-- 请选择 --</option>' +
                    ordered.map(p => `<option value="${p}">${p}</option>`).join('');
            } catch (e) {
                document.getElementById('ai-provider').innerHTML = '<option value="">加载失败</option>';
            }
        }

        async function onProviderChange() {
            const provider = document.getElementById('ai-provider').value;
            updateConfig('ai.model', joinModel());
            if (!provider) return;
            await loadModelsForProvider(provider, /* preserveCurrent */ true);
        }

        async function loadModelsForProvider(provider, preserveCurrent) {
            const sel = document.getElementById('ai-model');
            sel.innerHTML = '<option value="">加载中...</option>';
            try {
                const res = await fetch('/api/ai/models', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider: provider})
                });
                const data = await res.json();
                if (!data.success) {
                    sel.innerHTML = `<option value="">${data.message || '加载失败'}</option>`;
                    return;
                }
                renderModelOptions(data.models, preserveCurrent);
            } catch (e) {
                sel.innerHTML = '<option value="">网络错误</option>';
            }
        }

        async function refreshAiModels() {
            const provider = document.getElementById('ai-provider').value;
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();
            if (!provider) { showToast('请先选择 Provider', 'error'); return; }
            if (!apiBase) { showToast('请先填写 API 基础地址', 'error'); return; }

            const btn = document.getElementById('ai-model-refresh');
            const sel = document.getElementById('ai-model');
            const prevValue = sel.value;
            btn.disabled = true;
            sel.innerHTML = '<option value="">刷新中...</option>';

            try {
                const res = await fetch('/api/ai/models', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({provider, api_key: apiKey, api_base: apiBase})
                });
                const data = await res.json();
                if (data.success) {
                    renderModelOptions(data.models, /* preserve */ false);
                    sel.value = prevValue;
                    const added = (data.provider_count || 0);
                    const suffix = added > 0 ? `（+${added} 来自 provider）` : '';
                    showToast(`已刷新 ${data.models.length} 个模型${suffix}`, 'success');
                } else {
                    sel.innerHTML = `<option value="${prevValue}">${prevValue}</option>`;
                    showToast('❌ ' + (data.message || '刷新失败'), 'error');
                }
            } catch (e) {
                sel.innerHTML = `<option value="${prevValue}">${prevValue}</option>`;
                showToast('❌ 网络错误', 'error');
            } finally {
                btn.disabled = false;
            }
        }

        function renderModelOptions(models, preserveCurrent) {
            const sel = document.getElementById('ai-model');
            const currentVal = preserveCurrent ? sel.value : '';
            const opts = ['<option value="">-- 请选择 --</option>']
                .concat(models.map(m => `<option value="${m}">${m}</option>`));
            if (currentVal && !models.includes(currentVal)) {
                opts.splice(1, 0, `<option value="${currentVal}">${currentVal} (自定义)</option>`);
            }
            sel.innerHTML = opts.join('');
            if (currentVal) sel.value = currentVal;
        }
```

### Step 3.4: 改 setInput 加载逻辑

找到 `setInput('ai-model', ai.model);` 这一行（~line 952）。把这一行**和它前面相关的代码**一起替换。

OLD（从 `// AI` 注释开始到 `setInput('ai-num-retries', ...);` 行结束）：

```javascript
            // AI
            const ai = getValue('ai') || {};
            setInput('ai-model', ai.model);
            setInput('ai-api-key', ai.api_key);
            setInput('ai-api-base', ai.api_base);
            setInput('ai-timeout', ai.timeout);
            setInput('ai-temperature', ai.temperature);
            setInput('ai-max-tokens', ai.max_tokens);
            setInput('ai-num-retries', ai.num_retries);
```

NEW：

```javascript
            // AI
            const ai = getValue('ai') || {};
            setInput('ai-api-key', ai.api_key);
            setInput('ai-api-base', ai.api_base);
            setInput('ai-timeout', ai.timeout);
            setInput('ai-temperature', ai.temperature);
            setInput('ai-max-tokens', ai.max_tokens);
            setInput('ai-num-retries', ai.num_retries);

            // Provider + Model 下拉（异步初始化）
            const [savedProvider, savedModel] = splitModel(ai.model || '');
            initAiProviderList().then(() => {
                const pSel = document.getElementById('ai-provider');
                if (savedProvider && [...pSel.options].some(o => o.value === savedProvider)) {
                    pSel.value = savedProvider;
                }
                if (savedProvider) {
                    loadModelsForProvider(savedProvider, /* preserve */ true).then(() => {
                        if (savedModel) {
                            const mSel = document.getElementById('ai-model');
                            if ([...mSel.options].some(o => o.value === savedModel)) {
                                mSel.value = savedModel;
                            }
                        }
                    });
                }
            });
```

### Step 3.5: 静态检查

```bash
cd /home/administrator/TrendRadar
python3 -c "import ast; ast.parse(open('trendradar/webui/config_page.py').read()); print('OK')"
```

Expected: `OK`

### Step 3.6: Curl 验证 served HTML

```bash
cd /home/administrator/TrendRadar
python3 -m trendradar.webui.server 18099 /tmp &
SERVER_PID=$!
sleep 1

# 1. 页面加载
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:18099/config.html
# Expected: 200

# 2. 新元素都存在
curl -s http://localhost:18099/config.html | grep -E 'id="ai-provider"|id="ai-model"|id="ai-model-refresh"|initAiProviderList|refreshAiModels|joinModel\(\)|onProviderChange' | head -10
# Expected: 至少 7 行匹配

# 3. 端点联通
curl -s -X POST http://localhost:18099/api/ai/providers -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('providers ok:', d['success'], 'count:', len(d.get('providers', [])))"

curl -s -X POST http://localhost:18099/api/ai/models -H 'Content-Type: application/json' -d '{"provider":"openai"}' | python3 -c "import sys, json; d=json.load(sys.stdin); print('models ok:', d['success'], 'count:', len(d.get('models', [])))"

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 3.7: 浏览器手动冒烟

启动 server 并打开浏览器：

```bash
cd /home/administrator/TrendRadar
python3 -m trendradar.webui.server 18099 /tmp &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
echo "打开浏览器: http://localhost:18099/config.html"
```

逐项验证：
- [ ] 切到 AI 模型 Tab，provider 下拉显示 "加载中..." → 然后填入 100+ provider
- [ ] 常用 provider（openai/anthropic/gemini/deepseek/minimax/qwen/moonshot/mistral/xai/groq）排在前面
- [ ] 选 `minimax` → model 下拉自动加载 minimax 模型列表；之前保存的 `MiniMax-Text-01` 标选中
- [ ] 选 `openai` → model 下拉显示 gpt-4o / gpt-4o-mini 等
- [ ] 已选 minimax + MiniMax-Text-01；点 ↻ → "刷新中..." → 成功 toast "已刷新 N 个模型"
- [ ] 改 api_base 为 `https://wrong.host.invalid` → 点 ↻ → toast "网络连接失败..."
- [ ] 留空 api_base → 点 ↻ → toast "请先填写 API 基础地址"
- [ ] 切换 provider 后 model 跟着重载
- [ ] 保存后 `ai.model` 在 config 中是 `provider/model` 格式

```bash
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 3.8: 提交

⚠️ **重要**：提交前先确认 `config_page.py` 工作树里只有你这次的改动（不要混入用户的预存在修改）。

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/config_page.py
git diff --cached --stat
# 期望：只显示 config_page.py，且行数 ~+200 / -<10>
# 如果行数远大于此，先检查并用 git reset + git apply --cached patch 方式提交

git commit -m "feat(webui): AI 模型配置 - 改为 provider + model 两级下拉 + 刷新按钮"
```

如果 `git diff --cached --stat` 显示的行数远超预期（混入用户预存在工作），参考 docs/superpowers/plans/ 之前的 3367029 事故处理方式：构造 patch 文件，只 `git apply --cached` 本 task 的改动。

---

## 自审检查清单

执行前确认：

- [x] **Spec 覆盖**：架构（ModelCatalog + 端点 + UI）→ Task 1/2/3；12 个单测 → Task 1；6 项冒烟清单 → Task 3.7
- [x] **无 placeholder**：每个 step 有完整代码或精确命令
- [x] **类型一致**：`ModelCatalog.get_merged_with_counts()` 返回 `Tuple[List[str], int, int]` 在 Task 1 定义、在 Task 2 使用
- [x] **API 字段一致**：`{provider, api_key, api_base}` 在 spec、Task 1 实现、Task 2 端点、Task 3 前端四处一致
- [x] **错误归一**：`ProviderAPIError.user_message` 在 Task 1 的 6 种异常中归一，在 Task 2 端点透传给前端
- [x] **CSS 复用**：仅新增 `.btn-icon` 一条；其他复用现有 select 样式
- [x] **频率提交**：每个 task 末尾 `git commit`，3 个 commit

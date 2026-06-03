# AI 模型配置 — 测试连接按钮 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 WebUI 的"AI 模型配置"区增加一个"测试连接"按钮，使用当前未保存的输入值直接 ping 模型并把结果反馈给用户。

**Architecture:** 三层：前端读 DOM → POST `/api/ai/test` → 新建 `trendradar/ai/tester.py` 的 `AITester.test()` 用 LiteLLM 发 `max_tokens=1` 的最小 ping。复用现有 RSS test 端点的请求/响应/前端样式风格，保持代码风格统一。

**Tech Stack:** Python 3.12、`litellm`（已安装）、`http.server`（已有）、项目内单测用 stdlib `unittest` + `unittest.mock`、前端 vanilla JS 复用现有 `.rss-test-status` CSS。

**Spec:** `docs/superpowers/specs/2026-06-03-ai-config-test-button-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `trendradar/ai/tester.py` | 新建 | `AITester` 类 + `_friendly_message` 异常归一；纯逻辑 |
| `trendradar/ai/test_tester.py` | 新建 | `unittest.TestCase` 单测，mock `litellm.completion` |
| `trendradar/webui/server.py` | 修改 | 新增 `_api_post_ai_test()` + `do_POST` 注册 `/api/ai/test` |
| `trendradar/webui/config_page.py` | 修改 | 在 AI 模型配置 section 尾部加 HTML 按钮/状态 span；新增 `testAiConnection()` JS |

**没有依赖关系**：
- `tester.py` 不依赖 `AIClient`（独立小类）
- `server.py` 的端点只依赖 `tester.AITester`
- 前端只读 DOM、只调新端点；不读 config 对象、不写 config 对象

---

## Task 1: 新建 `AITester` 类（TDD：7 个单测 + 实现）

**Files:**
- Create: `trendradar/ai/tester.py`
- Create: `trendradar/ai/test_tester.py`

### Step 1.1: 写失败的单测

写入 `trendradar/ai/test_tester.py`：

```python
# coding=utf-8
"""
AITester 单测

使用 unittest + unittest.mock 隔离 litellm.completion 的真实网络调用。
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from litellm import APIConnectionError, AuthenticationError, NotFoundError, Timeout


class FakeMessage:
    def __init__(self, content="hi"):
        self.content = content


class FakeChoice:
    def __init__(self, content="hi"):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content="hi", choices=None):
        self.choices = choices if choices is not None else [FakeChoice(content)]


class TestAITesterSuccess(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_success_returns_ok_and_message(self, mock_completion):
        """成功路径：返回 (True, "连接成功", latency_ms>0)"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse(content="hi")
        tester = AITester(model="deepseek/deepseek-chat", api_key="sk-test", api_base="")
        ok, message, latency = tester.test()

        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")
        self.assertIsInstance(latency, int)
        self.assertGreaterEqual(latency, 0)

    @patch("trendradar.ai.tester.completion")
    def test_success_passes_minimal_ping(self, mock_completion):
        """成功路径：传给 completion 的参数是最小 ping"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(model="openai/gpt-4o-mini", api_key="sk-x", api_base="")
        tester.test()

        call = mock_completion.call_args
        params = call.kwargs
        self.assertEqual(params["model"], "openai/gpt-4o-mini")
        self.assertEqual(params["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(params["max_tokens"], 1)
        self.assertEqual(params["num_retries"], 0)
        self.assertEqual(params["timeout"], 30)
        self.assertEqual(params["api_key"], "sk-x")
        self.assertNotIn("api_base", params)


class TestAITesterOptionalFields(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_no_api_key_no_base_does_not_pass_them(self, mock_completion):
        """空 api_key/api_base：params 中不应含这两个键"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(model="x/y", api_key="", api_base="")
        tester.test()

        params = mock_completion.call_args.kwargs
        self.assertNotIn("api_key", params)
        self.assertNotIn("api_base", params)

    @patch("trendradar.ai.tester.completion")
    def test_with_api_base_passes_it(self, mock_completion):
        """非空 api_base：应传 api_base 参数"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(
            model="x/y", api_key="sk-x", api_base="https://api.example.com/v1"
        )
        tester.test()

        params = mock_completion.call_args.kwargs
        self.assertEqual(params["api_base"], "https://api.example.com/v1")


class TestAITesterErrors(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_auth_error_message(self, mock_completion):
        """鉴权失败：message 包含"鉴权失败" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = AuthenticationError(
            message="invalid api key", llm_provider="openai", model="x/y"
        )
        tester = AITester(model="x/y", api_key="bad", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("鉴权失败", message)

    @patch("trendradar.ai.tester.completion")
    def test_not_found_message(self, mock_completion):
        """模型不存在：message 包含"模型不存在" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = NotFoundError(
            message="model not found", llm_provider="openai", model="bad/name"
        )
        tester = AITester(model="bad/name", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("模型不存在", message)

    @patch("trendradar.ai.tester.completion")
    def test_timeout_message(self, mock_completion):
        """超时：message 包含"请求超时（30s）" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = Timeout(
            message="timed out", llm_provider="openai", model="x/y"
        )
        tester = AITester(model="x/y", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("请求超时（30s）", message)

    @patch("trendradar.ai.tester.completion")
    def test_empty_choices_message(self, mock_completion):
        """模型返回空 choices：message 是"模型返回空响应" """
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse(choices=[])
        tester = AITester(model="x/y", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertEqual(message, "模型返回空响应")


if __name__ == "__main__":
    unittest.main()
```

### Step 1.2: 跑测试确认失败

```bash
cd /home/administrator/TrendRadar
python -m unittest trendradar.ai.test_tester -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'trendradar.ai.tester'`

### Step 1.3: 实现 AITester

写入 `trendradar/ai/tester.py`：

```python
# coding=utf-8
"""
AI 模型连通性测试模块

最小 ping：用 LiteLLM 同步 completion() 发送 "hi" + max_tokens=1，
独立于 AIClient 业务调用链，避免被业务默认 timeout/重试拖慢反馈。
"""

import time
from typing import Optional, Tuple

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
        api_key: str = "",
        api_base: str = "",
        timeout: int = PING_TIMEOUT,
    ):
        self.model = model
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
                "model": self.model,
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


def _friendly_message(exc: Exception, model: str, api_base: str) -> str:
    """
    把 LiteLLM/网络/未知异常归一为用户可读的中文短句。

    优先级：鉴权 > 模型不存在 > 超时 > 网络 > 其它
    """
    if isinstance(exc, AuthenticationError):
        return "鉴权失败：API Key 无效或已过期"
    if isinstance(exc, NotFoundError):
        return f"模型不存在：{model}"
    if isinstance(exc, Timeout):
        return f"请求超时（{AITester.PING_TIMEOUT}s）"
    if isinstance(exc, APIConnectionError):
        host = api_base or "默认端点"
        return f"网络连接失败：{host}"
    # 其它异常（如 RateLimitError、ServiceUnavailableError、未分类）
    raw = str(exc).strip() or exc.__class__.__name__
    return f"测试失败: {type(exc).__name__}: {raw[:200]}"
```

### Step 1.4: 跑测试确认通过

```bash
cd /home/administrator/TrendRadar
python -m unittest trendradar.ai.test_tester -v 2>&1 | tail -20
```

Expected: 7 个 test_xxx 全部 PASS，OK 7 / FAILED 0。

> 注意：`Timeout` 在新版 litellm 可能是 `litellm.Timeout`（模块属性）或 `litellm.exceptions.Timeout`（异常类）。Step 1.1 已 import `from litellm import Timeout`，与实现端 `from litellm.exceptions import Timeout` 同源，都是 `litellm.Timeout`，无需改。

### Step 1.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/tester.py trendradar/ai/test_tester.py
git commit -m "feat(ai): 新增 AITester 模块 - 同步 ping 模型连通性"
```

---

## Task 2: 注册 HTTP 端点 `/api/ai/test`

**Files:**
- Modify: `trendradar/webui/server.py:97-100`（在 `do_POST` 增加路由分支）
- Modify: `trendradar/webui/server.py:577`（在 `_api_post_rss_test` 之后新增 `_api_post_ai_test`）

### Step 2.1: 在 `do_POST` 增加 `/api/ai/test` 路由分支

打开 `trendradar/webui/server.py`，找到 `do_POST` 方法（约 line 84-100）：

```python
    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            self._api_post_config()
        elif path == "/api/tags/preview":
            self._api_post_tags_preview()
        elif path == "/api/trigger":
            self._api_trigger_crawl()
        elif path == "/api/regenerate-report":
            self._api_regenerate_report()
        elif path == "/api/rss/test":
            self._api_post_rss_test()
        else:
            self._send_json(404, {"success": False, "message": "Not found"})
```

把 `elif path == "/api/rss/test":` 这一行替换为：

```python
        elif path == "/api/rss/test":
            self._api_post_rss_test()
        elif path == "/api/ai/test":
            self._api_post_ai_test()
```

### Step 2.2: 新增 `_api_post_ai_test` 方法

在 `_api_post_rss_test` 方法结尾（约 line 577，`_api_get_tags` 之前），在其后插入新方法。找到这段：

```python
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"测试出错: {e}"})

    def _api_get_tags(self):
```

把这段替换为：

```python
        except Exception as e:
            self._send_json(500, {"success": False, "message": f"测试出错: {e}"})

    def _api_post_ai_test(self):
        """API：测试 AI 模型连通性（使用最小 ping）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(200, {"success": False, "message": f"JSON 解析错误: {e}"})
            return
        except Exception as e:
            self._send_json(200, {"success": False, "message": f"请求解析失败: {e}"})
            return

        model = (data.get("model") or "").strip()
        api_key = (data.get("api_key") or "").strip()
        api_base = (data.get("api_base") or "").strip()

        if not model:
            self._send_json(200, {"success": False, "message": "模型名称不能为空"})
            return
        if "/" not in model:
            self._send_json(200, {
                "success": False,
                "message": "模型格式错误，应为 'provider/model' 格式",
            })
            return

        from trendradar.ai.tester import AITester

        try:
            tester = AITester(model=model, api_key=api_key, api_base=api_base)
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

    def _api_get_tags(self):
```

### Step 2.3: 语法/导入 sanity 检查

```bash
cd /home/administrator/TrendRadar
python -c "import ast; ast.parse(open('trendradar/webui/server.py').read()); print('OK')"
```

Expected: `OK`

### Step 2.4: 手动验证端点（不需要真实模型，可验证 JSON 解析与基础校验）

```bash
cd /home/administrator/TrendRadar
# 启动 server（用 /tmp 作为文档根避免依赖 /app）
python -m trendradar.webui.server 18099 /tmp 2>&1 &
SERVER_PID=$!
sleep 1

# 测试 1: 空 model → 应返回 success=false, message 包含"模型名称不能为空"
curl -s -X POST http://localhost:18099/api/ai/test \
  -H 'Content-Type: application/json' \
  -d '{"model":"","api_key":"","api_base":""}'
# Expected: {"success": false, "message": "模型名称不能为空", ...}

# 测试 2: model 不含 / → 应返回 success=false
curl -s -X POST http://localhost:18099/api/ai/test \
  -H 'Content-Type: application/json' \
  -d '{"model":"badname","api_key":"","api_base":""}'
# Expected: {"success": false, "message": "模型格式错误，应为 'provider/model' 格式", ...}

# 测试 3: 真实 ping（用 deepseek + 假 key 测，会得到鉴权失败，但路径走通）
#   这一步需要真实网络，可能慢，按 Ctrl+C 中断
curl -s --max-time 60 -X POST http://localhost:18099/api/ai/test \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek/deepseek-chat","api_key":"sk-fake","api_base":""}'
# Expected: {"success": false, "message": "鉴权失败...", "latency_ms": ...}
#   （如果断网则可能是 "网络连接失败..." 或 "请求超时..."）

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

> 真实网络测试需要外网，若 sandbox 不通外网，跳过测试 3 也可；前两个测试已覆盖"路由 + 基础校验 + JSON 解析"。

### Step 2.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/server.py
git commit -m "feat(webui): 新增 POST /api/ai/test 端点 - 测试 AI 模型连通性"
```

---

## Task 3: 在配置页加"测试连接"按钮 + JS

**Files:**
- Modify: `trendradar/webui/config_page.py:468-469`（HTML 插入）
- Modify: `trendradar/webui/config_page.py:1350`（JS 函数追加）

### Step 3.1: 插入 HTML 按钮

打开 `trendradar/webui/config_page.py`，找到 AI 模型配置 section 的尾部（约 line 467-469）：

```python
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">重试次数</label>
                        <input type="number" id="ai-num-retries" min="0" max="10"
                            onchange="updateConfig('ai.num_retries', parseInt(this.value)||1)">
                    </div>
                </div>
            </div>
```

把 `</div>\n            </div>` （结束 form-row 的 div + 结束 section 的 div）替换为：

```python
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <button class="btn btn-sm btn-secondary" id="ai-test-btn" onclick="testAiConnection()">测试连接</button>
                        <span id="ai-test-status" class="rss-test-status"></span>
                        <span class="optional" style="margin-left: 8px;">使用当前填写的值，不会保存</span>
                    </div>
                </div>
            </div>
```

> 缩进：4 个空格的层级。这里插入了一个完整的 form-row，与上一段 form-row 平级。

### Step 3.2: 追加 `testAiConnection` JS 函数

找到 `testRssConnectivity` 函数结尾（约 line 1350，`}` 之后空行）：

```javascript
        async function testRssConnectivity(index) {
            ...
            } finally {
                btn.disabled = false;
            }
        }

        // 显示区域
```

把 `}\n\n        // 显示区域` 替换为：

```javascript
        }

        async function testAiConnection() {
            const model = document.getElementById('ai-model').value.trim();
            const apiKey = document.getElementById('ai-api-key').value.trim();
            const apiBase = document.getElementById('ai-api-base').value.trim();

            if (!model) {
                showToast('请先填写模型名称', 'error');
                return;
            }
            if (!model.includes('/')) {
                showToast('模型格式应为 provider/model（例如 deepseek/deepseek-chat）', 'error');
                return;
            }

            const btn = document.getElementById('ai-test-btn');
            const statusEl = document.getElementById('ai-test-status');
            btn.disabled = true;
            statusEl.textContent = '测试中...';
            statusEl.className = 'rss-test-status testing';

            try {
                const res = await fetch('/api/ai/test', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({model: model, api_key: apiKey, api_base: apiBase})
                });
                const data = await res.json();
                if (data.success) {
                    const ms = data.latency_ms != null ? `（${data.latency_ms}ms）` : '';
                    statusEl.textContent = '✅ 连接成功 ' + ms;
                    statusEl.className = 'rss-test-status success';
                } else {
                    statusEl.textContent = '❌ ' + (data.message || '测试失败');
                    statusEl.className = 'rss-test-status error';
                }
            } catch (e) {
                statusEl.textContent = '❌ 网络错误';
                statusEl.className = 'rss-test-status error';
            } finally {
                btn.disabled = false;
            }
        }

        // 显示区域
```

### Step 3.3: 静态检查

```bash
cd /home/administrator/TrendRadar
python -c "import ast; ast.parse(open('trendradar/webui/config_page.py').read()); print('OK')"
```

Expected: `OK`（config_page.py 是 .py 文件包着 JS 字符串，AST 解析能捕获 Python 语法错误。JS 语法靠后续的浏览器测试覆盖。）

### Step 3.4: 浏览器手动冒烟（按 spec 第 7 节清单）

启动 server 并打开浏览器：

```bash
cd /home/administrator/TrendRadar
python -m trendradar.webui.server 18099 /tmp &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
echo "打开浏览器: http://localhost:18099/config.html"
```

逐项验证：
- [ ] 切到 AI 模型 Tab，能看到"测试连接"按钮和"使用当前填写的值，不会保存"提示文字
- [ ] 留空 model → 点测试 → 应看到 toast "请先填写模型名称"，Network 面板无 `/api/ai/test` 请求
- [ ] 填 `badname`（不含 /） → 点测试 → toast "模型格式应为 provider/model..."，无请求
- [ ] 填真实可用 model + key → 点测试 → 应看到"✅ 连接成功（xxx ms）"绿色字
- [ ] 填 `wrong/no-such-model` → 点测试 → 应看到"❌ 模型不存在..."红色字
- [ ] 填错 key → 点测试 → 应看到"❌ 鉴权失败..."红色字
- [ ] 浏览器 Network 面板：检查请求 body 只含 `model/api_key/api_base` 三字段、HTTP 200

```bash
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

### Step 3.5: 提交

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/config_page.py
git commit -m "feat(webui): AI 模型配置 - 新增测试连接按钮与状态展示"
```

---

## 自审检查清单

执行前确认：

- [x] **Spec 覆盖**：架构（AITester + 端点 + UI）→ Task 1/2/3；7 个单测 → Task 1；6 项冒烟清单 → Task 3.4
- [x] **无 placeholder**：每个 step 有完整代码或精确命令
- [x] **类型一致**：`AITester.test()` 返回 `Tuple[bool, str, int]` 在 Task 1 定义、在 Task 2 使用
- [x] **API 字段一致**：`model/api_key/api_base` 在 spec、Task 1 实现、Task 2 端点、Task 3 前端四处一致
- [x] **样式复用**：前端 CSS class 复用 `.rss-test-status.testing/.success/.error`
- [x] **异常归一**：spec 第 4 节的 5 种类型在 Task 1 的 `_friendly_message` 全覆盖
- [x] **频率提交**：每个 task 末尾 `git commit`，4 个 commit

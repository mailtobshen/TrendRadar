# AI 模型配置 — 测试连接按钮

**日期**：2026-06-03
**作者**：Claude (brainstorming with user)
**状态**：已批准，待实施

## 背景与目标

`配置管理 → AI 模型 → AI 模型配置` 区的所有参数都靠手工输入，灵活但容易出错。常见失败包括：

- 填错模型名（`provider/model` 中 provider 或 model 拼错）
- API Key 错误 / 已过期 / 多粘贴了空格
- 自建网关的 API Base URL 写错
- 用户改了 `config.yaml` 但没意识到没生效

目标：在 AI 模型配置区加一个 **"测试连接"** 按钮，使用当前表单里未保存的输入值直接 ping 模型，把"网络可达 / 鉴权通过 / 模型存在"这层最易错的事实即时反馈给用户。

非目标：不验证 `temperature` / `max_tokens` / `num_retries` / `fallback_models` 等参数；不改 `AIClient` 现有调用路径；不替代真正的业务调用。

## 设计

### 1. 架构（三层）

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (config_page.py)                                  │
│  [测试连接] 按钮 + 状态 span (testing/success/error)        │
│  ↓ 读 ai-model/ai-api-key/ai-api-base 三个 input 当前值     │
│  ↓ POST /api/ai/test                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WebUI server (server.py)                                   │
│  _api_post_ai_test()                                        │
│  - 基础格式校验 (model 必含 "/")                            │
│  - 委托给 trendradar.ai.tester.AITester.test()              │
│  - 返回 JSON {success, message, latency_ms}                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  New module: trendradar/ai/tester.py                        │
│  class AITester:                                            │
│    def test() -> tuple[bool, str, int]                      │
│      LiteLLM completion(messages=[hi], max_tokens=1)        │
│      计时, 异常归一                                          │
└─────────────────────────────────────────────────────────────┘
```

### 2. 模块职责

| 模块 | 职责 | 不做的事 |
|---|---|---|
| `trendradar/ai/tester.py` (新) | 单次 ping 模型，计时，异常归一 | 不读配置、不写文件 |
| `server.py::_api_post_ai_test` | HTTP 路由、基础格式校验、调用 tester | 不直接调 LiteLLM |
| `config_page.py` JS | 读 3 个 input 当前值、POST、渲染状态 | 不读 config 对象 |

**关键决策**：

- **不依赖 `AIClient`**：避免把 `timeout=120/num_retries=2` 等业务默认带入 ping 路径
- **`AITester` 是独立小类**：与 `AIClient` 平级，方便单测；如需删除只动一个文件
- **路由独立于 `/api/config`**：测试不会触发 tags 对比、爬取、数据库同步等保存副作用

### 3. API 契约

| 项 | 值 | 说明 |
|---|---|---|
| Endpoint | `POST /api/ai/test` | 仿照 `/api/rss/test` |
| Request body | `{model, api_key, api_base}` | 全 string，可为空 |
| Response body | `{success: bool, message: str, latency_ms: int}` | success=true 时 message 是"连接成功"；失败时是友好错误 |
| 业务 HTTP 状态 | 永远 200 | 与 RSS test 端点保持一致；前端只读 JSON |
| ping 内容 | `messages=[{role:user, content:"hi"}], max_tokens=1` | 最小成本、跨 provider 通用 |
| ping 超时 | 30s | 硬编码，独立于 AIClient.timeout |
| ping 重试 | `num_retries=0` | 测试要快反馈，不要重试 |
| Content-Length 上限 | 8KB | 三个字段绰绰有余 |

### 4. 异常归一（`tester.py` 内 `_friendly(e)`）

- `litellm.AuthenticationError` → `"鉴权失败：API Key 无效或已过期"`
- `litellm.NotFoundError` → `"模型不存在：{model}"`
- `litellm.Timeout` / `requests.Timeout` → `"请求超时（30s）"`
- `litellm.APIConnectionError` / `requests.ConnectionError` → `"网络连接失败：{url}"`
- `litellm.RateLimitError` → `"请求过于频繁，请稍后重试"`
- 其它 → `f"测试失败: {type(e).__name__}: {str(e)[:200]}"`（截断防刷屏）

### 5. 前端 UI 改动（`config_page.py`）

**CSS**：复用现有 `.rss-test-status.testing/.success/.error` 三个 class（line 270-273），不新增样式。

**HTML**（在 `panel-ai` → "AI 模型配置" section 尾部，line 468 后插入）：

```html
<div class="form-row">
    <div class="form-group">
        <button class="btn btn-sm btn-secondary" id="ai-test-btn" onclick="testAiConnection()">测试连接</button>
        <span id="ai-test-status" class="rss-test-status"></span>
        <span class="optional" style="margin-left: 8px;">使用当前填写的值，不会保存</span>
    </div>
</div>
```

**JS 函数**（紧跟 `testRssConnectivity` 之后，约 line 1350 后）：

```javascript
async function testAiConnection() {
    const model = document.getElementById('ai-model').value.trim();
    const apiKey = document.getElementById('ai-api-key').value.trim();
    const apiBase = document.getElementById('ai-api-base').value.trim();

    // 前端基础校验，免一次往返
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
            body: JSON.stringify({model, api_key: apiKey, api_base: apiBase})
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
```

**注意点**：

- 函数读 **DOM 当前值**，不读 `getValue('ai')`，不读任何未保存状态树 → 与"读未保存输入"选择一致
- `api_key` 即使为空也会发请求，允许后端用环境变量兜底
- 不写回 config 对象 → 不污染未保存状态树

### 6. 后端测试（`trendradar/ai/test_tester.py`，mock LiteLLM）

| 测试用例 | 期望 |
|---|---|
| `test_success` | mock `completion` 返回合法 response → `(True, "连接成功", <ms>)` |
| `test_auth_error` | mock 抛 `litellm.AuthenticationError` → `(False, "鉴权失败...", _)` |
| `test_not_found` | mock 抛 `NotFoundError` → `(False, "模型不存在...", _)` |
| `test_timeout` | mock 抛 `Timeout` → `(False, "请求超时（30s）", _)` |
| `test_empty_choices` | mock 返回 `choices=[]` → `(False, "模型返回空响应", _)` |
| `test_no_api_key_no_base` | 传 `(model="x/y", api_key="", api_base="")` → 不报 KeyError，正常调 LiteLLM |
| `test_with_api_base` | 传 `api_base` → 验证 params 含 `api_base` |

### 7. 手动冒烟清单（实施完成后我跑一遍）

- [ ] 打开 `http://localhost:8080/config.html` → 切到 AI 模型 Tab
- [ ] 填一个真实可用模型 + key → 点测试连接 → 应看到"✅ 连接成功（xxx ms）"
- [ ] 改 model 名为 `wrong/no-such-model` → 点测试 → 应看到"❌ 模型不存在..."
- [ ] 改 api_key 为 `sk-invalid` → 点测试 → 应看到"❌ 鉴权失败..."
- [ ] 留空 model → 点测试 → 应看到 toast "请先填写模型名称"，不发请求
- [ ] 浏览器 Network 面板：检查请求体只含 `model/api_key/api_base` 三字段、HTTP 200

### 8. 兼容性

- `AIClient.validate_config()` **保持不变**（仍在 `AIClient` 启动时调用，避免破坏其它调用方）
- `AIClient` 不动；`AITester` 是独立新类
- `AIFilter` / `AIAnalyzer` / `AITranslator` 等下游不受影响
- 前端不破坏"自动保存"逻辑：测试按钮只读 DOM、只调新端点，不写 config 对象
- 不在保存配置时自动 ping

### 9. 不会做的事（避免范围蔓延）

- ❌ 不测 temperature / max_tokens / num_retries / fallback_models（按选择只测三件套）
- ❌ 不改 `AIClient.validate_config()`
- ❌ 不在保存配置时自动 ping
- ❌ 不做"测试历史记录"、"多模型对比"
- ❌ 不改 LiteLLM 调用参数；只用同步 `completion()`

## 实施步骤（高层）

1. 新建 `trendradar/ai/tester.py`（`AITester` 类 + `_friendly` 异常归一函数）
2. 新建 `trendradar/ai/test_tester.py`（7 个单测，mock `litellm.completion`）
3. `server.py` 新增 `_api_post_ai_test()` + 在 `do_POST` 路由注册 `/api/ai/test`
4. `config_page.py`：
   - HTML 在 AI 模型配置 section 尾部插入按钮 + 状态 span
   - JS 新增 `testAiConnection()` 函数
5. 跑单测 + 手动冒烟清单
6. 提交

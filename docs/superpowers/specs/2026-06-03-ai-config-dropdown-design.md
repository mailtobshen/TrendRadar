# AI 模型配置 — 两级下拉 + Provider API 刷新 设计

**日期**：2026-06-03
**作者**：Claude (brainstorming with user)
**状态**：已批准，待实施
**前置 spec**：`docs/superpowers/specs/2026-06-03-ai-config-test-button-design.md`

## 背景与目标

`配置管理 → AI 模型 → 模型名称` 当前是 free-text input (`provider/model_name`)。手工输入易错：
- provider 拼错（`MiniMax` vs `minimax`）
- model 名拼错或漏字符
- 用户不知道当前 LiteLLM 支持什么

**新方案**：把 free-text input 替换为 **两级下拉**（provider + model），并提供 **↻ 刷新按钮** 实时从 provider API 拉取最新模型清单。

**核心原则**：
- **向后兼容**：`ai.model` 仍是单字符串 `provider/model`；AIClient / AITester / 现有 config schema 零改动
- **双源合并**：model 下拉数据 = LiteLLM catalog（过滤 provider/*）∪ provider API 返回的模型（去重）
- **轻量集成**：复用现有 `litellm.model_cost` 和 `litellm.provider_list`，不引入新依赖

**非目标**：
- 不做 provider-specific URL 模板（只走 OpenAI 兼容 `/v1/models`）
- 不缓存到磁盘
- 不展示 model cost / context 等元信息
- 不做保存时自动刷新

## 设计

### 1. 架构

四层数据流：UI 触发 → 后端聚合 → LiteLLM + provider API 双源 → 合并去重 → 渲染到下拉

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (config_page.py)                                   │
│  Provider <select>   Model <select>  [↻]                     │
│       ↓                    ↑             │                    │
│  onchange → loadModels()  填充 ←── refresh click            │
└─────────────────────────────────────────────────────────────┘
            │                            │
   loadModels(provider)        refreshModels()
   POST /api/ai/models         POST /api/ai/models
   (无 api_key, base 可空)    (带 api_key + api_base)
            ↓                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WebUI server (server.py)                                   │
│  _api_post_ai_models()                                       │
│  - 接收 {provider, api_key?, api_base?}                     │
│  - 委托给 ModelCatalog.get_merged()                         │
│  - 永远 HTTP 200, {success, models, lite_count, ...}        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  New module: trendradar/ai/model_catalog.py                 │
│  class ModelCatalog:                                        │
│    list_providers() → list[str]                              │
│      从 litellm.provider_list 取所有 slug                    │
│    get_merged(provider, api_key, api_base) → list[str]      │
│      1. 从 litellm.model_cost 过滤 provider/* 去前缀         │
│      2. 若 api_base 非空 + api_key 非空,                    │
│         GET {api_base}/models 带 Authorization              │
│         解析 OpenAI 格式 {data:[{id:...}]}                  │
│         异常 → 静默返回 None                                 │
│      3. 合并去重, 排序, 返回                                │
└─────────────────────────────────────────────────────────────┘
```

### 2. 文件清单

| 文件 | 操作 | 职责 |
|---|---|---|
| `trendradar/ai/model_catalog.py` | 新建 | `ModelCatalog` 类；纯逻辑，独立可测 |
| `trendradar/ai/test_model_catalog.py` | 新建 | 单测，mock `litellm.model_cost` + `requests.get` |
| `trendradar/webui/server.py` | 修改 | 新增 `_api_post_ai_models()` + `do_POST` 注册 `/api/ai/models` |
| `trendradar/webui/config_page.py` | 修改 | 替换 free-text input 为两个 `<select>` + 刷新按钮；新增 `loadModels()` / `refreshAiModels()` / `initAiProviderList()` / `splitModel()` / `joinModel()` / `renderModelOptions()` / `onProviderChange()` JS |

**关键决策**：
- `config schema` 不变：`ai.model` 仍是单一字符串 `provider/model`；前端在两个下拉和字符串之间转换
- `AITester` / `AIClient` / `AIFilter` 不动：保持向后兼容
- 新模块 `ModelCatalog` 独立小类：与 `AITester` 平级，方便单测
- 空 `api_base` 或空 `api_key` 不报错：只返回 LiteLLM catalog

### 3. API 契约

| 项 | 值 |
|---|---|
| Endpoint | `POST /api/ai/models` |
| Request body | `{provider: str, api_key?: str, api_base?: str}` |
| Response body | `{success: bool, message?: str, models: list[str], lite_count: int, provider_count: int, fetched_at?: int}` |
| 业务 HTTP 状态 | 永远 200 |
| 后端超时 | 15s（provider API 调用） |

**额外端点**：
- `POST /api/ai/providers` — 返回 `{success, providers: [slug1, slug2, ...]}`，调用 `ModelCatalog.list_providers()`

### 4. model 字符串格式与解析

- **保存**：`ai.model = provider + "/" + model_name`（前端 JS 拼接）
- **加载**：`[provider, model_name] = ai.model.split("/", 1)`，分别设到两个 select
- **多 `/` 处理**：含多个 `/` 的 model 切第一个 `/`，`model_name = "foo/bar"`

### 5. 合并策略

- LiteLLM 部分：来自 `model_cost`，过滤 `provider/*` 后去掉前缀
- Provider API 部分：解析 `{data: [{id: "model-1"}, {id: "model-2"}]}`；如果 id 含 `/` 则切第一个
- 去重：`set(litellm) | set(provider_api)`，保序
- 排序：LiteLLM 在前（按字母序），provider API 新增的标 "(新)" 在后

### 6. UI 改动（`config_page.py`）

**HTML 替换**（在 AI 模型配置 section 头部，目前是 free-text input）：

**OLD**：
```html
<div class="form-row">
    <div class="form-group full">
        <label class="form-label">模型名称 <span class="optional">格式: provider/model_name</span></label>
        <input type="text" id="ai-model" placeholder="deepseek/deepseek-chat"
            onchange="updateConfig('ai.model', this.value)">
    </div>
</div>
```

**NEW**：
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

**JS 函数**（追加在 `testAiConnection` 后面）：

```javascript
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
        if (!data.success) { sel.innerHTML = '<option value="">加载失败</option>'; return; }
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

**加载已保存值**（在 `setInput('ai-model', ai.model)` 处改为）：

```javascript
// OLD: setInput('ai-model', ai.model);
// NEW:
const [savedProvider, savedModel] = splitModel(ai.model || '');
initAiProviderList().then(() => {
    const pSel = document.getElementById('ai-provider');
    if (savedProvider) pSel.value = savedProvider;
    if (savedProvider) {
        loadModelsForProvider(savedProvider, /* preserve */ true).then(() => {
            if (savedModel) document.getElementById('ai-model').value = savedModel;
        });
    }
});
```

**新增 CSS**（仅一条，复用 `.btn` 风格）：

```css
.btn-icon {
    width: 28px; height: 28px; padding: 0;
    border-radius: 6px; font-size: 14px;
    background: #f3f4f6; border: 1px solid #e5e5e5;
    cursor: pointer;
}
.btn-icon:hover { background: #e5e7eb; }
.btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }
```

### 7. 错误归一（`ModelCatalog` 内 `_fetch_provider_models`）

| 异常/状态 | 抛出 `ProviderAPIError` 消息 |
|---|---|
| `requests.Timeout` | "请求 provider 超时（15s）" |
| `requests.ConnectionError` | "网络连接失败：{host}" |
| HTTP 401/403 | "Provider API 鉴权失败，请检查 API Key" |
| HTTP 404 | "Provider API 不支持 /models 端点" |
| HTTP 5xx | "Provider API 异常 ({status})" |
| 非 JSON body | 静默返回 None（视为不可解析，不影响主流程） |
| body 不是 `{data:[...]}` 格式 | 静默返回 None |

`ProviderAPIError` 包含 `user_message` 字段，HTTP 端点把它放进响应 JSON 的 `message` 字段，前端用 toast 显示。

### 8. 与现有代码的兼容性

- `AITester`、`AIClient`、`AIFilter` 等下游：**零改动**，仍接收 `model="provider/model"` 字符串
- 现有 `/api/ai/test` 端点：**零改动**
- config schema：`ai.model` 仍是单字符串
- 现有用户保存的 `minimax/MiniMax-Text-01`：**完全兼容**，加载时正确解析到两个下拉

### 9. 实施步骤（高层）

1. 新建 `trendradar/ai/model_catalog.py`（`ModelCatalog` 类 + `ProviderAPIError` 异常 + `_fetch_provider_models` 内部）
2. 新建 `trendradar/ai/test_model_catalog.py`（12 个单测，mock `litellm.model_cost` + `requests.get`）
3. `server.py` 新增 `_api_post_ai_models()` 和 `_api_post_ai_providers()` + 在 `do_POST` 注册两个路由
4. `config_page.py`：
   - CSS 加 `.btn-icon`
   - HTML 替换模型名称 input 为两个 select + 刷新按钮
   - JS 新增 7 个函数（`joinModel` / `splitModel` / `initAiProviderList` / `onProviderChange` / `loadModelsForProvider` / `refreshAiModels` / `renderModelOptions`）
   - 改 `setInput('ai-model', ...)` 加载逻辑
5. 跑单测 + 手动冒烟清单
6. 提交

## 不会做的事（避免范围蔓延）

- ❌ 不在 catalog 端点上做 provider-specific URL 模板（`gemini → /v1beta/models` 等）；只用 OpenAI 兼容 `/v1/models`；不支持的 provider 显式告诉用户
- ❌ 不缓存 model list 到磁盘
- ❌ 不暴露 `litellm.get_model_cost_map(remote_url)` 的手动 URL 覆盖参数
- ❌ 不做 model 搜索框
- ❌ 不在 model 下拉项里展示 cost / context / capabilities
- ❌ 不在保存配置时自动 ping（与"测试连接"按钮的设计哲学保持一致：动作分离）

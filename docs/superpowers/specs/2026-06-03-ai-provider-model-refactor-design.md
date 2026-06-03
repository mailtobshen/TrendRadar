# AI 模型配置 — Provider/Model 字段重构 设计

**日期**：2026-06-03
**作者**：Claude (brainstorming with user)
**状态**：已批准，待实施
**前置 spec**：
- `docs/superpowers/specs/2026-06-03-ai-config-test-button-design.md`（测试连接按钮）
- `docs/superpowers/specs/2026-06-03-ai-config-dropdown-design.md`（provider + model 两级下拉）

## 背景与目标

之前的设计把 `ai.model` 存为 `provider/model` 拼接字符串（如 `minimax/MiniMax-Text-01`），用 `splitModel` / `joinModel` 在前端两下拉和字符串之间转换。

**问题**（用户在手工测试中暴露）：
- 选 `provider=anthropic` + `model=MiniMax-M3` 点"测试连接" → LiteLLM 用 Anthropic adapter，发到 Anthropic 端点，抛 "模型不存在：anthropic/MiniMax-M3"
- 实际：用户想调 MiniMax API，但 provider 标签选错了，LiteLLM 路由也跟着错

**根因**：
- `provider` 在 LiteLLM 里是 **adapter 路由键**（openai/anthropic/gemini/bedrock 各自不同 client）
- `provider` 在用户认知里是 **分类标签**（只是给 model 加个前缀好看）
- 当前设计把这两个角色混在一起，错误使用导致 LiteLLM 选错 adapter

**新方案**：
- 把 `ai.model` 拆成两个字段：`ai.provider`（LiteLLM adapter 路由）+ `ai.model`（纯模型名）
- 前端 provider 下拉改为 **6 项硬编码精简清单**（openai / anthropic / gemini / bedrock / vertex_ai / azure）
- model 下拉默认空，用户**手动点 ↻ 拉取**（从 `api_base/models`），LiteLLM catalog 作 fallback
- 测试连接发送 4 个字段（`provider, model, api_key, api_base`）
- 老配置文件中 `ai.model = "provider/model"` 在 schema 加载时自动拆分，用户无感

## 设计

### 1. 架构

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (config_page.py)                                   │
│  Provider  ── 6 项硬编码下拉                                │
│  API 基础地址  ── input                                     │
│  API Key      ── input                                     │
│  模型名称  ── select (默认空) + ↻ 按钮                     │
│                                                               │
│  onchange provider → 仅写 ai.provider                        │
│  onchange api_base → 仅写 ai.api_base                        │
│  onchange model    → 仅写 ai.model                           │
│  click ↻ → POST /api/ai/models                              │
│  click 测试连接 → POST /api/ai/test                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WebUI server (server.py)                                    │
│  /api/ai/test ← {provider, model, api_key, api_base}        │
│  /api/ai/models ← {provider, api_key?, api_base?}            │
│  /api/ai/providers ← 返回 6 项 (CURATED_PROVIDERS)          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Modified modules:                                           │
│  - AIClient (client.py): 加 provider 字段；构造 f"{p}/{m}"  │
│  - AITester (tester.py): 加 provider 字段；构造 f"{p}/{m}"  │
│  - ModelCatalog: 加 CURATED_PROVIDERS + list_curated_providers()│
│  - config_schema.py: 加载时拆分老格式；默认值加 ai.provider │
└─────────────────────────────────────────────────────────────┘
```

### 2. 文件清单

| 文件 | 操作 | 职责 |
|---|---|---|
| `trendradar/ai/client.py` | 修改 | `AIClient.__init__` 增加 `PROVIDER` 字段；构造 `f"{provider}/{model}"` 调 LiteLLM；`validate_config` 改用 `provider`+`model`（不再校验 `/`） |
| `trendradar/ai/tester.py` | 修改 | `AITester.__init__` 增加 `provider` 参数；同样构造 `f"{provider}/{model}"` |
| `trendradar/ai/test_tester.py` | 修改 | 更新 9 个单测以适配新签名（`AITester(model="X/Y", ...)` → `AITester(provider="X", model="Y", ...)`） |
| `trendradar/ai/model_catalog.py` | 修改 | 新增 `CURATED_PROVIDERS` 常量（6 项）+ `list_curated_providers()` 静态方法 |
| `trendradar/ai/test_model_catalog.py` | 修改 | 新增 1 个单测 |
| `trendradar/webui/server.py` | 修改 | `_api_post_ai_test` 接收 `provider` 字段；`_api_post_ai_providers` 返回 6 项；防御性检测 body 中 model 含 `/` 时自动拆分 |
| `trendradar/webui/config_page.py` | 修改 | provider 改 6 项硬编码下拉；model 默认空；删除 `joinModel`/`splitModel`/`initAiProviderList`/`onProviderChange`；改写 `refreshAiModels`；改写 `testAiConnection`；改写加载逻辑 |
| `trendradar/webui/config_schema.py` | 修改 | `get_default_config` 添加 `ai.provider = "openai"`；`load_structured_config` 添加老格式拆分逻辑 |

### 3. API 契约

| 端点 | 旧 body | 新 body |
|---|---|---|
| `POST /api/ai/test` | `{model, api_key, api_base}` | `{provider, model, api_key, api_base}` |
| `POST /api/ai/models` | 不变 | 不变 |
| `POST /api/ai/providers` | 返回 130+ | 返回 6 项（`openai, anthropic, gemini, bedrock, vertex_ai, azure`） |

所有端点业务 HTTP 状态仍为 200。

### 4. Config Schema 变更

| 字段 | 旧 | 新 |
|---|---|---|
| `ai.model` | `"minimax/MiniMax-Text-01"`（含 `/`） | `"MiniMax-Text-01"`（纯名） |
| `ai.provider` | （不存在） | `"minimax"`（默认 `openai`） |
| `ai.api_key` | 不变 | 不变 |
| `ai.api_base` | 不变 | 不变 |

`config_schema.py` 加载时拆分逻辑（向后兼容）：
```python
if "ai" in result:
    ai = result["ai"]
    model = ai.get("model", "")
    if "/" in model and not ai.get("provider"):
        parts = model.split("/", 1)
        ai["provider"] = parts[0]
        ai["model"] = parts[1]
    if not ai.get("provider"):
        ai["provider"] = "openai"
```

`save_structured_config` 不需要改：写 `ai.provider` + `ai.model`（新格式）即可。

### 5. HTML 变更

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

### 6. JS 函数变更

**删除**：
- `joinModel()` ← 整个删掉
- `splitModel()` ← 整个删掉
- `initAiProviderList()` ← 整个删掉
- `onProviderChange()` ← 整个删掉
- `_modelLoadToken` race guard ← 不再需要（model 下拉默认空，不自动加载）

**修改/新增**：
- `refreshAiModels()` ← 简化为：只读 provider/api_key/api_base；POST 后渲染；不再 race guard
- `renderModelOptions(models, restoreValue)` ← 保留简化版
- `testAiConnection()` ← 改用 4 字段（`{provider, model, api_key, api_base}`）

加载逻辑：
```javascript
// AI
const ai = getValue('ai') || {};
setInput('ai-api-key', ai.api_key);
setInput('ai-api-base', ai.api_base);
setInput('ai-timeout', ai.timeout);
setInput('ai-temperature', ai.temperature);
setInput('ai-max-tokens', ai.max_tokens);
setInput('ai-num-retries', ai.num_retries);

const pSel = document.getElementById('ai-provider');
const mSel = document.getElementById('ai-model');
if (ai.provider && [...pSel.options].some(o => o.value === ai.provider)) {
    pSel.value = ai.provider;
} else {
    pSel.value = 'openai';
}
if (ai.model) {
    mSel.innerHTML = `<option value="${ai.model}">${ai.model} (已保存)</option>`;
    mSel.value = ai.model;
}
```

### 7. 后端 AIClient 变更

```python
class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.provider = config.get("PROVIDER", "openai")  # 新增
        self.model = config.get("MODEL", "")              # 纯名
        self.api_key = config.get("API_KEY") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE", "")
        # ... 其他字段不变
    
    def chat(self, messages, **kwargs):
        params = {
            "model": f"{self.provider}/{self.model}",  # 构造
            "messages": messages,
            # ... 其他不变
        }
    
    def validate_config(self) -> tuple[bool, str]:
        if not self.provider: return False, "未配置 AI Provider"
        if not self.model: return False, "未配置 AI 模型"
        if not self.api_key: return False, "未配置 AI API Key"
        return True, ""  # 不再校验 /
```

### 8. 后端 AITester 变更

```python
class AITester:
    PING_PROMPT = "hi"
    PING_MAX_TOKENS = 1
    PING_TIMEOUT = 30
    PING_NUM_RETRIES = 0

    def __init__(
        self,
        model: str,
        provider: str = "openai",  # 新增
        api_key: str = "",
        api_base: str = "",
        timeout: int = PING_TIMEOUT,
    ):
        self.model = model
        self.provider = provider
        # ...
    
    def test(self) -> Tuple[bool, str, int]:
        # 内部构造 f"{self.provider}/{self.model}"
        params = {
            "model": f"{self.provider}/{self.model}",
            ...
        }
```

### 9. ModelCatalog 变更

```python
CURATED_PROVIDERS = [
    "openai",
    "anthropic",
    "gemini",
    "bedrock",
    "vertex_ai",
    "azure",
]

class ModelCatalog:
    @staticmethod
    def list_curated_providers() -> List[str]:
        return list(CURATED_PROVIDERS)
    
    # 旧 list_providers() 保留不动
    @staticmethod
    def list_providers() -> Set[str]:
        return {p.value for p in litellm.provider_list}
```

### 10. LiteLLM 路由行为

| 用户配置 | LiteLLM 实际 model 参数 | 路由 |
|---|---|---|
| `provider=openai, model=MiniMax-M3, api_base=https://api.minimaxi.com/v1` | `openai/MiniMax-M3` | OpenAI adapter → minimaxi base URL |
| `provider=anthropic, model=claude-3-5-sonnet, api_base=...` | `anthropic/claude-3-5-sonnet` | Anthropic adapter |
| `provider=gemini, model=gemini-1.5-pro, api_base=...` | `gemini/gemini-1.5-pro` | Gemini adapter |
| `provider=bedrock, model=..., api_base=...` | `bedrock/...` | AWS Bedrock |
| `provider=vertex_ai, model=..., api_base=...` | `vertex_ai/...` | Google Cloud |
| `provider=azure, model=..., api_base=...` | `azure/...` | Azure OpenAI |

### 11. 测试策略

`test_tester.py` 更新 9 个测试以适配新 AITester 签名（`AITester(model="X/Y", ...)` → `AITester(provider="X", model="Y", ...)`）。`params["model"]` 断言保持 `X/Y`（LiteLLM 看到的还是 X/Y）。

`test_model_catalog.py` 新增 1 个测试：
- `test_list_curated_providers_returns_6_items` — 验证返回 6 项

不需要新测 `client.py`（所有 LiteLLM 调用都委托给 LiteLLM）。

### 12. 不会做的事

- ❌ 不做 provider 协议家族分组 UI（用户已选 6 项扁平列表）
- ❌ 不支持用户在 provider 下拉里自由输入
- ❌ 不改 LiteLLM catalog 端点（130+ 全清单保留在 `/api/ai/providers` 但前端不用）
- ❌ 不为不同 provider 自动检测 api_base
- ❌ 不做 model 名格式校验（LiteLLM 自己会路由失败）
- ❌ 不改 `AIFilter / AIAnalyzer / AITranslator`（它们用 AIClient，透明受益）
- ❌ 不暴露 `provider` 字段给老用户做 migration warning

## 实施步骤（高层）

1. `trendradar/ai/client.py` — 加 `PROVIDER` 字段 + 改 `validate_config`
2. `trendradar/ai/tester.py` — 加 `provider` 参数
3. `trendradar/ai/test_tester.py` — 更新 9 个单测
4. `trendradar/ai/model_catalog.py` — 加 `CURATED_PROVIDERS` + `list_curated_providers()`
5. `trendradar/ai/test_model_catalog.py` — 加 1 个单测
6. `trendradar/webui/server.py` — `_api_post_ai_test` 接收 `provider`；`_api_post_ai_providers` 返回 6 项
7. `trendradar/webui/config_schema.py` — `get_default_config` 加 `ai.provider`；`load_structured_config` 加拆分逻辑
8. `trendradar/webui/config_page.py` — HTML 改 6 项硬编码；JS 删 4 个函数、改 2 个函数；改写加载逻辑
9. 跑单测 + 手动冒烟
10. 提交

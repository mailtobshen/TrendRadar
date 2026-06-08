# AI 翻译 batch_size 可配置 实现 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ai_translation.batch_size` 暴露为可配置项——yaml + schema + WebUI HTML + WebUI JS + loader 翻译字段 + translator 空值判 5

**Architecture:** 6 文件 ~25 行改动。loader 是 yaml 小写 key → 大写 dict 的转换层，必须让 loader 输出 `BATCH_SIZE` 字段，translator 才能读到大写 key。translator 自身做"空值判 5"逻辑（None / 缺省 / 0 / 负数 / 非整数 → 5；1~N 正整数 → 直接用）。

**Tech Stack:** Python 3.12 / YAML / 原生 HTML+JS

**Spec:** `docs/superpowers/specs/2026-06-08-ai-translation-batch-size-configurable.md`（commit 12a7e43）

---

## 文件清单

| 文件 | 改动 |
|------|------|
| `config/config.yaml` | 加 `batch_size: 5` |
| `trendradar/webui/config_schema.py:205-211` | 默认值加 `batch_size: 5` |
| `trendradar/webui/config_page.py:572-575` | 加每批翻译条数输入框 HTML |
| `trendradar/webui/config_page.py:1035` | JS load 加一行 |
| `trendradar/core/loader.py:325-346` `_load_ai_translation_config` | 加 `BATCH_SIZE: trans_config.get("batch_size", 5)` |
| `trendradar/ai/translator.py:55-62` | 改读大写 `BATCH_SIZE` + 空值判 5（try/except 兜住 TypeError/ValueError；<1 视为空值） |

---

### Task 1: yaml + config_schema 默认值

**Files:**
- Modify: `config/config.yaml:239-246`
- Modify: `trendradar/webui/config_schema.py:205-211`

- [ ] **Step 1: 打开 yaml 确认上下文**

读 `config/config.yaml:239-246`，确认当前结构（实际行号可能有 ±2 偏差）：

```yaml
ai_translation:
  enabled: true
  language: 中文
  prompt_file: ai_translation_prompt.txt
  scope:
    hotlist: false
    rss: true
    standalone: true
```

- [ ] **Step 2: yaml 加 batch_size**

在 `standalone: true` 后面（与 scope 段平齐，缩进 2 空格）加：

```yaml
  batch_size: 5   # 每批翻译条数。值越小越不易触发内容审核拖累整批
```

- [ ] **Step 3: 打开 config_schema.py 确认上下文**

读 `trendradar/webui/config_schema.py:205-211`，确认当前 ai_translation 段：

```python
        "ai_translation": {
            "enabled": False,
            "language": "中文",
            "prompt_file": "ai_translation_prompt.txt",
            "scope": {"hotlist": False, "rss": True, "standalone": True},
            "pre_translate_on_crawl": True,
        },
```

- [ ] **Step 4: schema 默认值加 batch_size**

在 `"pre_translate_on_crawl": True,` 后面加：

```python
            "batch_size": 5,
```

- [ ] **Step 5: 自检**

```bash
cd /home/administrator/TrendRadar
python3 -c "
import yaml
print('yaml batch_size =', yaml.safe_load(open('config/config.yaml'))['ai_translation']['batch_size'])
from trendradar.webui.config_schema import DEFAULT_CONFIG
print('schema batch_size =', DEFAULT_CONFIG['ai_translation']['batch_size'])
assert DEFAULT_CONFIG['ai_translation']['batch_size'] == 5
print('✓ both 5')
"
```

预期：
```
yaml batch_size = 5
schema batch_size = 5
✓ both 5
```

- [ ] **Step 6: Commit**

```bash
cd /home/administrator/TrendRadar
git add config/config.yaml trendradar/webui/config_schema.py
git commit -m "feat(config): ai_translation.batch_size 暴露为可配置项

之前 commit 09de799 让 translator.py 读 yaml batch_size 默认 5，
但 yaml 和 schema 默认值里都没有这个字段——用户调不到。
本次让 yaml + schema 显式声明 batch_size: 5，为 WebUI 编辑铺路。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: WebUI HTML + JS

**Files:**
- Modify: `trendradar/webui/config_page.py:572` 附近
- Modify: `trendradar/webui/config_page.py:1035` 附近

- [ ] **Step 1: 打开 config_page.py 定位 AI 翻译面板**

读 `trendradar/webui/config_page.py:560-595`，定位 AI 翻译 section 的 form-row（行号 ±5 偏差）。

预期能看到 2 个 form-row：
1. 启用翻译 toggle + 目标语言 input
2. scope 三个 checkbox

- [ ] **Step 2: 在 scope form-row 之后新增一个 form-row**

在"翻译独立展示区"复选框所在的 form-row 结束后（`<div class="form-row">...</div>` 闭合标签之后），加：

```html
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">每批翻译条数</label>
                        <input type="number" id="ai-translation-batch-size" min="1"
                            onchange="updateConfig('ai_translation.batch_size', parseInt(this.value)||5)">
                        <div class="form-hint">每批发给 AI 的标题数（值越小越不易触发内容审核拖累整批，建议 5-30）</div>
                    </div>
                </div>
```

注意：与同行 form-row 保持 16 空格缩进（4 层：section → form-row → form-group → label）。

- [ ] **Step 3: 打开 JS load 段**

读 `trendradar/webui/config_page.py:1031-1038`，确认：

```javascript
            // AI 翻译
            const aiTrans = getValue('ai_translation') || {};
            setToggle('ai-translation-enabled-toggle', aiTrans.enabled);
            setInput('ai-translation-language', aiTrans.language);
            const transScope = aiTrans.scope || {};
            setCheckbox('ai-translation-scope-hotlist', transScope.hotlist);
            ...
```

- [ ] **Step 4: JS load 加一行**

在 `setInput('ai-translation-language', aiTrans.language);` 后面加：

```javascript
            setInput('ai-translation-batch-size', aiTrans.batch_size);
```

- [ ] **Step 5: 自检 WebUI 模板 + Python import**

```bash
cd /home/administrator/TrendRadar
python3 -c "
import importlib
m = importlib.import_module('trendradar.webui.config_page')
# 找模板字符串里包含 batch-size 的 id
import re
src = open('trendradar/webui/config_page.py').read()
assert 'ai-translation-batch-size' in src, 'input id missing'
assert 'ai_translation.batch_size' in src, 'config key missing in updateConfig'
print('✓ WebUI id + updateConfig present')
"
```

预期：`✓ WebUI id + updateConfig present`

- [ ] **Step 6: Commit**

```bash
cd /home/administrator/TrendRadar
git add trendradar/webui/config_page.py
git commit -m "feat(webui): AI 翻译面板加每批翻译条数输入框

跟 ai_filter.batch_size 对称。用户在 WebUI 改后保存，
yaml 自动更新；下次爬取时 translator.py 按新值分批。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: loader._load_ai_translation_config 加 BATCH_SIZE 字段

**Files:**
- Modify: `trendradar/core/loader.py:325-346`

- [ ] **Step 1: 打开文件确认上下文**

读 `trendradar/core/loader.py:325-346`，确认当前结构：

```python
def _load_ai_translation_config(config_data: Dict) -> Dict:
    """加载 AI 翻译配置（功能配置，模型配置见 _load_ai_config）"""
    trans_config = config_data.get("ai_translation", {})

    enabled_env = _get_env_bool("AI_TRANSLATION_ENABLED")

    scope = trans_config.get("scope", {})

    return {
        "ENABLED": enabled_env if enabled_env is not None else trans_config.get("enabled", False),
        "LANGUAGE": _get_env_str("AI_TRANSLATION_LANGUAGE") or trans_config.get("language", "English"),
        "PROMPT_FILE": trans_config.get("prompt_file", "ai_translation_prompt.txt"),
        "SCOPE": {
            "HOTLIST": scope.get("hotlist", True),
            "RSS": scope.get("rss", True),
            "STANDALONE": scope.get("standalone", True),
        },
        "PRE_TRANSLATE_ON_CRAWL": trans_config.get("pre_translate_on_crawl", True),
    }
```

- [ ] **Step 2: 加 BATCH_SIZE 字段**

参考 `_load_ai_filter_config`（line 354 `ai_filter.get("batch_size", 200)`）的写法。

在 `"PRE_TRANSLATE_ON_CRAWL": trans_config.get("pre_translate_on_crawl", True),` 后面加：

```python
        # 每批翻译条数上限：避免单次 prompt 过大导致 AI 输出截断
        # 值越小越不易触发内容审核拖累整批
        "BATCH_SIZE": trans_config.get("batch_size", 5),
```

- [ ] **Step 3: 自检 loader 输出**

```bash
cd /home/administrator/TrendRadar
python3 -c "
import yaml
from trendradar.core.loader import _load_ai_translation_config
raw = yaml.safe_load(open('config/config.yaml'))
out = _load_ai_translation_config(raw)
print('BATCH_SIZE =', out.get('BATCH_SIZE'))
assert out.get('BATCH_SIZE') == 5, f'expected 5, got {out.get(\"BATCH_SIZE\")}'
print('✓ loader exposes BATCH_SIZE = 5')
"
```

预期：
```
BATCH_SIZE = 5
✓ loader exposes BATCH_SIZE = 5
```

- [ ] **Step 4: Commit**

```bash
cd /home/administrator/TrendRadar
git add trendradar/core/loader.py
git commit -m "fix(loader): _load_ai_translation_config 暴露 BATCH_SIZE 字段

loader 是 yaml 小写 key → 大写 dict 的转换层。
translator 读大写 BATCH_SIZE 必须由 loader 提供。
修法是让 loader 输出 BATCH_SIZE 字段（跟 _load_ai_filter_config
输出 BATCH_SIZE 对称）。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 15: translator 改读大写 + 空值判 5

**Files:**
- Modify: `trendradar/ai/translator.py:55-62`

- [ ] **Step 1: 打开文件确认上下文**

读 `trendradar/ai/translator.py:50-60`，确认：

```python
        # 翻译配置
        self.enabled = translation_config.get("ENABLED", False)
        self.target_language = translation_config.get("LANGUAGE", "English")
        self.scope = translation_config.get("SCOPE", {"HOTLIST": True, "RSS": True, "STANDALONE": True})
        # 每批翻译条数上限：避免单次 prompt 过大导致 AI 输出截断
        self.batch_size = max(1, int(translation_config.get("batch_size", 5)))
```

- [ ] **Step 2: 改 batch_size 行为**

把第 55-56 行（注释 + batch_size 赋值）替换为：

```python
        # 每批翻译条数：避免单次 prompt 过大导致 AI 输出截断。
        # 空值（None/缺省/0/负数/非整数）→ 用默认 5；其他正整数 → 直接使用配置值
        raw = translation_config.get("BATCH_SIZE")
        try:
            parsed = int(raw) if raw is not None else 5
        except (TypeError, ValueError):
            parsed = 5
        self.batch_size = parsed if parsed >= 1 else 5
```

- [ ] **Step 3: 自检——空值边界（8 case）**

```bash
cd /home/administrator/TrendRadar
python3 -c "
from trendradar.ai.translator import AITranslator

t1 = AITranslator({'ENABLED': True}, {'api_key': 'x'}); assert t1.batch_size == 5
t2 = AITranslator({'BATCH_SIZE': None}, {'api_key': 'x'}); assert t2.batch_size == 5
t3 = AITranslator({'BATCH_SIZE': 0}, {'api_key': 'x'}); assert t3.batch_size == 5
t4 = AITranslator({'BATCH_SIZE': -10}, {'api_key': 'x'}); assert t4.batch_size == 5
t5 = AITranslator({'BATCH_SIZE': 'abc'}, {'api_key': 'x'}); assert t5.batch_size == 5
t6 = AITranslator({'BATCH_SIZE': 1}, {'api_key': 'x'}); assert t6.batch_size == 1
t7 = AITranslator({'BATCH_SIZE': 30}, {'api_key': 'x'}); assert t7.batch_size == 30
t8 = AITranslator({'BATCH_SIZE': '7'}, {'api_key': 'x'}); assert t8.batch_size == 7
print('ALL OK')
"
```

预期：`ALL OK`

- [ ] **Step 4: Commit**

```bash
cd /home/administrator/TrendRadar
git add trendradar/ai/translator.py
git commit -m "fix(translator): BATCH_SIZE 改回大写 + 空值判 5

1. 改回大写 BATCH_SIZE（与同文件 ENABLED/LANGUAGE/SCOPE 风格一致；
   loader 才是 yaml 小写 key → 大写 dict 的转换层）
2. 实现用户要求的'空值判 5'：
   - None / 缺省 / 0 / 负数 / 非整数 → 5
   - 1 及以上正整数 → 直接用配置值
3. try/except 兜住 TypeError + ValueError

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 端到端验证 + push

**Files:** 不改文件

- [ ] **Step 1: 容器内 python 自检**

```bash
cd /home/administrator/TrendRadar
docker exec trendradar python3 -c "
import yaml
import importlib
from trendradar.webui.config_schema import DEFAULT_CONFIG
print('yaml:', yaml.safe_load(open('/app/config/config.yaml'))['ai_translation']['batch_size'])
print('schema:', DEFAULT_CONFIG['ai_translation']['batch_size'])
importlib.import_module('trendradar.webui.config_page')
print('✓ all ok')
"
```

如果容器跑不起来（没启动），用 host：
```bash
cd /home/administrator/TrendRadar
python3 -c "
import yaml
import importlib
from trendradar.webui.config_schema import DEFAULT_CONFIG
print('yaml:', yaml.safe_load(open('config/config.yaml'))['ai_translation']['batch_size'])
print('schema:', DEFAULT_CONFIG['ai_translation']['batch_size'])
importlib.import_module('trendradar.webui.config_page')
print('✓ all ok')
"
```

- [ ] **Step 2: git status + log**

```bash
cd /home/administrator/TrendRadar
git status
echo "---"
git log --oneline -3
```

预期：工作树干净；HEAD 在 Task 2 commit 上。

- [ ] **Step 3: push**

```bash
cd /home/administrator/TrendRadar
git push origin master
```

预期：fast-forward 推送成功。

---

## Self-Review

1. **Spec 覆盖：** ✅ 任务 1（yaml + schema）/ ✅ 任务 2（HTML + JS）/ ✅ 任务 14（loader 翻译 BATCH_SIZE）/ ✅ 任务 15（translator 大写 + 空值判 5）/ ✅ 任务 3（验证 + push）
2. **占位符扫描：** grep "TODO|TBD|fill in|Similar to Task" — 0 hit
3. **类型一致性：** `aiTrans.batch_size` 在 schema 默认值里是 `int: 5`，与 loader 输出的 `BATCH_SIZE: 5`（int）、translator 的 `int(raw) if raw is not None else 5` 类型一致；`parseInt(this.value)||5` 兜前端空值
4. **链路完整性：** yaml `ai_translation.batch_size` (int) → loader `_load_ai_translation_config` 输出 `BATCH_SIZE` (int) → `__main__.py:1251` 喂给 `AITranslator` → translator 读大写 + 空值兜底。**8 个边界用例全过**（缺省/None/0/负数/字符串/1/30/字符串数字）

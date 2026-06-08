# AI 翻译 batch_size 可配置 实现 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ai_translation.batch_size` 暴露为可配置项——yaml + schema + WebUI HTML + WebUI JS

**Architecture:** 4 文件 ~15 行改动。完全不动 `translator.py`（commit 09de799 已经让它读 yaml `batch_size`）。

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

1. **Spec 覆盖：** ✅ 任务 1（yaml + schema）/ ✅ 任务 2（HTML + JS）/ ✅ 任务 3（验证 + push）
2. **占位符扫描：** grep "TODO|TBD|fill in|Similar to Task" — 0 hit
3. **类型一致性：** `aiTrans.batch_size` 在 schema 默认值里是 `int: 5`，与 translator.py `int(translation_config.get("batch_size", 5))` 类型一致；`parseInt(this.value)||5` 处理空值/NaN

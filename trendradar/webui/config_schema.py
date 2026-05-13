# coding=utf-8
"""
配置结构化 Schema 模块

将 config.yaml 和 frequency_words.txt 解析为结构化 JSON，
并提供将结构化 JSON 写回文件的功能。
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


# ═══════════════════════════════════════════════════════════════
# 常量定义
# ═══════════════════════════════════════════════════════════════

ALL_PLATFORM_IDS = [
    {"id": "toutiao", "name": "今日头条"},
    {"id": "baidu", "name": "百度热搜"},
    {"id": "wallstreetcn-hot", "name": "华尔街见闻"},
    {"id": "thepaper", "name": "澎湃新闻"},
    {"id": "bilibili-hot-search", "name": "bilibili 热搜"},
    {"id": "cls-hot", "name": "财联社热门"},
    {"id": "ifeng", "name": "凤凰网"},
    {"id": "tieba", "name": "贴吧"},
    {"id": "weibo", "name": "微博"},
    {"id": "douyin", "name": "抖音"},
    {"id": "zhihu", "name": "知乎"},
]

REPORT_MODES = [
    {"value": "daily", "label": "全天汇总（信息最全）"},
    {"value": "current", "label": "当前榜单（实时热度）"},
    {"value": "incremental", "label": "增量更新（最少打扰）"},
]

DISPLAY_MODES = [
    {"value": "keyword", "label": "按关键词分组"},
    {"value": "platform", "label": "按平台分组"},
]

FILTER_METHODS = [
    {"value": "keyword", "label": "关键词匹配"},
    {"value": "ai", "label": "AI 智能筛选"},
]

AI_ANALYSIS_MODES = [
    {"value": "follow_report", "label": "跟随报告模式"},
    {"value": "daily", "label": "当日汇总"},
    {"value": "current", "label": "当前榜单"},
    {"value": "incremental", "label": "增量更新"},
]

STORAGE_BACKENDS = [
    {"value": "auto", "label": "自动选择"},
    {"value": "local", "label": "本地存储"},
    {"value": "remote", "label": "远程存储（S3 兼容）"},
]

SCHEDULE_PRESETS = [
    {"value": "always_on", "label": "全天候"},
    {"value": "morning_evening", "label": "早晚模式（推荐）"},
    {"value": "office_hours", "label": "工作日三段式"},
    {"value": "night_owl", "label": "夜间模式"},
    {"value": "custom", "label": "完全自定义"},
]

NOTIFICATION_CHANNELS = [
    {"key": "feishu", "label": "飞书", "icon": "📢"},
    {"key": "dingtalk", "label": "钉钉", "icon": "💬"},
    {"key": "wework", "label": "企业微信", "icon": "💼"},
    {"key": "telegram", "label": "Telegram", "icon": "✈️"},
    {"key": "email", "label": "邮件", "icon": "📧"},
    {"key": "ntfy", "label": "ntfy", "icon": "🔔"},
    {"key": "bark", "label": "Bark", "icon": "🍎"},
    {"key": "slack", "label": "Slack", "icon": "💻"},
    {"key": "generic_webhook", "label": "通用 Webhook", "icon": "🔗"},
]

DISPLAY_REGIONS = [
    {"key": "hotlist", "label": "热榜区域"},
    {"key": "new_items", "label": "新增热点"},
    {"key": "rss", "label": "RSS 订阅"},
    {"key": "standalone", "label": "独立展示区"},
    {"key": "ai_analysis", "label": "AI 分析"},
]


# ═══════════════════════════════════════════════════════════════
# 默认配置模板
# ═══════════════════════════════════════════════════════════════

def get_default_config() -> Dict[str, Any]:
    """返回默认结构化配置"""
    return {
        "app": {
            "timezone": "Asia/Shanghai",
            "show_version_update": True,
        },
        "schedule": {
            "enabled": True,
            "preset": "morning_evening",
        },
        "platforms": {
            "enabled": True,
            "sources": [{"id": p["id"], "name": p["name"], "enabled": True} for p in ALL_PLATFORM_IDS],
        },
        "rss": {
            "enabled": False,
            "freshness_filter": {"enabled": True, "max_age_days": 3},
            "feeds": [],
        },
        "report": {
            "mode": "current",
            "display_mode": "keyword",
            "sort_by_position_first": False,
            "rank_threshold": 5,
            "max_news_per_keyword": 0,
        },
        "filter": {
            "method": "keyword",
            "priority_sort_enabled": False,
        },
        "ai_filter": {
            "batch_size": 200,
            "batch_interval": 5,
            "min_score": 0.0,
            "reclassify_threshold": 0.6,
            "interests_file": None,
            "prompt_file": "prompt.txt",
            "extract_prompt_file": "extract_prompt.txt",
            "update_tags_prompt_file": "update_tags_prompt.txt",
        },
        "display": {
            "region_order": ["new_items", "hotlist", "rss", "standalone", "ai_analysis"],
            "regions": {
                "hotlist": True,
                "new_items": True,
                "rss": True,
                "standalone": False,
                "ai_analysis": True,
            },
            "standalone": {
                "platforms": ["zhihu", "wallstreetcn-hot"],
                "rss_feeds": [],
                "max_items": 20,
            },
        },
        "notification": {
            "enabled": True,
            "channels": {
                "feishu": {"webhook_url": ""},
                "dingtalk": {"webhook_url": ""},
                "wework": {"webhook_url": "", "msg_type": "markdown"},
                "telegram": {"bot_token": "", "chat_id": ""},
                "email": {"from": "", "password": "", "to": "", "smtp_server": "", "smtp_port": ""},
                "ntfy": {"server_url": "https://ntfy.sh", "topic": "", "token": ""},
                "bark": {"url": ""},
                "slack": {"webhook_url": ""},
                "generic_webhook": {"webhook_url": "", "payload_template": ""},
            },
        },
        "storage": {
            "backend": "auto",
            "formats": {"sqlite": True, "txt": False, "html": True},
            "local": {"data_dir": "output", "retention_days": 0},
            "remote": {
                "endpoint_url": "",
                "bucket_name": "",
                "access_key_id": "",
                "secret_access_key": "",
                "region": "",
                "retention_days": 0,
            },
            "pull": {"enabled": False, "days": 7},
        },
        "ai": {
            "model": "deepseek/deepseek-chat",
            "api_key": "",
            "api_base": "",
            "timeout": 120,
            "temperature": 1.0,
            "max_tokens": 5000,
            "num_retries": 1,
            "fallback_models": [],
            "extra_params": {},
        },
        "ai_analysis": {
            "enabled": True,
            "language": "Chinese",
            "prompt_file": "ai_analysis_prompt.txt",
            "mode": "follow_report",
            "max_news_for_analysis": 50,
            "include_rss": True,
            "include_standalone": False,
            "include_rank_timeline": False,
        },
        "ai_translation": {
            "enabled": False,
            "language": "中文",
            "prompt_file": "ai_translation_prompt.txt",
            "scope": {"hotlist": False, "rss": True, "standalone": True},
        },
        "tags": {
            "mode": "auto",
            "items": [],
        },
        "advanced": {
            "debug": False,
            "version_check_url": "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version",
            "mcp_version_check_url": "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version_mcp",
            "configs_version_check_url": "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version_configs",
            "crawler": {
                "request_interval": 100,
                "use_proxy": False,
                "default_proxy": "http://127.0.0.1:10801",
            },
            "rss": {
                "request_interval": 1000,
                "timeout": 15,
                "use_proxy": False,
                "proxy_url": "",
            },
            "weight": {
                "rank": 0.6,
                "frequency": 0.3,
                "hotness": 0.1,
            },
            "max_accounts_per_channel": 3,
            "batch_size": {
                "default": 4000,
                "dingtalk": 20000,
                "feishu": 29000,
                "bark": 3600,
                "slack": 4000,
            },
            "batch_send_interval": 1.0,
            "feishu_message_separator": "---",
        },
    }


# ═══════════════════════════════════════════════════════════════
# config.yaml 读写
# ═══════════════════════════════════════════════════════════════

def load_structured_config(config_path: Path) -> Dict[str, Any]:
    """
    从 config.yaml 加载结构化配置
    如果文件不存在，返回默认配置
    """
    if not config_path.exists():
        return get_default_config()

    if yaml is None:
        raise ImportError("缺少 PyYAML 依赖，无法解析 YAML")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"YAML 解析失败: {e}")

    if not isinstance(raw, dict):
        return get_default_config()

    default = get_default_config()
    result = {}

    # 递归合并，保留文件中的值，缺失的使用默认值
    for key in default:
        if key in raw and isinstance(raw[key], dict):
            result[key] = _deep_merge(default[key], raw[key])
        elif key in raw:
            result[key] = raw[key]
        else:
            result[key] = default[key]

    # 确保 platforms.sources 中所有平台都存在
    if "platforms" in result:
        existing_ids = {s.get("id") for s in result["platforms"].get("sources", [])}
        for p in ALL_PLATFORM_IDS:
            if p["id"] not in existing_ids:
                result["platforms"]["sources"].append({"id": p["id"], "name": p["name"], "enabled": True})

    return result


def save_structured_config(config_path: Path, config: Dict[str, Any]) -> None:
    """
    将结构化配置保存为 config.yaml
    """
    if yaml is None:
        raise ImportError("缺少 PyYAML 依赖，无法生成 YAML")

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # 清理 None 值和空列表，使 YAML 更干净
    cleaned = _clean_empty_values(config)

    # 使用 yaml.safe_dump 生成 YAML
    content = yaml.safe_dump(
        cleaned,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
        indent=2,
    )

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)


def _deep_merge(default: Any, override: Any) -> Any:
    """深度合并两个字典，override 优先"""
    if isinstance(default, dict) and isinstance(override, dict):
        result = dict(default)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    return override


def _clean_empty_values(obj: Any) -> Any:
    """清理 None 值，但保留空字符串和空列表"""
    if isinstance(obj, dict):
        return {k: _clean_empty_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_clean_empty_values(v) for v in obj]
    return obj


# ═══════════════════════════════════════════════════════════════
# frequency_words.txt 读写
# ═══════════════════════════════════════════════════════════════

def load_structured_frequency_words(path: Path) -> Dict[str, Any]:
    """
    从 frequency_words.txt 加载结构化配置

    Returns:
        {
            "global_filters": [{"type": "normal", "content": "..."}, ...],
            "word_groups": [
                {
                    "name": "组名或 null",
                    "max_count": 0,
                    "keywords": [
                        {"type": "normal|regex|required|filter", "content": "...", "alias": "..."},
                    ]
                },
            ]
        }
    """
    if not path.exists():
        return {"global_filters": [], "word_groups": []}

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_frequency_words_text(content)


def parse_frequency_words_text(content: str) -> Dict[str, Any]:
    """解析 frequency_words.txt 文本为结构化数据"""
    lines = content.splitlines()

    global_filters = []
    word_groups = []

    current_section = "header"  # header, global_filter, word_groups
    current_group = None

    for raw_line in lines:
        line = raw_line.strip()

        # 跳过空行和纯注释行（但在词组中的空行表示词组结束）
        if not line or line.startswith("#"):
            if current_section == "word_groups" and current_group is not None:
                # 空行结束当前词组
                if current_group["keywords"]:
                    word_groups.append(current_group)
                current_group = None
            continue

        # 区域标记
        if line == "[GLOBAL_FILTER]":
            current_section = "global_filter"
            current_group = None
            continue
        elif line == "[WORD_GROUPS]":
            current_section = "word_groups"
            current_group = None
            continue

        if current_section == "global_filter":
            kw = _parse_keyword_line(line)
            if kw:
                global_filters.append(kw)

        elif current_section == "word_groups":
            # 组别名 [xxx]
            if line.startswith("[") and line.endswith("]"):
                if current_group is not None and current_group["keywords"]:
                    word_groups.append(current_group)
                current_group = {
                    "name": line[1:-1].strip(),
                    "max_count": 0,
                    "keywords": [],
                }
                continue

            # 限制条数 @数字
            if line.startswith("@") and line[1:].isdigit():
                if current_group is None:
                    current_group = {"name": None, "max_count": 0, "keywords": []}
                current_group["max_count"] = int(line[1:])
                continue

            kw = _parse_keyword_line(line)
            if kw:
                if current_group is None:
                    current_group = {"name": None, "max_count": 0, "keywords": []}
                current_group["keywords"].append(kw)

    # 最后一个词组
    if current_group is not None and current_group["keywords"]:
        word_groups.append(current_group)

    return {"global_filters": global_filters, "word_groups": word_groups}


def _parse_keyword_line(line: str) -> Optional[Dict[str, str]]:
    """解析单行关键词"""
    # 分离别名 =>
    alias = None
    if "=>" in line:
        parts = line.split("=>", 1)
        line = parts[0].strip()
        alias = parts[1].strip() if parts[1].strip() else None

    # 必须词 +
    if line.startswith("+"):
        return {"type": "required", "content": line[1:].strip(), "alias": alias}

    # 过滤词 !
    if line.startswith("!"):
        return {"type": "filter", "content": line[1:].strip(), "alias": alias}

    # 正则 /.../
    if line.startswith("/") and line.endswith("/"):
        return {"type": "regex", "content": line[1:-1], "alias": alias}
    if line.startswith("/") and len(line) > 2:
        # 检查 /pattern/flags 格式
        m = re.match(r'^/(.+)/([a-zA-Z]*)$', line)
        if m:
            return {"type": "regex", "content": m.group(1), "alias": alias}

    # 普通词
    return {"type": "normal", "content": line, "alias": alias}


def save_structured_frequency_words(path: Path, data: Dict[str, Any]) -> None:
    """将结构化配置保存为 frequency_words.txt"""
    lines = []

    # 头部注释
    lines.append("# TrendRadar 频率词配置文件")
    lines.append("# 由 WebUI 配置管理系统生成")
    lines.append("")

    # 全局过滤区
    lines.append("[GLOBAL_FILTER]")
    for kw in data.get("global_filters", []):
        lines.append(_keyword_to_line(kw))
    lines.append("")

    # 词组定义区
    lines.append("[WORD_GROUPS]")
    lines.append("")

    for group in data.get("word_groups", []):
        if group.get("name"):
            lines.append(f"[{group['name']}]")
        for kw in group.get("keywords", []):
            lines.append(_keyword_to_line(kw))
        if group.get("max_count", 0) > 0:
            lines.append(f"@{group['max_count']}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _keyword_to_line(kw: Dict[str, str]) -> str:
    """将结构化关键词转换为文本行"""
    t = kw.get("type", "normal")
    content = kw.get("content", "")
    alias = kw.get("alias")

    prefix = {
        "required": "+",
        "filter": "!",
        "regex": "/",
        "normal": "",
    }.get(t, "")

    suffix = "/" if t == "regex" else ""

    line = f"{prefix}{content}{suffix}"
    if alias:
        line += f" => {alias}"
    return line

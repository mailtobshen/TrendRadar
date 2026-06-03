# coding=utf-8
"""
配置验证模块（结构化配置版本）

验证用户提交的结构化配置对象，确保格式正确后再写入磁盘。
"""

import re
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

from trendradar.webui.config_schema import ALL_PLATFORM_IDS
from trendradar.ai.model_catalog import CURATED_PROVIDERS

VALID_PLATFORM_IDS = {p["id"] for p in ALL_PLATFORM_IDS}
VALID_AI_PROVIDERS_SET = set(CURATED_PROVIDERS)
VALID_REPORT_MODES = {"daily", "current", "incremental"}
VALID_DISPLAY_MODES = {"keyword", "platform"}
VALID_FILTER_METHODS = {"keyword", "ai"}
VALID_AI_MODES = {"follow_report", "daily", "current", "incremental"}
VALID_STORAGE_BACKENDS = {"auto", "local", "remote"}
VALID_SCHEDULE_PRESETS = {"always_on", "morning_evening", "office_hours", "night_owl", "custom"}
VALID_TAGS_MODES = {"auto", "manual"}


def validate_structured_config(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    验证结构化配置对象

    Returns:
        错误列表，每项包含 section（区块）、field（字段）、message（错误信息）
    """
    errors = []

    if not isinstance(config, dict):
        errors.append({"section": "root", "field": "", "message": "配置根节点必须是对象"})
        return errors

    # === app ===
    app = config.get("app", {})
    if not isinstance(app, dict):
        errors.append({"section": "app", "field": "", "message": "app 必须是对象"})
    else:
        tz = app.get("timezone", "")
        if not tz or "/" not in tz:
            errors.append({"section": "app", "field": "timezone", "message": "时区格式无效，应为 Continent/City 格式"})

    # === schedule ===
    schedule = config.get("schedule", {})
    if isinstance(schedule, dict):
        preset = schedule.get("preset", "")
        if preset and preset not in VALID_SCHEDULE_PRESETS:
            errors.append({"section": "schedule", "field": "preset", "message": f"无效的预设值: {preset}"})

    # === platforms ===
    platforms = config.get("platforms", {})
    if isinstance(platforms, dict):
        sources = platforms.get("sources", [])
        if not isinstance(sources, list):
            errors.append({"section": "platforms", "field": "sources", "message": "sources 必须是列表"})
        else:
            for idx, src in enumerate(sources):
                if not isinstance(src, dict):
                    errors.append({"section": "platforms", "field": f"sources[{idx}]", "message": "平台配置必须是对象"})
                    continue
                pid = src.get("id", "")
                if not pid:
                    errors.append({"section": "platforms", "field": f"sources[{idx}].id", "message": "平台 ID 不能为空"})
                elif pid not in VALID_PLATFORM_IDS:
                    errors.append({"section": "platforms", "field": f"sources[{idx}].id", "message": f"未知平台 ID: {pid}"})

    # === rss ===
    rss = config.get("rss", {})
    if isinstance(rss, dict):
        feeds = rss.get("feeds", [])
        if isinstance(feeds, list):
            for idx, feed in enumerate(feeds):
                if not isinstance(feed, dict):
                    continue
                url = feed.get("url", "")
                if url and not _is_valid_url(url):
                    errors.append({"section": "rss", "field": f"feeds[{idx}].url", "message": f"无效的 RSS URL: {url}"})
                fid = feed.get("id", "")
                if fid and not re.match(r'^[a-zA-Z0-9_-]+$', fid):
                    errors.append({"section": "rss", "field": f"feeds[{idx}].id", "message": f"RSS ID 只能包含字母、数字、下划线和连字符: {fid}"})
        freshness = rss.get("freshness_filter", {})
        if isinstance(freshness, dict):
            max_age = freshness.get("max_age_days", 3)
            if not isinstance(max_age, int) or max_age < 0:
                errors.append({"section": "rss", "field": "freshness_filter.max_age_days", "message": "max_age_days 必须是非负整数"})

    # === report ===
    report = config.get("report", {})
    if isinstance(report, dict):
        mode = report.get("mode", "")
        if mode and mode not in VALID_REPORT_MODES:
            errors.append({"section": "report", "field": "mode", "message": f"无效的报告模式: {mode}"})
        display_mode = report.get("display_mode", "")
        if display_mode and display_mode not in VALID_DISPLAY_MODES:
            errors.append({"section": "report", "field": "display_mode", "message": f"无效的显示模式: {display_mode}"})
        rank_threshold = report.get("rank_threshold", 10)
        if not isinstance(rank_threshold, int) or rank_threshold < 0:
            errors.append({"section": "report", "field": "rank_threshold", "message": "rank_threshold 必须是非负整数"})

    # === filter ===
    filt = config.get("filter", {})
    if isinstance(filt, dict):
        method = filt.get("method", "")
        if method and method not in VALID_FILTER_METHODS:
            errors.append({"section": "filter", "field": "method", "message": f"无效的筛选策略: {method}"})

    # === ai_filter ===
    ai_filter = config.get("ai_filter", {})
    if isinstance(ai_filter, dict):
        for key, label in [("min_score", "最低分数阈值"), ("reclassify_threshold", "重分类阈值")]:
            val = ai_filter.get(key)
            if val is not None and (not isinstance(val, (int, float)) or val < 0 or val > 1):
                errors.append({"section": "ai_filter", "field": key, "message": f"{label} 必须在 0.0 ~ 1.0 之间"})

    # === ai ===
    ai = config.get("ai", {})
    if isinstance(ai, dict):
        provider = ai.get("provider", "")
        if provider and provider not in VALID_AI_PROVIDERS_SET:
            errors.append({"section": "ai", "field": "provider", "message": f"provider 必须是已知 adapter 之一（{', '.join(VALID_AI_PROVIDERS_SET)}）"})
        model = ai.get("model", "")
        if model and "/" in model:
            errors.append({"section": "ai", "field": "model", "message": "model 应为纯名，不含 '/' 字符（provider 已拆为独立字段）"})
        timeout = ai.get("timeout", 120)
        if not isinstance(timeout, int) or timeout < 0:
            errors.append({"section": "ai", "field": "timeout", "message": "超时时间必须是非负整数"})
        temperature = ai.get("temperature", 1.0)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            errors.append({"section": "ai", "field": "temperature", "message": "温度必须在 0.0 ~ 2.0 之间"})

    # === ai_analysis ===
    ai_analysis = config.get("ai_analysis", {})
    if isinstance(ai_analysis, dict):
        mode = ai_analysis.get("mode", "")
        if mode and mode not in VALID_AI_MODES:
            errors.append({"section": "ai_analysis", "field": "mode", "message": f"无效的 AI 分析模式: {mode}"})
        max_news = ai_analysis.get("max_news_for_analysis", 50)
        if not isinstance(max_news, int) or max_news < 0:
            errors.append({"section": "ai_analysis", "field": "max_news_for_analysis", "message": "必须是大于等于 0 的整数"})

    # === display ===
    display = config.get("display", {})
    if isinstance(display, dict):
        standalone = display.get("standalone", {})
        if isinstance(standalone, dict):
            for pid in standalone.get("platforms", []):
                if pid not in VALID_PLATFORM_IDS:
                    errors.append({"section": "display", "field": "standalone.platforms", "message": f"未知平台 ID: {pid}"})

    # === tags ===
    tags = config.get("tags", {})
    if isinstance(tags, dict):
        mode = tags.get("mode", "")
        if mode and mode not in VALID_TAGS_MODES:
            errors.append({"section": "tags", "field": "mode", "message": f"无效的标签模式: {mode}"})
        items = tags.get("items", [])
        if mode == "manual":
            if not isinstance(items, list) or len(items) == 0:
                errors.append({"section": "tags", "field": "items", "message": "手动模式下必须配置至少一个标签"})
            else:
                seen_names = set()
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append({"section": "tags", "field": f"items[{idx}]", "message": "标签必须是对象"})
                        continue
                    name = item.get("name", "").strip()
                    if not name:
                        errors.append({"section": "tags", "field": f"items[{idx}].name", "message": "标签名不能为空"})
                    elif name in seen_names:
                        errors.append({"section": "tags", "field": f"items[{idx}].name", "message": f"标签名重复: {name}"})
                    else:
                        seen_names.add(name)
                    desc = item.get("description", "")
                    if not isinstance(desc, str):
                        errors.append({"section": "tags", "field": f"items[{idx}].description", "message": "标签描述必须是字符串"})

    # === storage ===
    storage = config.get("storage", {})
    if isinstance(storage, dict):
        backend = storage.get("backend", "")
        if backend and backend not in VALID_STORAGE_BACKENDS:
            errors.append({"section": "storage", "field": "backend", "message": f"无效的存储后端: {backend}"})

    # === notification ===
    notification = config.get("notification", {})
    if isinstance(notification, dict):
        channels = notification.get("channels", {})
        if isinstance(channels, dict):
            for ch_key, ch_cfg in channels.items():
                if not isinstance(ch_cfg, dict):
                    continue
                webhook_url = ch_cfg.get("webhook_url", "")
                if webhook_url and not _is_valid_url(webhook_url):
                    errors.append({"section": "notification", "field": f"channels.{ch_key}.webhook_url", "message": f"无效的 Webhook URL"})

    return errors


def validate_structured_frequency_words(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """验证结构化频率词配置"""
    errors = []

    if not isinstance(data, dict):
        errors.append({"section": "frequency_words", "field": "", "message": "频率词配置必须是对象"})
        return errors

    # 验证全局过滤词
    global_filters = data.get("global_filters", [])
    if isinstance(global_filters, list):
        for idx, kw in enumerate(global_filters):
            if not isinstance(kw, dict):
                continue
            content = kw.get("content", "")
            kw_type = kw.get("type", "normal")
            if kw_type == "regex" and content:
                try:
                    re.compile(content)
                except re.error as e:
                    errors.append({"section": "frequency_words", "field": f"global_filters[{idx}]", "message": f"正则表达式语法错误: {e}"})

    # 验证词组
    word_groups = data.get("word_groups", [])
    if isinstance(word_groups, list):
        for gidx, group in enumerate(word_groups):
            if not isinstance(group, dict):
                continue
            for kidx, kw in enumerate(group.get("keywords", [])):
                if not isinstance(kw, dict):
                    continue
                content = kw.get("content", "")
                kw_type = kw.get("type", "normal")
                if not content:
                    errors.append({"section": "frequency_words", "field": f"word_groups[{gidx}].keywords[{kidx}]", "message": "关键词内容不能为空"})
                elif kw_type == "regex":
                    try:
                        re.compile(content)
                    except re.error as e:
                        errors.append({"section": "frequency_words", "field": f"word_groups[{gidx}].keywords[{kidx}]", "message": f"正则表达式语法错误: {e}"})

    return errors


def _is_valid_url(url: str) -> bool:
    """简单 URL 验证"""
    if not url:
        return True
    pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(pattern.match(url))

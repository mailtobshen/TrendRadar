#!/usr/bin/env python3
"""
TrendRadar config 恢复脚本

从 output/news/*.db 的 ai_filter_tags 表恢复：
  - config/ai_interests.txt   (AI 兴趣描述)
  - config/frequency_words.txt (频率词 - 使用 AI tag 别名作为 group 别名)

原理：
  1. DB 中 ai_filter_tags 表存储了用户配置的 AI 标签（含 description）
  2. 描述文本中用 、 / 等分隔的关键词就是用户关心的关键词
  3. HTML 报告中的 word-group 名称 == AI tag 名称，说明用户用 tag 名作为 group 别名

用法：
  python3 scripts/recover_config_from_db.py
"""
import sqlite3
import re
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "output" / "news" / "2026-06-05.db"
AI_INTERESTS_OUT = REPO_ROOT / "config" / "ai_interests.txt"
FREQ_WORDS_OUT = REPO_ROOT / "config" / "frequency_words.txt"


def extract_keywords_from_description(description: str) -> list[str]:
    """
    从 AI tag 描述中提取候选关键词。

    描述样例:
      '华为、腾讯、字节跳动、京东、鸿蒙、海思、昇腾、抖音、微信等公司战略、...；
       苹果、微软、谷歌、Anthropic、OpenAI 财报、发布会、产品路线、合作竞争'

    策略:
      1. 按 ；/；/； 分段（多个领域）
      2. 每段按 、 / , 分词
      3. 进一步按空格切分英文
      4. 过滤: 长度 < 2 的词、全是标点的词、纯虚词
    """
    if not description:
        return []

    # 1. 段落分隔（中英文分号）
    segments = re.split(r"[;；]+", description)
    keywords = set()

    for seg in segments:
        # 2. 按多种分隔符切分
        parts = re.split(r"[、，,/／\s]+", seg)
        for p in parts:
            p = p.strip().strip("。、，,;；:：()（）[]【】\"'`")
            if not p:
                continue
            # 3. 长度过滤
            if len(p) < 2:
                continue
            # 4. 长度上限（防止一整段）
            if len(p) > 20:
                continue
            # 5. 跳过纯虚词 / 通用词（不参与匹配但可能误导）
            stopwords = {
                # 通用词
                "的", "和", "与", "及", "或", "等", "了", "是", "在",
                # 单字/过短
                "财报", "发布会", "上市", "产品", "组织", "战略", "监管",
                "竞争", "合作", "出海", "量产", "落地",
                "开源", "策略", "生态", "能力", "模型", "系统", "建设",
                "突破", "应用", "产业", "科研", "上市", "市场",
                # 复合停用词
                "等公司战略", "公司战略", "产品路线", "合作竞争", "生态竞争",
                "开源策略", "等模型能力", "上市交易",
                "供应链", "供应链博弈", "脱钩", "产业脱钩", "外交", "冲突",
                "战争", "制裁", "关税", "商品", "流动性", "全球", "利率",
                "汇率", "通胀", "就业",
                "光伏", "太阳能", "水电", "核能", "电力", "电力系统",
                "新型电力系统", "卫星", "空间站", "飞船", "火星", "登月",
                "深空", "商业航天", "航天",
                "脑机接口", "量子", "基因", "基因工程",
            }
            if p in stopwords:
                continue
            # 6. 去噪：以 等/的/与/或/、结尾的碎片
            if p.endswith(("等", "的", "与", "或", "、", "，", ",", "/")):
                continue
            # 7. 去噪："微信等公司战略" 这种 → 只保留 "微信"
            if "等" in p and len(p.split("等")[0]) <= 4:
                p = p.split("等")[0].strip()
                if len(p) < 2 or p in stopwords:
                    continue
            keywords.add(p)

    return sorted(keywords, key=lambda x: -len(x))  # 长词优先


def extract_subgroups(description: str) -> list[str]:
    """
    从描述中提取分段子标题（用于 keyword group 内进一步分组）。
    分段分隔符：；；
    简单实现：返回每段的前 N 个最具代表性的关键词作为子线索
    """
    segments = re.split(r"[;；]+", description)
    groups = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        groups.append(seg)
    return groups


def recover_from_db():
    """从 DB 读取 ai_filter_tags，恢复两个配置文件"""
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute("""
        SELECT priority, tag, description, version, interests_file, prompt_hash
        FROM ai_filter_tags
        WHERE status = 'active'
        ORDER BY priority
    """)

    tags = cur.fetchall()
    conn.close()

    if not tags:
        print("❌ DB 中无 active 标签")
        sys.exit(1)

    print(f"✅ 从 {DB_PATH.name} 读取 {len(tags)} 个 AI 标签")

    # === 写 ai_interests.txt ===
    write_ai_interests(tags)

    # === 写 frequency_words.txt ===
    write_frequency_words(tags)

    print()
    print("🎉 恢复完成")
    print(f"  - {AI_INTERESTS_OUT.relative_to(REPO_ROOT)}")
    print(f"  - {FREQ_WORDS_OUT.relative_to(REPO_ROOT)}")


def write_ai_interests(tags):
    """生成 ai_interests.txt（用户原格式）"""
    lines = [
        "# AI 兴趣标签配置文件",
        "# 从 output/news/2026-06-05.db 的 ai_filter_tags 表自动恢复",
        f"# 恢复时间: {datetime.now().isoformat()}",
        f"# 共 {len(tags)} 个标签",
        "",
    ]
    for priority, tag, description, version, interests_file, prompt_hash in tags:
        lines.append(f"## [{priority}] {tag}")
        lines.append("")
        lines.append(f"# 描述: {description}")
        lines.append(f"# 优先级: {priority} | 版本: {version}")
        lines.append("")

    AI_INTERESTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    AI_INTERESTS_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ {AI_INTERESTS_OUT.relative_to(REPO_ROOT)} ({len(tags)} 标签)")


def write_frequency_words(tags):
    """
    生成 frequency_words.txt。

    关键设计：
    - [组别名] 使用 AI tag 名称（与 HTML 报告一致）
    - 组内放从 description 提取的关键词
    - 保留 [GLOBAL_FILTER] 段（震惊 filter，upstream 默认）
    - 顶部加注释说明这是从 DB 恢复的
    """
    # 先读现有 frequency_words.txt，保留 [GLOBAL_FILTER] 段中的过滤词
    # 注意：只保留真正的"过滤词"行（非空、非注释、非装饰线）
    existing_global_filter = []
    if FREQ_WORDS_OUT.exists():
        text = FREQ_WORDS_OUT.read_text(encoding="utf-8")
        m = re.search(r"\[GLOBAL_FILTER\]\s*\n(.*?)(?=\n\[)", text, re.DOTALL)
        if m:
            for l in m.group(1).splitlines():
                stripped = l.strip()
                if (stripped
                    and not stripped.startswith("#")
                    and not stripped.startswith("─")
                    and not stripped.startswith("-")
                    and not stripped.startswith("==")
                    and len(stripped) <= 20):  # 真正的词不会很长
                    existing_global_filter.append(stripped)

    if not existing_global_filter:
        existing_global_filter = ["震惊"]  # upstream 默认

    lines = [
        "# ═══════════════════════════════════════════════════════════════",
        "#         TrendRadar 频率词配置文件 - 从 DB 反推恢复版本",
        "# ═══════════════════════════════════════════════════════════════",
        "#",
        "# ⚠️  本文件由 scripts/recover_config_from_db.py 从历史数据库自动恢复",
        f"#     恢复时间: {datetime.now().isoformat()}",
        f"#     数据源: {DB_PATH.relative_to(REPO_ROOT)}",
        f"#     标签数: {len(tags)}",
        "#",
        "# 注意：原 frequency_words.txt 已被 WebUI 覆盖丢失，且 DB 中不存储",
        "# 原始关键词/正则定义。本文件以 AI tag 名称作为 keyword group 别名，",
        "# 组内放从 AI tag 描述文本中提取的关键词。",
        "#",
        "# 文件结构：",
        "#   [GLOBAL_FILTER]  - 全局过滤（保留 upstream 默认）",
        "#   [WORD_GROUPS]    - 词组定义（每个 AI tag = 一个 group）",
        "#",
        "# ═══════════════════════════════════════════════════════════════",
        "",
        "",
        "# ───────────────────────────────────────────────────────────────",
        "#                        全局过滤区",
        "# ───────────────────────────────────────────────────────────────",
        "# 保留 upstream 默认（震惊）",
        "[GLOBAL_FILTER]",
    ]
    lines.extend(existing_global_filter)
    lines.extend([
        "",
        "",
        "# ───────────────────────────────────────────────────────────────",
        "#                        词组定义区",
        "# ───────────────────────────────────────────────────────────────",
        "# 每个 AI tag 对应一个 keyword group，组别名 = tag 名。",
        "# 组内放从 tag 描述中提取的关键词。",
        "",
        "[WORD_GROUPS]",
        "",
    ])

    for priority, tag, description, version, interests_file, prompt_hash in tags:
        keywords = extract_keywords_from_description(description)
        subgroups = extract_subgroups(description)

        lines.append(f"[{tag}]")
        lines.append(f"# 优先级: {priority} | 描述: {description[:80]}{'...' if len(description) > 80 else ''}")
        lines.append("")

        # 如果有多个分段子标题，用注释标注
        if len(subgroups) > 1:
            for i, sub in enumerate(subgroups, 1):
                lines.append(f"# [{i}] {sub[:100]}{'...' if len(sub) > 100 else ''}")

        # 输出关键词
        for kw in keywords:
            lines.append(kw)

        lines.append("")
        lines.append("")

    FREQ_WORDS_OUT.parent.mkdir(parents=True, exist_ok=True)
    FREQ_WORDS_OUT.write_text("\n".join(lines), encoding="utf-8")

    # 统计
    total_keywords = sum(len(extract_keywords_from_description(t[2])) for t in tags)
    print(f"  ✓ {FREQ_WORDS_OUT.relative_to(REPO_ROOT)} ({len(tags)} groups, {total_keywords} keywords)")


if __name__ == "__main__":
    recover_from_db()

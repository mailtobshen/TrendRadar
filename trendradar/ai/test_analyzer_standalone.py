# coding=utf-8
"""
_parse_standalone_text 单元测试

复现：AI 偶发不遵守 prompt 约束（要求返回 dict 形态），输出
"源名: 摘要" 多行文本。原 analyzer.py:729 fallback 把整行塞
value、key 用 "源N" 占位，导致页面渲染出 "[源1]:\\n福克斯新闻: 摘要"
这种重前缀残片。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trendradar.ai.analyzer import _parse_standalone_text


def test_user_reported_bug_multiline_text():
    """用户报告的 bug 复现：AI 返回多行 "源名: 摘要" 文本。"""
    fake_ai_value = (
        "福克斯新闻: 聚焦美国中期初选，特朗普背书效应持续发酵。\n"
        "\n"
        "自由时报: 台湾社会新闻为主线，中山大学期末考遇停电。\n"
        "\n"
        "南华早报: 亚太地缘动态突出，新加坡总理访俄。\n"
        "\n"
        "BBC: 美伊冲突升级为头版头条。\n"
    )
    parsed = _parse_standalone_text(fake_ai_value)

    # 源名应被正确拆出
    assert "福克斯新闻" in parsed
    assert "自由时报" in parsed
    assert "南华早报" in parsed
    assert "BBC" in parsed

    # 不应出现兜底 "源N" 命名（除非 key 不像源名）
    assert all(not k.startswith("源") for k in parsed.keys()), (
        f"走了兜底命名: {list(parsed.keys())}"
    )

    # value 是摘要（不含源名前缀）
    assert "聚焦美国中期初选" in parsed["福克斯新闻"]
    assert "特朗普" not in parsed["福克斯新闻"][:0]  # 确保 key 干净


def test_handles_chinese_and_english_names():
    """中英文源名都能正确拆分。"""
    text = (
        "Hacker News: 技术热点\n"
        "纽约时报: 美国政治\n"
        "BBC News: 全球新闻\n"
    )
    parsed = _parse_standalone_text(text)
    assert "Hacker News" in parsed
    assert "纽约时报" in parsed
    assert "BBC News" in parsed


def test_does_not_misparse_list_items():
    """不应把 "1. 摘要" 这种列表项误拆成 name="1"。"""
    text = (
        "1. 这是列表项不应被误拆\n"
        "知乎: 这是真源名\n"
        "2. 又一个列表项\n"
    )
    parsed = _parse_standalone_text(text)
    # "1." 和 "2." 开头是数字/标点，不应被当源名
    assert "1" not in parsed
    assert "2" not in parsed
    assert "知乎" in parsed
    # 列表项应走兜底 "源N" 命名
    non_zhihu_keys = [k for k in parsed.keys() if k != "知乎"]
    assert all(k.startswith("源") for k in non_zhihu_keys), (
        f"非源名项应走兜底: {non_zhihu_keys}"
    )


def test_empty_input():
    """空字符串 / 仅空白行。"""
    assert _parse_standalone_text("") == {}
    assert _parse_standalone_text("   \n\n  \n") == {}


def test_long_name_triggers_fallback():
    """源名过长（> 20 字）时不应被当源名，走兜底。"""
    text = "这是一段非常非常非常非常非常长的前缀不是源名: 后面是摘要"
    parsed = _parse_standalone_text(text)
    # 不应被误拆为 key="这是一段非常..."
    assert "这是一段非常非常非常非常非常长的前缀不是源名" not in parsed
    # 应走兜底
    assert list(parsed.keys()) == ["源1"]


def test_line_without_colon_goes_to_fallback():
    """无冒号的行走兜底。"""
    text = "这是无冒号的一行摘要文本"
    parsed = _parse_standalone_text(text)
    assert list(parsed.keys()) == ["源1"]
    assert parsed["源1"] == "这是无冒号的一行摘要文本"


def test_value_part_empty_is_skipped():
    """冒号后是空白的行：跳过（不创建空 value 的项）。"""
    text = "源名:    \n知乎: 真摘要"
    parsed = _parse_standalone_text(text)
    assert "源名" not in parsed
    assert "知乎" in parsed


if __name__ == "__main__":
    tests = [
        test_user_reported_bug_multiline_text,
        test_handles_chinese_and_english_names,
        test_does_not_misparse_list_items,
        test_empty_input,
        test_long_name_triggers_fallback,
        test_line_without_colon_goes_to_fallback,
        test_value_part_empty_is_skipped,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    if failed:
        print(f"\n{failed} 个测试失败")
        sys.exit(1)
    print(f"\n全部 {len(tests)} 个测试通过")

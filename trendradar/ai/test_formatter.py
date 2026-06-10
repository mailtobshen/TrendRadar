# coding=utf-8
"""
AI formatter 单元测试

复现并回归保护：
- 独立展示区概括里 key/value 是半成品 JSON 残片时
  （如 AI 调用 json_repair 后产出 "{'Hacker News': 'xxx'" 这种
  dict repr 字符串），不应在 HTML 报告/推送正文中暴露
  "[{'Hacker News': 'xxx']:" 这种半成品 tag。
"""

import sys
from pathlib import Path

# 把项目根加入 path，便于直接 python 跑
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trendradar.ai.formatter import (
    _format_standalone_summaries,
    render_ai_analysis_dingtalk,
    render_ai_analysis_feishu,
    render_ai_analysis_html_rich,
    render_ai_analysis_markdown,
    render_ai_analysis_plain,
    render_ai_analysis_telegram,
)
from trendradar.ai.analyzer import AIAnalysisResult


def test_buggy_key_with_json_repr_does_not_leak():
    """用户报告的 bug 复现：key 是半成品 JSON repr。"""
    summaries = {"{'Hacker News': '话题X'": "内容Y", "知乎": "内容Z"}
    out = _format_standalone_summaries(summaries)

    # 半成品 tag 不应再出现在正文
    assert "[{'Hacker News'" not in out
    # 应走 fallback 命名
    assert "源1" in out
    # 正常 key 保留
    assert "[知乎]:" in out
    # 原内容没丢
    assert "内容Y" in out
    assert "内容Z" in out


def test_value_can_be_dict_safely_serialized():
    """value 是 dict 时（AI 不守约束返了嵌套结构）不应崩溃。"""
    summaries = {"知乎": {"话题1": "desc1"}}
    out = _format_standalone_summaries(summaries)
    assert "[知乎]:" in out
    assert "话题1" in out


def test_empty_and_none_value_dropped():
    """value 为空字符串/None/纯空白：直接丢弃，不渲染 "[源N]:\nNone" 残片。"""
    summaries = {"知乎": "", "微博": None, "贴吧": "   "}
    out = _format_standalone_summaries(summaries)
    assert out == ""


def test_normal_input_unchanged():
    """正常输入的渲染结果不受影响。"""
    summaries = {"知乎": "热议话题A", "Hacker News": "技术热点B"}
    out = _format_standalone_summaries(summaries)
    assert "[知乎]:\n热议话题A" in out
    assert "[Hacker News]:\n技术热点B" in out


def test_empty_key_falls_back_to_placeholder():
    """key 为空字符串/起始 {/[ 时走 fallback 命名。"""
    summaries = {"": "orphan", "{bad": "val", "知乎": "正常"}
    out = _format_standalone_summaries(summaries)
    assert "[源1]:" in out
    assert "[源2]:" in out
    assert "[知乎]:" in out


def test_empty_dict_and_none_input():
    """边界：空 dict / None。"""
    assert _format_standalone_summaries({}) == ""
    assert _format_standalone_summaries(None) == ""


def test_html_rich_renderer_clean():
    """HTML 报告渲染：bug 场景下不泄露 JSON 半成品 tag。"""
    result = AIAnalysisResult(
        success=True,
        standalone_summaries={
            "{'Hacker News': '话题X'": "内容Y",
            "知乎": "内容Z",
        },
    )
    html = render_ai_analysis_html_rich(result)
    assert "[{'Hacker News'" not in html
    assert "源1" in html
    assert "内容Y" in html


def _buggy_summaries_result():
    """构造触发 bug 的 AIAnalysisResult。"""
    return AIAnalysisResult(
        success=True,
        standalone_summaries={
            "{'Hacker News': '话题X'": "内容Y",
            "知乎": "内容Z",
        },
    )


# === 举一反三：所有 6 个渲染通道都不应泄露半成品 JSON tag ===

def test_all_renderers_clean_from_buggy_summaries():
    """举一反三：6 个渲染通道在 bug 输入下都不应暴露 JSON 残片。"""
    buggy_payload = "{'Hacker News'"
    result = _buggy_summaries_result()

    renderers = {
        "markdown": render_ai_analysis_markdown,
        "feishu": render_ai_analysis_feishu,
        "dingtalk": render_ai_analysis_dingtalk,
        "plain": render_ai_analysis_plain,
        "telegram": render_ai_analysis_telegram,
        "html_rich": render_ai_analysis_html_rich,
    }
    for name, fn in renderers.items():
        out = fn(result)
        assert buggy_payload not in out, (
            f"{name} 渲染器仍泄露半成品 JSON tag\n--- output ---\n{out}"
        )
        # fallback 命名应起作用
        assert "源1" in out, f"{name} 渲染器未走 fallback 命名"
        # 正常 key 内容没丢
        assert "知乎" in out, f"{name} 渲染器丢失正常 key"


def test_value_is_dict_dict_preserved_in_all_renderers():
    """value 是 dict 时（AI 偶发返回嵌套结构）所有渲染器应正常输出，不崩溃。"""
    result = AIAnalysisResult(
        success=True,
        standalone_summaries={"知乎": {"话题1": "desc1"}},
    )
    for fn in (
        render_ai_analysis_markdown,
        render_ai_analysis_feishu,
        render_ai_analysis_dingtalk,
        render_ai_analysis_plain,
        render_ai_analysis_telegram,
        render_ai_analysis_html_rich,
    ):
        out = fn(result)
        assert "知乎" in out
        assert "话题1" in out


def test_other_string_fields_with_none_or_dict_via_str_coercion():
    """5 个 str 板块：AI 返回 None / dict 时，经 _parse_board_response 强制 str()，
    渲染器应正常处理（不崩溃、不渲染出 'None'）。"""
    # 模拟 _parse_board_response 的 str() 强制后形态
    result = AIAnalysisResult(
        success=True,
        core_trends="",  # 走 if x: 分支，跳过
        sentiment_controversy="",  # 同上
        signals="",  # 同上
        rss_insights="",  # 同上
        outlook_strategy="",  # 同上
    )
    for fn in (
        render_ai_analysis_markdown,
        render_ai_analysis_feishu,
        render_ai_analysis_dingtalk,
        render_ai_analysis_plain,
        render_ai_analysis_telegram,
        render_ai_analysis_html_rich,
    ):
        out = fn(result)
        # 渲染不应出现字面 "None"
        assert "None" not in out


if __name__ == "__main__":
    # 便于直接 python 跑
    tests = [
        test_buggy_key_with_json_repr_does_not_leak,
        test_value_can_be_dict_safely_serialized,
        test_empty_and_none_value_dropped,
        test_normal_input_unchanged,
        test_empty_key_falls_back_to_placeholder,
        test_empty_dict_and_none_input,
        test_html_rich_renderer_clean,
        test_all_renderers_clean_from_buggy_summaries,
        test_value_is_dict_dict_preserved_in_all_renderers,
        test_other_string_fields_with_none_or_dict_via_str_coercion,
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

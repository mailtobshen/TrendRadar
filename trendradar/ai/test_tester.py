# coding=utf-8
"""
AITester 单测

使用 unittest + unittest.mock 隔离 litellm.completion 的真实网络调用。
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from litellm import APIConnectionError, AuthenticationError, NotFoundError, Timeout


class FakeMessage:
    def __init__(self, content="hi"):
        self.content = content


class FakeChoice:
    def __init__(self, content="hi"):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content="hi", choices=None):
        self.choices = choices if choices is not None else [FakeChoice(content)]


class TestAITesterSuccess(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_success_returns_ok_and_message(self, mock_completion):
        """成功路径：返回 (True, "连接成功", latency_ms>0)"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse(content="hi")
        tester = AITester(model="deepseek/deepseek-chat", api_key="sk-test", api_base="")
        ok, message, latency = tester.test()

        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")
        self.assertIsInstance(latency, int)
        self.assertGreaterEqual(latency, 0)

    @patch("trendradar.ai.tester.completion")
    def test_success_passes_minimal_ping(self, mock_completion):
        """成功路径：传给 completion 的参数是最小 ping"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(model="openai/gpt-4o-mini", api_key="sk-x", api_base="")
        tester.test()

        call = mock_completion.call_args
        params = call.kwargs
        self.assertEqual(params["model"], "openai/gpt-4o-mini")
        self.assertEqual(params["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(params["max_tokens"], 1)
        self.assertEqual(params["num_retries"], 0)
        self.assertEqual(params["timeout"], 30)
        self.assertEqual(params["api_key"], "sk-x")
        self.assertNotIn("api_base", params)


class TestAITesterOptionalFields(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_no_api_key_no_base_does_not_pass_them(self, mock_completion):
        """空 api_key/api_base：params 中不应含这两个键"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(model="x/y", api_key="", api_base="")
        tester.test()

        params = mock_completion.call_args.kwargs
        self.assertNotIn("api_key", params)
        self.assertNotIn("api_base", params)

    @patch("trendradar.ai.tester.completion")
    def test_with_api_base_passes_it(self, mock_completion):
        """非空 api_base：应传 api_base 参数"""
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse()
        tester = AITester(
            model="x/y", api_key="sk-x", api_base="https://api.example.com/v1"
        )
        tester.test()

        params = mock_completion.call_args.kwargs
        self.assertEqual(params["api_base"], "https://api.example.com/v1")


class TestAITesterErrors(unittest.TestCase):
    @patch("trendradar.ai.tester.completion")
    def test_auth_error_message(self, mock_completion):
        """鉴权失败：message 包含"鉴权失败" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = AuthenticationError(
            message="invalid api key", llm_provider="openai", model="x/y"
        )
        tester = AITester(model="x/y", api_key="bad", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("鉴权失败", message)

    @patch("trendradar.ai.tester.completion")
    def test_not_found_message(self, mock_completion):
        """模型不存在：message 包含"模型不存在" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = NotFoundError(
            message="model not found", llm_provider="openai", model="bad/name"
        )
        tester = AITester(model="bad/name", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("模型不存在", message)

    @patch("trendradar.ai.tester.completion")
    def test_timeout_message(self, mock_completion):
        """超时：message 包含"请求超时（30s）" """
        from trendradar.ai.tester import AITester

        mock_completion.side_effect = Timeout(
            message="timed out", llm_provider="openai", model="x/y"
        )
        tester = AITester(model="x/y", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertIn("请求超时（30s）", message)

    @patch("trendradar.ai.tester.completion")
    def test_empty_choices_message(self, mock_completion):
        """模型返回空 choices：message 是"模型返回空响应" """
        from trendradar.ai.tester import AITester

        mock_completion.return_value = FakeResponse(choices=[])
        tester = AITester(model="x/y", api_key="sk-x", api_base="")
        ok, message, _ = tester.test()

        self.assertFalse(ok)
        self.assertEqual(message, "模型返回空响应")


if __name__ == "__main__":
    unittest.main()

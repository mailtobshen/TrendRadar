# coding=utf-8
"""
ModelCatalog 单测

使用 unittest + unittest.mock 隔离 litellm.model_cost 和 requests.get。
"""

import unittest
from unittest.mock import patch, MagicMock

import requests


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, raise_json=False, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self._raise_json = raise_json
        self.text = text

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


class TestModelCatalogProviders(unittest.TestCase):
    def test_list_providers_returns_set_of_slugs(self):
        """list_providers 返回 litellm.provider_list 中所有 slug 的集合"""
        from trendradar.ai.model_catalog import ModelCatalog

        providers = ModelCatalog.list_providers()
        # 至少包含一些知名 provider
        for p in ["openai", "anthropic", "gemini", "deepseek", "minimax"]:
            self.assertIn(p, providers)
        # 是 set 或 list 都可以；只要求可迭代 & 包含上述
        self.assertGreaterEqual(len(providers), 50)


class TestModelCatalogLiteLLMOnly(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_litellm_only_when_no_api_base(self, mock_get):
        """无 api_base → 只返回 LiteLLM catalog 过滤后的列表，不发 HTTP 请求"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {
                "openai/gpt-4o": {"litellm_provider": "openai"},
                "openai/gpt-4o-mini": {"litellm_provider": "openai"},
                "anthropic/claude-3-5-sonnet": {"litellm_provider": "anthropic"},
            },
            clear=True,
        ):
            models = ModelCatalog.get_merged(provider="openai", api_key="", api_base="")

        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4o-mini", models)
        self.assertNotIn("claude-3-5-sonnet", models)
        mock_get.assert_not_called()

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_litellm_only_when_no_api_key(self, mock_get):
        """无 api_key → 不发 HTTP 请求（避免无鉴权调用）"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=True,
        ):
            models = ModelCatalog.get_merged(provider="openai", api_key="", api_base="https://x")

        self.assertIn("gpt-4o", models)
        mock_get.assert_not_called()

    def test_unknown_provider_returns_empty_litellm(self):
        """provider 不在 catalog → 返回空 list（不抛错）"""
        from trendradar.ai.model_catalog import ModelCatalog

        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=True,
        ):
            models = ModelCatalog.get_merged(provider="mycompany-internal", api_key="", api_base="")

        self.assertEqual(models, [])


class TestModelCatalogMerge(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_success_merges_and_dedupes(self, mock_get):
        """provider API 返回的 models 与 LiteLLM 合并去重"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"data": [{"id": "gpt-4o"}, {"id": "gpt-5-new"}]},
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {
                "openai/gpt-4o": {"litellm_provider": "openai"},
                "openai/gpt-4o-mini": {"litellm_provider": "openai"},
            },
            clear=True,
        ):
            models, lite_count, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://api.openai.com/v1"
            )

        self.assertEqual(lite_count, 2)
        self.assertEqual(provider_count, 1)  # gpt-4o 已在 LiteLLM，只有 gpt-5-new 是新的
        self.assertIsNone(provider_error)
        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4o-mini", models)
        self.assertIn("gpt-5-new", models)
        # 去重：gpt-4o 只出现一次
        self.assertEqual(models.count("gpt-4o"), 1)

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_returns_dotted_ids(self, mock_get):
        """provider API 返回的 id 含 `provider/` 前缀时被切掉"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"data": [{"id": "openai/gpt-4o"}]},
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {},
            clear=True,
        ):
            models, _, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://api.openai.com/v1"
            )

        self.assertEqual(provider_count, 1)
        self.assertIsNone(provider_error)
        self.assertEqual(models, ["gpt-4o"])

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_non_openai_format_silently_ignored(self, mock_get):
        """body 不是 {data:[...]} 格式 → 静默忽略，不影响 LiteLLM 部分"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200,
            json_data={"models": ["foo", "bar"]},  # 错误字段名
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=True,
        ):
            models, lite_count, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://x"
            )

        self.assertEqual(lite_count, 1)
        self.assertEqual(provider_count, 0)
        self.assertIsNone(provider_error)
        self.assertIn("gpt-4o", models)

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_invalid_json_silently_ignored(self, mock_get):
        """200 + 非 JSON body → 静默忽略"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(
            status_code=200, raise_json=True, text="<html>not json</html>"
        )
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=True,
        ):
            models, lite_count, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="sk-x", api_base="https://x"
            )

        self.assertEqual(lite_count, 1)
        self.assertEqual(provider_count, 0)
        self.assertIsNone(provider_error)
        self.assertIn("gpt-4o", models)


class TestModelCatalogErrors(unittest.TestCase):
    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_401_message(self, mock_get):
        """401 → 抛 ProviderAPIError 含鉴权提示"""
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.return_value = FakeResponse(status_code=401, text="Unauthorized")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="bad", api_base="https://x"
            )
        self.assertIn("鉴权失败", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_404_message(self, mock_get):
        """404 → ProviderAPIError 含"不支持 /models 端点" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.return_value = FakeResponse(status_code=404, text="Not Found")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="custom", api_key="k", api_base="https://x"
            )
        self.assertIn("/models 端点", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_timeout_message(self, mock_get):
        """Timeout → ProviderAPIError 含"请求 provider 超时" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.side_effect = requests.Timeout("timed out")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="k", api_base="https://x"
            )
        self.assertIn("超时", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_connection_error_message(self, mock_get):
        """ConnectionError → ProviderAPIError 含"网络连接失败" """
        from trendradar.ai.model_catalog import ModelCatalog, ProviderAPIError

        mock_get.side_effect = requests.ConnectionError("dns fail")
        with self.assertRaises(ProviderAPIError) as ctx:
            ModelCatalog._fetch_provider_models(
                provider="openai", api_key="k", api_base="https://x"
            )
        self.assertIn("网络连接失败", str(ctx.exception))

    @patch("trendradar.ai.model_catalog.requests.get")
    def test_provider_api_401_returns_error_in_merged(self, mock_get):
        """Provider API 401 → get_merged_with_counts 返回 provider_error 字符串，models 仍可用"""
        from trendradar.ai.model_catalog import ModelCatalog

        mock_get.return_value = FakeResponse(status_code=401, text="Unauthorized")
        with patch.dict(
            "trendradar.ai.model_catalog.litellm.model_cost",
            {"openai/gpt-4o": {"litellm_provider": "openai"}},
            clear=True,
        ):
            models, lite_count, provider_count, provider_error = ModelCatalog.get_merged_with_counts(
                provider="openai", api_key="bad", api_base="https://x"
            )

        self.assertEqual(lite_count, 1)
        self.assertIn("gpt-4o", models)  # LiteLLM 部分不受影响
        self.assertIsNotNone(provider_error)
        self.assertIn("鉴权失败", provider_error)


class TestModelCatalogCurated(unittest.TestCase):
    def test_list_curated_providers_returns_6_items(self):
        """CURATED_PROVIDERS 列表固定 6 项，按协议家族筛选"""
        from trendradar.ai.model_catalog import ModelCatalog, CURATED_PROVIDERS

        providers = ModelCatalog.list_curated_providers()
        # 6 项硬编码
        self.assertEqual(len(providers), 6)
        # 必须包含的核心 3 项
        for p in ["openai", "anthropic", "gemini"]:
            self.assertIn(p, providers)
        # 顺序固定（用户看到 6 项的固定顺序）
        self.assertEqual(
            providers,
            ["openai", "anthropic", "gemini", "bedrock", "vertex_ai", "azure"],
        )
        # CURATED_PROVIDERS 是个 list
        self.assertIsInstance(CURATED_PROVIDERS, list)


if __name__ == "__main__":
    unittest.main()

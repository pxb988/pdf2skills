"""Tests for LLM client."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.llm.client import ChatMessage, LLMClient, LLMClientError
from src.pipeline.config import LLMProviderConfig


class TestChatMessage:
    def test_fields(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestLLMClient:
    def _make_config(self, **overrides):
        defaults = {
            "api_key": "sk-test",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        }
        defaults.update(overrides)
        return LLMProviderConfig(**defaults)

    def test_init_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            LLMClient(LLMProviderConfig())

    def test_init_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url"):
            LLMClient(LLMProviderConfig(api_key="k"))

    def test_model_property(self):
        client = LLMClient(self._make_config())
        assert client.model == "gpt-4o"

    @patch("src.llm.client.requests.post")
    def test_chat_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello back!"}}]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(self._make_config())
        result = client.chat([ChatMessage(role="user", content="Hello")])

        assert result == "Hello back!"
        mock_post.assert_called_once()
        url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url", "")
        assert "chat/completions" in url

    @patch("src.llm.client.requests.post")
    def test_chat_api_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        client = LLMClient(self._make_config())
        with pytest.raises(LLMClientError, match="401"):
            client.chat([ChatMessage(role="user", content="Hi")])

    @patch("src.llm.client.requests.post")
    def test_chat_no_choices(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        mock_post.return_value = mock_resp

        client = LLMClient(self._make_config())
        with pytest.raises(LLMClientError, match="no choices"):
            client.chat([ChatMessage(role="user", content="Hi")])

    @patch("src.llm.client.requests.post")
    def test_chat_url_construction(self, mock_post):
        """Verify trailing slash in base_url is handled."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = mock_resp

        config = self._make_config(base_url="https://api.example.com/v1/")
        client = LLMClient(config)
        client.chat([ChatMessage(role="user", content="test")])

        url = mock_post.call_args[1].get("url") or mock_post.call_args[0][0]
        assert url == "https://api.example.com/v1/chat/completions"

    @patch("src.llm.client.requests.post")
    def test_chat_request_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(self._make_config(model="deepseek-chat"))
        client.chat(
            [ChatMessage(role="system", content="sys"), ChatMessage(role="user", content="hi")],
            max_tokens=2048,
            temperature=0.5,
        )

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "deepseek-chat"
        assert payload["max_tokens"] == 2048
        assert payload["temperature"] == 0.5
        assert len(payload["messages"]) == 2

    @patch("src.llm.client.requests.post")
    def test_chat_auth_header(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = mock_resp

        client = LLMClient(self._make_config(api_key="sk-secret"))
        client.chat([ChatMessage(role="user", content="x")])

        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-secret"

"""Unit tests for Ollama client and mock responses."""

from unittest.mock import patch, MagicMock
import pytest
from jarvis.llm.ollama_client import (
    OllamaClient,
    OllamaUnavailableError,
    ModelNotFoundError,
    test_ai_connection as verify_ai_connection,
)


def test_ollama_client_init():
    """Verify client URL formatting and defaults."""
    client = OllamaClient("http://localhost:11434/")
    assert client.base_url == "http://localhost:11434"
    assert client.model == "gemma4:e2b"


@patch("requests.get")
def test_check_connection_success(mock_get):
    """Test connection check when Ollama is running."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    client = OllamaClient()
    assert client.check_connection() is True


@patch("requests.get")
def test_check_connection_failure(mock_get):
    """Test connection check when Ollama is unreachable."""
    mock_get.side_effect = Exception("Connection refused")

    client = OllamaClient()
    assert client.check_connection() is False


@patch("requests.get")
def test_list_models(mock_get):
    """Test listing models from tags endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "qwen2.5:3b"}, {"name": "gemma4:e2b"}]
    }
    mock_get.return_value = mock_resp

    client = OllamaClient()
    models = client.list_models()
    assert "qwen2.5:3b" in models
    assert "gemma4:e2b" in models


@patch("requests.post")
def test_chat_stream_mock(mock_post):
    """Test streaming chunk aggregation and token callback."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'{"message": {"role": "assistant", "content": "Hello"}, "done": false}',
        b'{"message": {"role": "assistant", "content": " World!"}, "done": true}',
    ]
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_post.return_value = mock_resp

    client = OllamaClient()
    tokens = []
    result = client.chat_stream(
        messages=[{"role": "user", "content": "hi"}],
        on_token=lambda t: tokens.append(t),
    )

    assert result == "Hello World!"
    assert tokens == ["Hello", " World!"]


@patch("requests.post")
@patch("requests.get")
def test_test_ai_connection_success(mock_get, mock_post):
    """Test full AI connection check with mocked successful inference."""
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"models": [{"name": "gemma4:e2b"}]}
    mock_get.return_value = mock_get_resp

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.json.return_value = {"message": {"content": "pong"}}
    mock_post.return_value = mock_post_resp

    res = verify_ai_connection(base_url="http://localhost:11434", model="gemma4:e2b")
    assert res["success"] is True
    assert res["model"] == "gemma4:e2b"
    assert res["sample_response"] == "pong"


@patch("requests.get")
def test_test_ai_connection_missing_model(mock_get):
    """Test AI connection check when target model is missing."""
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"models": [{"name": "other-model:latest"}]}
    mock_get.return_value = mock_get_resp

    res = verify_ai_connection(base_url="http://localhost:11434", model="gemma4:e2b")
    assert res["success"] is False
    assert "not found" in res["message"]


@patch("requests.get")
def test_get_loaded_models(mock_get):
    """Test querying active models from /api/ps endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "gemma4:e2b", "size_vram": 330783784}]
    }
    mock_get.return_value = mock_resp

    client = OllamaClient()
    loaded = client.get_loaded_models()
    assert len(loaded) == 1
    assert loaded[0]["name"] == "gemma4:e2b"
    assert loaded[0]["size_vram"] == 330783784


@patch("requests.post")
def test_warmup(mock_post):
    """Test background warm-up ping."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    client = OllamaClient()
    success = client.warmup("gemma4:e2b")
    assert success is True
    assert "gemma4:e2b" in client._verified_models


@patch("requests.post")
def test_chat_stream_metrics_collection(mock_post):
    """Test that timing and token generation metrics are collected from done chunk."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'{"message": {"role": "assistant", "content": "Hello"}, "done": false}',
        b'{"message": {"role": "assistant", "content": "!"}, "done": true, "total_duration": 500000000, "load_duration": 10000000, "prompt_eval_count": 5, "prompt_eval_duration": 50000000, "eval_count": 2, "eval_duration": 100000000}',
    ]
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_post.return_value = mock_resp

    client = OllamaClient()
    result = client.chat_stream(messages=[{"role": "user", "content": "hi"}])
    assert result == "Hello!"
    assert client.last_metrics["total_duration_ms"] == 500.0
    assert client.last_metrics["load_duration_ms"] == 10.0
    assert client.last_metrics["eval_count"] == 2
    assert client.last_metrics["tokens_per_sec"] == 20.0


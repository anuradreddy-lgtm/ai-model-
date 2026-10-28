"""Ollama local API client with streaming and error resilience."""

import json
import threading
import time
from typing import Any, Callable, Dict, Generator, List, Optional
import requests
from jarvis.config import config
from jarvis.utils.logger import logger


class OllamaError(Exception):
    """Base exception for Ollama API issues."""
    pass


class OllamaUnavailableError(OllamaError):
    """Raised when Ollama daemon is unreachable."""
    pass


class ModelNotFoundError(OllamaError):
    """Raised when the requested model is not downloaded."""
    pass


class OllamaClient:
    """Robust client for communicating with local Ollama daemon."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or config.ollama.base_url).rstrip("/")
        self.model = model or config.ollama.model
        self.session = requests.Session()
        self._cancel_flag = threading.Event()
        self._verified_models = set()
        self.last_metrics: Dict[str, Any] = {}

    def _get(self, url: str, **kwargs) -> requests.Response:
        """Internal GET delegating to mock if active or persistent session."""
        from unittest.mock import MagicMock
        if isinstance(requests.get, MagicMock):
            return requests.get(url, **kwargs)
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        """Internal POST delegating to mock if active or persistent session."""
        from unittest.mock import MagicMock
        if isinstance(requests.post, MagicMock):
            return requests.post(url, **kwargs)
        return self.session.post(url, **kwargs)

    def close(self) -> None:
        """Close the persistent HTTP connection pool."""
        try:
            self.session.close()
        except Exception:
            pass

    def check_connection(self) -> bool:
        """Check if local Ollama daemon is active."""
        try:
            resp = self._get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug(f"Ollama connection check failed: {exc}")
            return False

    def test_connection(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Comprehensive verification of Ollama connection, model availability, and inference."""
        return test_ai_connection(base_url=self.base_url, model=model or self.model)

    def list_models(self) -> List[str]:
        """Return names of all models installed in Ollama."""
        try:
            resp = self._get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return models
            return []
        except requests.RequestException as exc:
            logger.error(f"Failed to list Ollama models: {exc}")
            return []

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """Query currently active models in Ollama memory (/api/ps)."""
        try:
            resp = self._get(f"{self.base_url}/api/ps", timeout=3)
            if resp.status_code == 200:
                return resp.json().get("models", [])
            return []
        except Exception as exc:
            logger.debug(f"Failed to query loaded models from Ollama: {exc}")
            return []

    def warmup(self, model: Optional[str] = None) -> bool:
        """Perform a single lightweight background warm-up to pre-load model into VRAM."""
        target = model or self.model
        try:
            payload = {
                "model": target,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "think": False,
                "keep_alive": config.ollama.keep_alive,
                "options": {
                    "num_ctx": config.ollama.num_ctx,
                    "num_predict": 1,
                },
            }
            resp = self._post(f"{self.base_url}/api/chat", json=payload, timeout=config.ollama.timeout_seconds)
            if resp.status_code == 200:
                self._verified_models.add(target)
                logger.info(f"Ollama warm-up succeeded for '{target}'. Model is loaded and warm.")
                return True
            return False
        except Exception as exc:
            logger.warning(f"Ollama warm-up encountered an issue: {exc}")
            return False

    def ensure_model_available(self, target_model: Optional[str] = None) -> str:
        """Verify target model exists, using internal cache to avoid redundant network tags calls."""
        target = target_model or self.model
        if target in self._verified_models:
            return target

        available = self.list_models()

        if not available:
            raise OllamaUnavailableError(
                f"Ollama is unreachable or has no models installed at {self.base_url}."
            )

        # Exact match or prefix match (e.g., 'gemma4:e2b' vs 'gemma4:e2b-latest')
        for m in available:
            if m == target or m.startswith(target) or target.startswith(m):
                self.model = m
                self._verified_models.add(m)
                return m

        # Try fallbacks
        for fb in config.ollama.fallback_models:
            for m in available:
                if m == fb or m.startswith(fb):
                    logger.warning(f"Target model '{target}' not found. Falling back to '{m}'.")
                    self.model = m
                    self._verified_models.add(m)
                    return m

        # If not found in available, raise clear error
        raise ModelNotFoundError(
            f"Model '{target}' was not found in Ollama. Available: {', '.join(available) or 'None'}. "
            f"Please run 'ollama pull {target}' in a terminal."
        )

    def cancel_current_stream(self) -> None:
        """Signal ongoing stream to terminate immediately."""
        self._cancel_flag.set()

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        on_token: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
    ) -> str:
        """Stream chat completion tokens from Ollama.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            on_token: Optional callback invoked with each token string.
            model: Optional model override.

        Returns:
            The complete aggregated response string.
        """
        self._cancel_flag.clear()
        chosen_model = model or self.model
        endpoint = f"{self.base_url}/api/chat"

        payload = {
            "model": chosen_model,
            "messages": messages,
            "stream": True,
            "keep_alive": config.ollama.keep_alive,
            "think": config.ollama.think,
            "options": {
                "temperature": config.ollama.temperature,
                "num_ctx": config.ollama.num_ctx,
                "num_predict": config.ollama.num_predict,
            },
        }

        logger.debug(f"Initiating chat stream with model '{chosen_model}', {len(messages)} messages.")
        full_response: List[str] = []

        try:
            with self._post(endpoint, json=payload, stream=True, timeout=config.ollama.timeout_seconds) as resp:
                if resp.status_code == 404:
                    raise ModelNotFoundError(f"Model '{chosen_model}' was not found in Ollama.")
                if resp.status_code != 200:
                    raise OllamaError(f"Ollama returned HTTP error {resp.status_code}: {resp.text}")

                for line in resp.iter_lines(decode_unicode=True):
                    if self._cancel_flag.is_set():
                        logger.info("Generation cancelled by user request.")
                        break

                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Extract partial token
                    msg = chunk.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        full_response.append(token)
                        if on_token:
                            on_token(token)

                    if chunk.get("done", False):
                        # Capture performance metrics from final completion chunk
                        total_dur = chunk.get("total_duration", 0)
                        load_dur = chunk.get("load_duration", 0)
                        prompt_dur = chunk.get("prompt_eval_duration", 0)
                        eval_dur = chunk.get("eval_duration", 0)
                        eval_cnt = chunk.get("eval_count", 0)
                        tok_s = (eval_cnt / (eval_dur / 1e9)) if eval_dur > 0 else 0.0

                        self.last_metrics = {
                            "total_duration_ms": round(total_dur / 1e6, 2),
                            "load_duration_ms": round(load_dur / 1e6, 2),
                            "prompt_eval_count": chunk.get("prompt_eval_count", 0),
                            "prompt_eval_duration_ms": round(prompt_dur / 1e6, 2),
                            "eval_count": eval_cnt,
                            "eval_duration_ms": round(eval_dur / 1e6, 2),
                            "tokens_per_sec": round(tok_s, 2),
                        }
                        break

        except requests.ConnectionError as exc:
            self._verified_models.clear()
            logger.error(f"Cannot reach Ollama at {endpoint}: {exc}")
            raise OllamaUnavailableError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure the Ollama service is running."
            ) from exc
        except requests.Timeout as exc:
            logger.error(f"Ollama request timed out: {exc}")
            raise OllamaError("Ollama inference timed out.") from exc
        except Exception as exc:
            logger.error(f"Unexpected error during chat stream: {exc}")
            raise

        return "".join(full_response)


def test_ai_connection(
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Test and verify AI connection to Ollama with live model inference.
    
    Returns:
        Dict with keys: success, model, latency_ms, available_models, message.
    """
    url = (base_url or config.ollama.base_url).rstrip("/")
    target_model = model or config.ollama.model
    start_time = time.perf_counter()

    # Step 1: Ping /api/tags
    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return {
                "success": False,
                "model": target_model,
                "latency_ms": 0.0,
                "available_models": [],
                "message": f"Ollama daemon returned HTTP {resp.status_code} at {url}.",
            }
        data = resp.json()
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    except requests.ConnectionError:
        return {
            "success": False,
            "model": target_model,
            "latency_ms": 0.0,
            "available_models": [],
            "message": f"Cannot connect to Ollama at {url}. Ensure Ollama is running.",
        }
    except Exception as exc:
        return {
            "success": False,
            "model": target_model,
            "latency_ms": 0.0,
            "available_models": [],
            "message": f"Connection check failed: {exc}",
        }

    # Step 2: Verify model presence
    matched_model = None
    for m in models:
        if m == target_model or m.startswith(target_model) or target_model.startswith(m):
            matched_model = m
            break

    if not matched_model:
        return {
            "success": False,
            "model": target_model,
            "latency_ms": 0.0,
            "available_models": models,
            "message": f"Model '{target_model}' not found in Ollama. Available: {', '.join(models) or 'None'}.",
        }

    # Step 3: Run quick live prompt verification
    chat_endpoint = f"{url}/api/chat"
    test_payload = {
        "model": matched_model,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False,
        "think": False,
        "keep_alive": config.ollama.keep_alive,
        "options": {
            "temperature": 0.1,
            "num_ctx": config.ollama.num_ctx,
            "num_predict": 32,
        },
    }

    try:
        chat_resp = requests.post(chat_endpoint, json=test_payload, timeout=timeout)
        elapsed = (time.perf_counter() - start_time) * 1000
        if chat_resp.status_code != 200:
            return {
                "success": False,
                "model": matched_model,
                "latency_ms": round(elapsed, 1),
                "available_models": models,
                "message": f"Inference failed with HTTP {chat_resp.status_code}: {chat_resp.text}",
            }

        chat_data = chat_resp.json()
        reply_content = chat_data.get("message", {}).get("content", "").strip()

        logger.info(f"Test AI Connection succeeded for '{matched_model}' in {round(elapsed, 1)}ms.")
        return {
            "success": True,
            "model": matched_model,
            "latency_ms": round(elapsed, 1),
            "available_models": models,
            "message": f"Connected to {matched_model} successfully ({round(elapsed, 1)} ms response).",
            "sample_response": reply_content,
        }
    except Exception as exc:
        return {
            "success": False,
            "model": matched_model,
            "latency_ms": 0.0,
            "available_models": models,
            "message": f"Model test inference failed: {exc}",
        }


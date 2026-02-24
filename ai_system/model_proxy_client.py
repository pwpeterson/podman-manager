"""HTTP client for the local model-proxy service.

This client targets the FastAPI model-proxy instance (default: http://localhost:8002)
which exposes OpenAI-compatible endpoints:
- GET  /v1/models
- POST /v1/chat/completions

It also exposes assistant-model management endpoints:
- GET    /v1/assistant/model
- POST   /v1/assistant/model   {"model": "model-id"}
- DELETE /v1/assistant/model

The PM app will use this client to:
1) list available models
2) show the currently configured assistant model
3) allow interactive selection of a model for troubleshooting
4) run AI troubleshooting prompts via /v1/chat/completions
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, cast

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class ModelProxyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelProxyModel:
    """Represents a model returned by GET /v1/models."""

    id: str
    owned_by: Optional[str] = None
    context_length: Optional[int] = None
    supports_streaming: Optional[bool] = None


class ModelProxyClient:
    """Thin HTTP client for model-proxy.

    Timeout behavior:
    - Uses separate connect/read timeouts by default: (5s connect, 180s read).
    - You can override via environment variables:
        * MODEL_PROXY_CONNECT_TIMEOUT (seconds)
        * MODEL_PROXY_READ_TIMEOUT (seconds)
    - Or pass `timeout=` explicitly (requests supports float or (connect, read) tuple).
    """

    # Provider-specific quirks:
    # - Moonshot Kimi models currently only accept temperature=1 (fixed sampling setting).
    #   We normalize requests here so call sites can use a consistent default.
    _MOONSHOT_FIXED_TEMP_PREFIXES: tuple[str, ...] = ("kimi-", "moonshotai/kimi-")

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float | tuple[float, float] | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("MODEL_PROXY_URL") or "http://localhost:8002"
        ).rstrip("/")
        self.timeout = timeout if timeout is not None else self._default_timeout()

    def _normalize_temperature(self, *, model: str, temperature: float) -> float:
        """Normalize temperature for providers/models with strict constraints."""
        if any(model.startswith(p) for p in self._MOONSHOT_FIXED_TEMP_PREFIXES):
            return 1.0
        return temperature

    def _ensure_requests(self) -> None:
        if requests is None:
            raise ModelProxyError("requests library is not available")

    @staticmethod
    def _default_timeout() -> tuple[float, float]:
        """Return default (connect_timeout, read_timeout) for requests."""
        connect_s = float(os.getenv("MODEL_PROXY_CONNECT_TIMEOUT", "5"))
        read_s = float(os.getenv("MODEL_PROXY_READ_TIMEOUT", "180"))
        return (connect_s, read_s)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        self._ensure_requests()

        req = cast(Any, requests)

        try:
            resp = req.request(
                method=method,
                url=self._url(path),
                json=json_body,
                headers=headers,
                timeout=self.timeout,
            )
        except Exception as e:  # requests.* exceptions
            raise ModelProxyError(f"model-proxy request failed: {e}") from e

        if resp.status_code >= 400:
            # model-proxy returns JSON error objects with {"detail": ...}
            detail: str
            try:
                payload = resp.json()
                detail = str(payload.get("detail", payload))
            except Exception:
                detail = resp.text.strip() or f"HTTP {resp.status_code}"

            raise ModelProxyError(f"model-proxy error {resp.status_code}: {detail}")

        if not resp.content:
            return None

        # Prefer JSON
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return resp.json()

        # Fallback text
        return resp.text

    # --- Public API -------------------------------------------------

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def list_models(self) -> List[ModelProxyModel]:
        """Return model list from GET /v1/models."""
        data = self._request("GET", "/v1/models")
        models: List[ModelProxyModel] = []

        for item in (data or {}).get("data", []):
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id:
                models.append(
                    ModelProxyModel(
                        id=model_id,
                        owned_by=(
                            item.get("owned_by")
                            if isinstance(item.get("owned_by"), str)
                            else None
                        ),
                        context_length=(
                            item.get("context_length")
                            if isinstance(item.get("context_length"), int)
                            else None
                        ),
                        supports_streaming=(
                            item.get("supports_streaming")
                            if isinstance(item.get("supports_streaming"), bool)
                            else None
                        ),
                    )
                )

        # Stable order for UI
        return sorted(models, key=lambda m: (m.owned_by or "", m.id))

    def get_assistant_model_status(self) -> Dict[str, Any]:
        """Return status object from GET /v1/assistant/model."""
        return self._request("GET", "/v1/assistant/model")

    def get_assistant_model(self) -> Optional[str]:
        status = self.get_assistant_model_status()
        model = status.get("assistant_model")
        return model if isinstance(model, str) and model else None

    def set_assistant_model(self, model_id: str) -> Dict[str, Any]:
        if not model_id or not isinstance(model_id, str):
            raise ValueError("model_id must be a non-empty string")
        return self._request(
            "POST", "/v1/assistant/model", json_body={"model": model_id}
        )

    def clear_assistant_model(self) -> Dict[str, Any]:
        return self._request("DELETE", "/v1/assistant/model")

    def chat_completions(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        stream: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call POST /v1/chat/completions and return the raw JSON response."""
        if not model or not isinstance(model, str):
            raise ValueError("model must be a non-empty string")

        temperature = self._normalize_temperature(model=model, temperature=temperature)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if extra:
            payload.update(extra)

        return self._request(
            "POST",
            "/v1/chat/completions",
            json_body=payload,
            headers={"Content-Type": "application/json"},
        )

    def chat_completion_text(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.1,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Convenience wrapper: return the first choice message content."""
        data = self.chat_completions(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            extra=extra,
        )

        try:
            choices = data.get("choices", [])
            if not choices:
                return None
            choice0 = choices[0]
            if not isinstance(choice0, dict):
                return None
            msg = choice0.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                return content.strip() if isinstance(content, str) else None
            text = choice0.get("text")
            return text.strip() if isinstance(text, str) else None
        except Exception:
            return None

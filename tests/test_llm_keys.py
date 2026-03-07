"""LLM provider key validation tests.

Each test checks that an API key is valid by hitting a lightweight endpoint
(e.g. /models or /chat/completions with minimal tokens).
Tests are skipped when the corresponding env var is not set.

Marked with pytest.mark.integration — not included in normal CI runs.
"""
import os

import httpx
import pytest

pytestmark = pytest.mark.integration

TIMEOUT = 15


# ── Helpers ──────────────────────────────────────────────

def _list_models(base_url: str, api_key: str, *, auth_header: str = "Authorization", auth_prefix: str = "Bearer ") -> httpx.Response:
    """GET /models — the lightest possible API call."""
    return httpx.get(
        f"{base_url}/models",
        headers={auth_header: f"{auth_prefix}{api_key}"},
        timeout=TIMEOUT,
    )


def _tiny_chat(base_url: str, api_key: str, model: str, *, auth_header: str = "Authorization", auth_prefix: str = "Bearer ") -> httpx.Response:
    """Minimal chat completion (1 token) as a key check fallback."""
    return httpx.post(
        f"{base_url}/chat/completions",
        headers={auth_header: f"{auth_prefix}{api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        timeout=TIMEOUT,
    )


# ── OpenAI ───────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
class TestOpenAI:
    BASE = "https://api.openai.com/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["OPENAI_API_KEY"])
        assert r.status_code == 200, f"OpenAI /models failed: {r.status_code} {r.text[:200]}"
        assert len(r.json().get("data", [])) > 0


# ── Anthropic ────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
class TestAnthropic:
    def test_list_models(self):
        r = httpx.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Anthropic /models failed: {r.status_code} {r.text[:200]}"


# ── OpenRouter ───────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
class TestOpenRouter:
    BASE = "https://openrouter.ai/api/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["OPENROUTER_API_KEY"])
        assert r.status_code == 200, f"OpenRouter /models failed: {r.status_code} {r.text[:200]}"


# ── Groq ─────────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
class TestGroq:
    BASE = "https://api.groq.com/openai/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["GROQ_API_KEY"])
        assert r.status_code == 200, f"Groq /models failed: {r.status_code} {r.text[:200]}"


# ── Google Gemini ────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
class TestGemini:
    def test_list_models(self):
        r = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": os.environ["GEMINI_API_KEY"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Gemini /models failed: {r.status_code} {r.text[:200]}"


# ── xAI / Grok ───────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("XAI_API_KEY"), reason="XAI_API_KEY not set")
class TestXAI:
    BASE = "https://api.x.ai/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["XAI_API_KEY"])
        assert r.status_code == 200, f"xAI /models failed: {r.status_code} {r.text[:200]}"


# ── Mistral ──────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("MISTRAL_API_KEY"), reason="MISTRAL_API_KEY not set")
class TestMistral:
    BASE = "https://api.mistral.ai/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["MISTRAL_API_KEY"])
        assert r.status_code == 200, f"Mistral /models failed: {r.status_code} {r.text[:200]}"


# ── Cerebras ─────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("CEREBRAS_API_KEY"), reason="CEREBRAS_API_KEY not set")
class TestCerebras:
    BASE = "https://api.cerebras.ai/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["CEREBRAS_API_KEY"])
        assert r.status_code == 200, f"Cerebras /models failed: {r.status_code} {r.text[:200]}"


# ── Cohere ───────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("COHERE_API_KEY"), reason="COHERE_API_KEY not set")
class TestCohere:
    BASE = "https://api.cohere.com/compatibility/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["COHERE_API_KEY"])
        assert r.status_code == 200, f"Cohere /models failed: {r.status_code} {r.text[:200]}"


# ── SambaNova ────────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("SAMBANOVA_API_KEY"), reason="SAMBANOVA_API_KEY not set")
class TestSambaNova:
    BASE = "https://api.sambanova.ai/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["SAMBANOVA_API_KEY"])
        assert r.status_code == 200, f"SambaNova /models failed: {r.status_code} {r.text[:200]}"


# ── HuggingFace ──────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("HF_API_KEY"), reason="HF_API_KEY not set")
class TestHuggingFace:
    BASE = "https://router.huggingface.co/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["HF_API_KEY"])
        assert r.status_code == 200, f"HuggingFace /models failed: {r.status_code} {r.text[:200]}"


# ── GitHub Models ────────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("GITHUB_MODELS_PAT"), reason="GITHUB_MODELS_PAT not set")
class TestGitHubModels:
    BASE = "https://models.inference.ai.azure.com"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["GITHUB_MODELS_PAT"])
        assert r.status_code == 200, f"GitHub Models /models failed: {r.status_code} {r.text[:200]}"


# ── Alibaba / Qwen ───────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("DASHSCOPE_API_KEY"), reason="DASHSCOPE_API_KEY not set")
class TestDashScope:
    BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def test_list_models(self):
        r = _list_models(self.BASE, os.environ["DASHSCOPE_API_KEY"])
        assert r.status_code == 200, f"DashScope /models failed: {r.status_code} {r.text[:200]}"

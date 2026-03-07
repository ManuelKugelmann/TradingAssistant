# Free LLM API Endpoints for LibreChat

All providers below offer free API tiers with OpenAI-compatible endpoints.
Preconfigured in `librechat.yaml` (commented out) — uncomment to enable.

Reference: [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)

---

## Quick Setup

1. Sign up at the provider URL (all free, just email)
2. Copy your API key
3. Add it to `~/LibreChat/.env` (or `ta env`)
4. Uncomment the matching endpoint in `librechat.yaml` (`ta yaml`)
5. Restart: `ta restart`

---

## Provider List

### Groq — Fastest free inference

| | |
|---|---|
| **Signup** | https://console.groq.com/keys |
| **Free limits** | 14,400 req/day (varies by model), 6K-30K tokens/min |
| **Best models** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768` |
| **Env var** | `GROQ_API_KEY=gsk_...` |
| **Notes** | Custom LPU hardware, extremely fast. Best free option for daily use. |

### Google Gemini — Largest free context

| | |
|---|---|
| **Signup** | https://aistudio.google.com/apikey |
| **Free limits** | 15 RPM, 1M tokens/day (Gemini Flash) |
| **Best models** | `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash` |
| **Env var** | `GEMINI_API_KEY=AI...` |
| **Notes** | Very generous token limits. 1M context on paid tier. |

### xAI / Grok — Free Grok access

| | |
|---|---|
| **Signup** | https://console.x.ai |
| **Free limits** | 30 RPM, free tier with monthly credit |
| **Best models** | `grok-3-mini`, `grok-3-mini-fast` |
| **Env var** | `XAI_API_KEY=xai-...` |
| **Notes** | Strong reasoning model. Free $25/month credit (as of early 2025). |

### Mistral — Best European provider

| | |
|---|---|
| **Signup** | https://console.mistral.ai/api-keys |
| **Free limits** | 1 req/sec, 500K tokens/min |
| **Best models** | `mistral-small-latest`, `codestral-latest` |
| **Env var** | `MISTRAL_API_KEY=...` |
| **Notes** | Codestral is great for code tasks. Free tier very generous. |

### Cerebras — Fast open-model inference

| | |
|---|---|
| **Signup** | https://cloud.cerebras.ai |
| **Free limits** | 30 RPM, 14,400 req/day |
| **Best models** | `llama-3.3-70b`, `qwen-3-235b`, `llama-3.1-8b` |
| **Env var** | `CEREBRAS_API_KEY=csk-...` |
| **Notes** | Very fast inference on open models. |

### Cohere — Command R family

| | |
|---|---|
| **Signup** | https://dashboard.cohere.com/api-keys |
| **Free limits** | 20 RPM, 1,000 req/month |
| **Best models** | `command-a-03-2025`, `command-r-plus-08-2024` |
| **Env var** | `COHERE_API_KEY=...` |
| **Notes** | Good for RAG use cases. Lower monthly limit but capable models. |

### SambaNova — Trial credits

| | |
|---|---|
| **Signup** | https://cloud.sambanova.ai |
| **Free limits** | $5 trial credit (3 month expiry) |
| **Best models** | `DeepSeek-V3-0324`, `Meta-Llama-3.3-70B-Instruct`, `Qwen2.5-72B-Instruct` |
| **Env var** | `SAMBANOVA_API_KEY=...` |
| **Notes** | Very fast inference. Trial credits, not perpetual free tier. |

### HuggingFace — Open model hub

| | |
|---|---|
| **Signup** | https://huggingface.co/settings/tokens |
| **Free limits** | Rate-limited free inference API |
| **Best models** | `Qwen/Qwen2.5-72B-Instruct`, `meta-llama/Llama-3.3-70B-Instruct` |
| **Env var** | `HF_API_KEY=hf_...` |
| **Notes** | Huge model selection. Some models may have queue times. |

### OpenRouter — Aggregator with free models

| | |
|---|---|
| **Signup** | https://openrouter.ai/keys |
| **Free limits** | 20 RPM, 50 req/day (free models only, `:free` suffix) |
| **Best models** | `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.3-70b-instruct:free` |
| **Env var** | `OPENROUTER_API_KEY=sk-or-...` |
| **Notes** | Aggregates many providers. Free models marked with `:free`. $10 adds 1000 req/day. |

### GitHub Models — Free via GitHub PAT

| | |
|---|---|
| **Signup** | https://github.com/settings/tokens (PAT with no scopes needed) |
| **Free limits** | Rate-limited, generous for personal use |
| **Best models** | `gpt-4o-mini`, `Meta-Llama-3.1-405B-Instruct`, `Mistral-large-2411`, `Phi-4` |
| **Env var** | `GITHUB_MODELS_PAT=ghp_...` |
| **Notes** | Uses your GitHub account. Access via [GitHub Marketplace Models](https://github.com/marketplace?type=models). |

### Alibaba Cloud / Qwen — Free 1M tokens/month

| | |
|---|---|
| **Signup** | https://dashscope.console.aliyun.com/apiKey |
| **Free limits** | 1M free tokens/month, rate-limited |
| **Best models** | `qwen-plus`, `qwen-turbo`, `qwen-max`, `qwen-long` |
| **Env var** | `DASHSCOPE_API_KEY=sk-...` |
| **Notes** | Alibaba's Qwen family. International endpoint. [Landing page](https://www.alibabacloud.com/en/campaign/qwen-ai-landing-page). |

---

## Recommended Combo

For a free multi-model LibreChat setup, use these 3 together:

1. **Groq** — daily driver (fast, high limits)
2. **Gemini** — large context tasks (1M tokens/day)
3. **Mistral** — code tasks (Codestral)

This gives you strong coverage across general chat, long-context analysis,
and code assistance — all completely free.

---

## Example .env

```bash
# Enable custom endpoints
ENDPOINTS=openAI,anthropic,custom

# Free providers (uncomment the ones you signed up for)
GROQ_API_KEY=gsk_abc123...
GEMINI_API_KEY=AIza...
XAI_API_KEY=xai-abc123...
# MISTRAL_API_KEY=...
# CEREBRAS_API_KEY=csk-...
# COHERE_API_KEY=...
# SAMBANOVA_API_KEY=...
# HF_API_KEY=hf_...
# OPENROUTER_API_KEY=sk-or-...
# GITHUB_MODELS_PAT=ghp_...
# DASHSCOPE_API_KEY=sk-...
```

Then uncomment the corresponding endpoint blocks in `librechat.yaml` and restart.

---

## Adding More Providers

Any OpenAI-compatible API can be added as a custom endpoint.
See the [LibreChat docs](https://www.librechat.ai/docs/configuration/librechat_yaml/ai_endpoints/custom)
and these resources for more options:
- [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)
- [leonardomontini.dev/free-llm-api](https://leonardomontini.dev/free-llm-api/)

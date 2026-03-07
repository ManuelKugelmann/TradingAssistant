# LLM Keys & Endpoints

Complete reference for LLM provider credentials used with LibreChat.
All keys go in `~/LibreChat/.env` (or via `ta env`).

At least one LLM provider is required. You can use multiple simultaneously.

---

## Quick Setup

1. Sign up at the provider URL
2. Copy your API key
3. Add it to `~/LibreChat/.env` (or `ta env`)
4. Uncomment the matching endpoint in `librechat.yaml` (`ta yaml`) if needed
5. Restart: `ta restart`

---

## Free Tier Providers

All providers below offer free API tiers (rate-limited, no billing required).
Preconfigured in `librechat.yaml` (commented out) -- uncomment to enable.

Reference: [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)

### Groq -- Fastest free inference

| | |
|---|---|
| **Signup** | https://console.groq.com/keys |
| **Free limits** | 14,400 req/day (varies by model), 6K-30K tokens/min |
| **Best models** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768` |
| **Env var** | `GROQ_API_KEY=gsk_...` |
| **Notes** | Custom LPU hardware, extremely fast. Best free option for daily use. |

### Google Gemini -- Largest free context

| | |
|---|---|
| **Signup** | https://aistudio.google.com/apikey |
| **Free limits** | 15 RPM, 1M tokens/day (Gemini Flash) |
| **Best models** | `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash` |
| **Env var** | `GEMINI_API_KEY=AI...` |
| **Notes** | Very generous token limits. 1M context on paid tier. |

### xAI / Grok -- Free Grok access

| | |
|---|---|
| **Signup** | https://console.x.ai |
| **Free limits** | 30 RPM, free tier with monthly credit |
| **Best models** | `grok-3-mini`, `grok-3-mini-fast` |
| **Env var** | `XAI_API_KEY=xai-...` |
| **Notes** | Strong reasoning model. Free $25/month credit (as of early 2025). |

### Mistral -- Best European provider

| | |
|---|---|
| **Signup** | https://console.mistral.ai/api-keys |
| **Free limits** | 1 req/sec, 500K tokens/min |
| **Best models** | `mistral-small-latest`, `codestral-latest` |
| **Env var** | `MISTRAL_API_KEY=...` |
| **Notes** | Codestral is great for code tasks. Free tier very generous. |

### Cerebras -- Fast open-model inference

| | |
|---|---|
| **Signup** | https://cloud.cerebras.ai |
| **Free limits** | 30 RPM, 14,400 req/day |
| **Best models** | `llama-3.3-70b`, `qwen-3-235b`, `llama-3.1-8b` |
| **Env var** | `CEREBRAS_API_KEY=csk-...` |
| **Notes** | Very fast inference on open models. |

### Cohere -- Command R family

| | |
|---|---|
| **Signup** | https://dashboard.cohere.com/api-keys |
| **Free limits** | 20 RPM, 1,000 req/month |
| **Best models** | `command-a-03-2025`, `command-r-plus-08-2024` |
| **Env var** | `COHERE_API_KEY=...` |
| **Notes** | Good for RAG use cases. Lower monthly limit but capable models. |

### SambaNova -- Trial credits

| | |
|---|---|
| **Signup** | https://cloud.sambanova.ai |
| **Free limits** | $5 trial credit (3 month expiry) |
| **Best models** | `DeepSeek-V3-0324`, `Meta-Llama-3.3-70B-Instruct`, `Qwen2.5-72B-Instruct` |
| **Env var** | `SAMBANOVA_API_KEY=...` |
| **Notes** | Very fast inference. Trial credits, not perpetual free tier. |

### HuggingFace -- Open model hub

| | |
|---|---|
| **Signup** | https://huggingface.co/settings/tokens |
| **Free limits** | Rate-limited free inference API |
| **Best models** | `Qwen/Qwen2.5-72B-Instruct`, `meta-llama/Llama-3.3-70B-Instruct` |
| **Env var** | `HF_API_KEY=hf_...` |
| **Notes** | Huge model selection. Some models may have queue times. |

### GitHub Models -- Free via GitHub PAT

| | |
|---|---|
| **Signup** | https://github.com/settings/tokens (PAT with no scopes needed) |
| **Free limits** | Rate-limited, generous for personal use |
| **Best models** | `gpt-4o-mini`, `Meta-Llama-3.1-405B-Instruct`, `Mistral-large-2411`, `Phi-4` |
| **Env var** | `GITHUB_MODELS_PAT=ghp_...` |
| **Notes** | Uses your GitHub account. Access via [GitHub Marketplace Models](https://github.com/marketplace?type=models). |

### Alibaba Cloud / Qwen -- Free 1M tokens/month

| | |
|---|---|
| **Signup** | https://dashscope.console.aliyun.com/apiKey |
| **Free limits** | 1M free tokens/month, rate-limited |
| **Best models** | `qwen-plus`, `qwen-turbo`, `qwen-max`, `qwen-long` |
| **Env var** | `DASHSCOPE_API_KEY=sk-...` |
| **Notes** | Alibaba's Qwen family. International endpoint. [Landing page](https://www.alibabacloud.com/en/campaign/qwen-ai-landing-page). |

### OpenRouter -- Aggregator with free models

| | |
|---|---|
| **Signup** | https://openrouter.ai/keys |
| **Free limits** | 20 RPM, 50 req/day (free models only, `:free` suffix) |
| **Best models** | `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.3-70b-instruct:free` |
| **Env var** | `OPENROUTER_API_KEY=sk-or-...` |
| **Notes** | Aggregates many providers. Free models marked with `:free`. Also has paid models (see below). |

### Recommended Free Combo

For a free multi-model LibreChat setup, use these 3 together:

1. **Groq** -- daily driver (fast, high limits)
2. **Gemini** -- large context tasks (1M tokens/day)
3. **Mistral** -- code tasks (Codestral)

---

## Paid Providers

### OpenAI -- GPT-4o, o1, o3

| | |
|---|---|
| **Signup** | https://platform.openai.com/api-keys |
| **Pricing** | Pay-per-token, prepaid credits |
| **Best models** | `gpt-4o`, `gpt-4o-mini`, `o3-mini` |
| **Env var** | `OPENAI_API_KEY=sk-...` |
| **Notes** | Native LibreChat endpoint (no custom config needed). Set in `.env` and it works. |

### Anthropic -- Claude Opus, Sonnet, Haiku

| | |
|---|---|
| **Signup** | https://console.anthropic.com/settings/keys |
| **Pricing** | Pay-per-token, prepaid credits |
| **Best models** | `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| **Env var** | `ANTHROPIC_API_KEY=sk-ant-...` |
| **Notes** | Native LibreChat endpoint (no custom config needed). Set in `.env` and it works. |

### OpenRouter -- Multi-provider gateway (paid tier)

| | |
|---|---|
| **Signup** | https://openrouter.ai/keys |
| **Pricing** | Pay-per-token, $10+ credit gives 1000 req/day |
| **Best models** | All OpenAI, Anthropic, Google, Meta models via single key |
| **Env var** | `OPENROUTER_API_KEY=sk-or-...` |
| **Notes** | Recommended if you want access to all major models through one key. Same key works for free `:free` models too. |

### Google Gemini -- Paid tier

| | |
|---|---|
| **Signup** | https://aistudio.google.com/apikey |
| **Pricing** | Pay-per-token (same key as free tier, billing enabled) |
| **Best models** | `gemini-2.0-pro`, `gemini-2.0-flash` (higher limits) |
| **Env var** | `GEMINI_API_KEY=AI...` |
| **Notes** | Same key as free tier. Enable billing for higher rate limits and pro models. |

### Mistral -- Paid tier

| | |
|---|---|
| **Signup** | https://console.mistral.ai/api-keys |
| **Pricing** | Pay-per-token |
| **Best models** | `mistral-large-latest`, `codestral-latest` (higher limits) |
| **Env var** | `MISTRAL_API_KEY=...` |
| **Notes** | Same key as free tier. Enable billing for higher limits and large model access. |

---

## Claude Max Subscription

Use your Claude Pro/Max subscription as a LibreChat endpoint -- no per-token billing.

| | |
|---|---|
| **Requires** | Active Claude Pro or Max subscription |
| **Setup** | `ta proxy setup` (installs CLIProxyAPI, registers service) |
| **How it works** | CLIProxyAPI runs locally on `:8317`, translates OpenAI-compatible requests to Claude CLI |
| **Env var** | `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...` (in `~/.claude-auth.env`) |
| **Full guide** | [docs/claude-token-wrapper.md](claude-token-wrapper.md) |

Already preconfigured in `librechat.yaml` (commented out). Uncomment the "Claude Max" endpoint and restart.

---

## GitHub Secrets

Store LLM keys as GitHub repository secrets to enable CI validation.
Go to: **Settings > Secrets and variables > Actions > New repository secret**

| Secret name | Used by |
|---|---|
| `OPENAI_API_KEY` | LLM key check CI job |
| `ANTHROPIC_API_KEY` | LLM key check CI job |
| `OPENROUTER_API_KEY` | LLM key check CI job |
| `GROQ_API_KEY` | LLM key check CI job |
| `GEMINI_API_KEY` | LLM key check CI job |
| `MISTRAL_API_KEY` | LLM key check CI job |
| `XAI_API_KEY` | LLM key check CI job |

All are optional -- the CI job skips providers whose secrets aren't set.

---

## Example .env

```bash
# ── Paid (pick at least one) ──
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# ── OpenRouter (one key, all models) ──
# OPENROUTER_API_KEY=sk-or-...

# ── Free providers (uncomment the ones you signed up for) ──
GROQ_API_KEY=gsk_abc123...
GEMINI_API_KEY=AIza...
XAI_API_KEY=xai-abc123...
# MISTRAL_API_KEY=...
# CEREBRAS_API_KEY=csk-...
# COHERE_API_KEY=...
# SAMBANOVA_API_KEY=...
# HF_API_KEY=hf_...
# GITHUB_MODELS_PAT=ghp_...
# DASHSCOPE_API_KEY=sk-...

# Enable custom endpoints
ENDPOINTS=openAI,anthropic,custom
```

Then uncomment the corresponding endpoint blocks in `librechat.yaml` and restart.

---

## Adding More Providers

Any OpenAI-compatible API can be added as a custom endpoint.
See the [LibreChat docs](https://www.librechat.ai/docs/configuration/librechat_yaml/ai_endpoints/custom)
and these resources for more options:
- [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)
- [leonardomontini.dev/free-llm-api](https://leonardomontini.dev/free-llm-api/)

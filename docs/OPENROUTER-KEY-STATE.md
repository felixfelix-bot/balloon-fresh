# OpenRouter key state — 2026-10-14 (post key-cap fix)

## The right key this time ✅

| Field | Before | Now |
|---|---|---|
| `limit` | 5 | **15** |
| `limit_remaining` | 0 | **9.995680** |
| `usage` | 8.055288 | 8.055288 |
| `resets_at` | 2026-10-15T00:00Z | 2026-10-15T00:00Z |

Auth **passes** (no 401). The account has credit ($40 total, $18.07 used).
So the key-level cap was raised on the correct key.

## But a NEW blocker replaces it: a workspace guardrail excludes every model

A real completion call returns:

```
HTTP 404  "0 endpoints out of 15 requested are available matching your
           guardrail restrictions and data policy.
           Model blocked by guardrail: 1 endpoint excluded"
reason:   "model-ignored-by-guardrail"
fix URL:  https://openrouter.ai/workspaces/default/guardrails
```

Tested across four unrelated models — **all blocked identically**:

| model | result |
|---|---|
| `deepseek/deepseek-v4-pro` | 404 — 0 of 15 endpoints, guardrail |
| `meta-llama/llama-3.3-70b-instruct` | 404 — 0 of 11 endpoints, guardrail |
| `qwen/qwen-2.5-7b-instruct` | 404 — 0 of 1 endpoint, guardrail |
| `google/gemini-2.0-flash-001` | 404 — no endpoints found |

**This is not a funding or key problem.** The routing funnel reaches
`Filter by Guardrails` and then drops every endpoint: the endpoints *exist*
(15 of them for deepseek-v4-pro), and the workspace guardrail is excluding them.

## The fix is a dashboard setting

`https://openrouter.ai/workspaces/default/guardrails` — the workspace's model
guardrail. Most likely a allow/deny list that does not include these models, or
an "ignore/bypass" rule configured to exclude them all. Nothing on this host
can fix it; it is an account-setting change.

## Router-side note

The router maps to openrouter via `deepseek/deepseek-v4-pro` and
`deepseek/deepseek-flash`. The latter is a **router alias only** —
`deepseek/deepseek-flash is not a valid model ID` upstream — so even with the
guardrail lifted, only the canonical `deepseek-v4-pro` spelling can serve.

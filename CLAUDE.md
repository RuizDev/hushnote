# HushNote — Hermes Integration Fork

This is a fork of HushNote (https://github.com/peteonrails/hushnote) with custom patches for Hermes integration.

**Branch:** `hermes-integration` — all custom changes live here.
**Upstream:** `upstream` remote points to the original repo.

## What's Different

1. **OpenAI-compatible API support** in `summarize.py` — `--provider openai` flag talks to LM Studio / any OpenAI-compatible endpoint
2. **Fixed BUG-1** — bash entry point now forwards `OLLAMA_URL` to Python (was silently ignored)
3. **Fixed BUG-2** — `replace()` instead of `.format()` to avoid crash on curly braces in transcripts
4. **Fixed BUG-3** — using bash arrays instead of `eval` for argument construction
5. **New config vars:** `SUMMARIZE_PROVIDER`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`

## Key Files

| File | Purpose |
|---|---|
| `summarize.py` | Main summarization script — patched for dual-provider support |
| `hushnote` | Bash entry point — patched to forward new config vars |
| `.hushnoterc.example` | Updated with OpenAI config section |

## LM Studio Endpoint

- Base URL: `http://127.0.0.1:1234` (via Cloudflare tunnel)
- API path: `/v1/chat/completions`
- Auth: none (LM Studio default) or `LM_API_KEY` env var

## Project Context

Full integration plan: `~/hermes_workspace/hushnote-hermes-integration/docs/`
Handoff doc: `~/hermes_workspace/hushnote-hermes-integration/CLAUDE.md`

## Testing

```bash
# Quick test that provider flag routing works
./venv/bin/python summarize.py <transcript.txt> --provider openai --base-url http://127.0.0.1:1234

# Full pipeline test
./hushnote record -d 10 -t "Test"
./hushnote process-last
```
#!/usr/bin/env python3

"""
Meeting summarization script — supports Ollama and OpenAI-compatible APIs (LM Studio)
Takes transcription text and generates meeting notes, summaries, and action items.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library not installed", file=sys.stderr)
    print("Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OPENAI_URL = "http://localhost:1234"

SUMMARY_PROMPT = """You are an assistant that writes concise meeting notes from transcripts.

Produce the following sections using markdown headings:

## Summary
2-3 sentences covering what the meeting was about and what was concluded.

## Discussion
Bullet points of the main topics covered. Be specific, not generic.

## Decisions
Key decisions or conclusions reached. Omit this section if none were made.

## Action Items
A markdown checklist of concrete next steps that were explicitly agreed on, with owner and deadline if mentioned. Only include items that were clearly committed to — not vague intentions or possibilities. Omit this section entirely if there are no real action items.

## Participants
Names or roles of identifiable speakers, if mentioned.

Transcription:
{transcription}

Use markdown headings and bullet points. Do not wrap your response in a code block."""


def _build_prompt(transcription: str) -> str:
    """
    Safely substitute transcription into the prompt template.

    Uses simple string replacement instead of str.format() to avoid
    KeyError/IndexError if the transcript contains curly braces
    (e.g. {variable}, {TICKET-123}, ${HOME}).
    """
    return SUMMARY_PROMPT.replace("{transcription}", transcription)


def query_ollama(prompt: str, model: str = "llama3.1:8b", ollama_url: str = DEFAULT_OLLAMA_URL) -> str:
    """
    Query Ollama API for text generation.

    Args:
        prompt: The prompt to send
        model: Model name to use
        ollama_url: Ollama API URL

    Returns:
        Generated text response
    """
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=300  # 5 minute timeout
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        print(f"Error querying Ollama at {ollama_url}: {e}", file=sys.stderr)
        sys.exit(1)


def query_openai(prompt: str, model: str, base_url: str, api_key: str = "") -> str:
    """
    Query OpenAI-compatible API (/v1/chat/completions) — works with LM Studio.

    Args:
        prompt: The prompt to send
        model: Model name to request
        base_url: Base URL of the API (no trailing slash, no /v1)
        api_key: Optional API key (empty for LM Studio default)

    Returns:
        Generated text response
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            print(
                f"Error: API returned empty choices. Response: {response.text[:500]}",
                file=sys.stderr,
            )
            sys.exit(1)
        return choices[0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error querying OpenAI-compatible API at {base_url}: {e}", file=sys.stderr)
        sys.exit(1)


def load_transcription(file_path: str) -> str:
    """Load transcription from file (supports .txt, .json)"""
    path = Path(file_path)

    if not path.exists():
        print(f"Error: Transcription file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if path.suffix == ".json":
        data = json.loads(path.read_text())
        return data.get("text", "")
    else:
        return path.read_text()


def summarize_meeting(
    transcription: str,
    model: str,
    provider: str = "ollama",
    ollama_url: str = DEFAULT_OLLAMA_URL,
    openai_url: str = DEFAULT_OPENAI_URL,
    openai_api_key: str = "",
) -> dict:
    """Generate meeting notes from a transcription using the configured provider."""
    print(f"Generating meeting summary using {provider}/{model}...", file=sys.stderr)

    prompt = _build_prompt(transcription)

    if provider == "openai":
        text = query_openai(prompt, model, openai_url, openai_api_key)
    else:
        text = query_ollama(prompt, model, ollama_url)

    return {"summary": _strip_code_fence(text)}


def _strip_code_fence(text: str) -> str:
    """Strip wrapping code fences that models sometimes add around markdown output."""
    import re
    # Match optional language tag: ```markdown or ```md or just ```
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


def save_summary(result: dict, output_file: str, format: str):
    """Save summary in specified format."""
    output_path = Path(output_file)

    if format in ("txt", "md"):
        output_path.write_text(result["summary"] + "\n")
    elif format == "json":
        output_path.write_text(json.dumps(result, indent=2))

    print(f"Summary saved to: {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Summarize meeting transcription using Ollama or OpenAI-compatible API"
    )
    parser.add_argument("transcription_file", help="Path to transcription file (.txt or .json)")
    parser.add_argument("-m", "--model", default="llama3.1:8b",
                        help="Model name (default: llama3.1:8b)")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "openai"],
                        help="API provider: ollama (default) or openai (LM Studio)")
    parser.add_argument("-u", "--ollama-url", default=DEFAULT_OLLAMA_URL,
                        help=f"Ollama API URL (default: {DEFAULT_OLLAMA_URL})")
    parser.add_argument("--base-url", default=DEFAULT_OPENAI_URL,
                        help=f"OpenAI-compatible base URL (default: {DEFAULT_OPENAI_URL})")
    parser.add_argument("--api-key", default="",
                        help="API key for OpenAI-compatible provider (default: none)")
    parser.add_argument("-f", "--format", default="md",
                        choices=["txt", "md", "json"],
                        help="Output format (default: md)")
    parser.add_argument("-o", "--output",
                        help="Output file (default: transcription_file_summary.md)")

    args = parser.parse_args()

    # Load transcription
    transcription = load_transcription(args.transcription_file)

    if not transcription.strip():
        print("Error: Transcription is empty", file=sys.stderr)
        sys.exit(1)

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        trans_path = Path(args.transcription_file)
        suffix = ".md" if args.format == "md" else f".{args.format}"
        output_file = trans_path.with_name(f"{trans_path.stem}_summary{suffix}")

    # Generate summary
    try:
        result = summarize_meeting(
            transcription,
            model=args.model,
            provider=args.provider,
            ollama_url=args.ollama_url,
            openai_url=args.base_url,
            openai_api_key=args.api_key,
        )

        # Save results
        save_summary(result, output_file, args.format)

        print("\nSummarization complete!", file=sys.stderr)

    except Exception as e:
        print(f"Error during summarization: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
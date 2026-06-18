"""Shared text-LLM helper — one place for `claude -p` (subscription) + API.

Both the knowledge synthesizer and the RAG chat send a text prompt and want a
text answer. Vision has its own image-aware path in extract/vision.py; this is
the text-only twin so we don't duplicate backend logic.
"""

from __future__ import annotations

import os
import shutil
import subprocess

CLI_TIMEOUT = 180


class LLMError(RuntimeError):
    """Raised when the chosen backend cannot produce an answer."""


def claude_text(
    prompt: str,
    backend: str = "claude-cli",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1200,
    timeout: int = CLI_TIMEOUT,
) -> str:
    """Send a text prompt, return the text answer. Raises LLMError on failure."""
    if backend == "claude-cli":
        return _via_cli(prompt, timeout)
    if backend == "api":
        return _via_api(prompt, model, max_tokens)
    raise LLMError(f"unknown backend {backend!r}")


def _via_cli(prompt: str, timeout: int) -> str:
    claude = shutil.which("claude")
    if not claude:
        raise LLMError("claude CLI not found; set backend=api")
    try:
        proc = subprocess.run(
            [claude, "-p", prompt],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"claude CLI timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise LLMError(f"claude CLI failed: {proc.stderr.strip()[:200]}")
    out = proc.stdout.strip()
    if not out:
        raise LLMError("claude CLI returned empty output")
    return out


def _via_api(prompt: str, model: str, max_tokens: int) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY not set; use backend=claude-cli")
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()

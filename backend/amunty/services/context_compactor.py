"""
context_compactor.py

Auto-compacts conversation history when approaching context window limits.
Summarizes older messages via the same LLM, preserving key context.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("amunty.context_compactor")

COMPACT_THRESHOLD = 0.85  # Trigger compaction at 85% of context window
SUMMARY_MAX_TOKENS = 1024

SELF_SUMMARY_SYSTEM_PROMPT = """You are summarizing a conversation to preserve context after compaction. Produce a structured summary that lets the conversation continue seamlessly.

Use this format:

## Conversation Summary
**Turns summarized:** {count}  |  **Compactions so far:** {n}

### User Goal
One sentence describing what the user is trying to accomplish.

### What Was Done
- Bullet points of completed actions, decisions made, and key outputs
- Include specific file paths, function names, variable names, URLs, and config values
- Note any errors encountered and how they were resolved

### Current State
What is the system/code/task state right now? What was the last thing discussed?

### Pending / Next Steps
- What remains to be done
- Any open questions or blockers

### Key Context
- Important constraints, preferences, or decisions that must not be forgotten
- Specific values: model names, ports, paths, credentials references, versions

Keep the summary under 1000 tokens. Be dense — every token should carry information. Do not include pleasantries or meta-commentary."""


def _message_text_token_estimate(text: str) -> int:
    return int(len(text) * 0.3) + 4


def estimate_tokens(messages: List[Dict]) -> int:
    """Estimate token count for a list of OpenAI-formatted messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += _message_text_token_estimate(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total += _message_text_token_estimate(item.get("text", ""))
    return total + 12


def _truncate_text_to_token_budget(text: str, token_budget: int) -> str:
    """Trim a too-large current user message instead of dropping it entirely."""
    if token_budget <= 32:
        return "[Current user message omitted: it exceeded the model context window.]"

    max_chars = max(200, int((token_budget - 16) / 0.3))
    if len(text) <= max_chars:
        return text

    notice = (
        "\n\n[Notice: the pasted message was too large for this model's context "
        "window, so Amunty kept the beginning and end.]"
    )
    keep_chars = max(200, max_chars - len(notice))
    head_len = max(100, int(keep_chars * 0.7))
    tail_len = max(80, keep_chars - head_len)
    return text[:head_len].rstrip() + notice + "\n\n" + text[-tail_len:].lstrip()


def _truncate_message_to_token_budget(msg: Dict[str, Any], token_budget: int) -> Dict[str, Any]:
    """Return a copy of msg whose text content fits inside token_budget."""
    out = dict(msg)
    content = out.get("content", "")
    if isinstance(content, str):
        out["content"] = _truncate_text_to_token_budget(content, token_budget)
        return out

    if isinstance(content, list):
        remaining = token_budget
        new_content = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                new_content.append(item)
                continue
            text = item.get("text", "")
            truncated = _truncate_text_to_token_budget(text, remaining)
            cloned = dict(item)
            cloned["text"] = truncated
            new_content.append(cloned)
            remaining -= _message_text_token_estimate(truncated)
        out["content"] = new_content
    return out


def trim_for_context(messages: List[Dict], context_length: int, reserve_tokens: int = 512) -> List[Dict]:
    """Trim system messages to fit within context_length."""
    budget = context_length - reserve_tokens
    used = estimate_tokens(messages)
    if used <= budget:
        return messages

    logger.info("Trimming messages: %s tokens > %s budget (ctx=%s)", used, budget, context_length)

    system_msgs = []
    protected_msgs = []
    convo_msgs = []
    for msg in messages:
        if msg.get("_protected"):
            protected_msgs.append(msg)
        elif msg.get("role") == "system":
            system_msgs.append(msg)
        else:
            convo_msgs.append(msg)

    protected_tokens = estimate_tokens(protected_msgs)
    budget -= protected_tokens

    essential_system = system_msgs[:1] if system_msgs else []
    extra_system = system_msgs[1:]

    trimmed = essential_system + convo_msgs
    if estimate_tokens(trimmed) <= budget:
        result = list(essential_system)
        for msg in extra_system:
            candidate = result + [msg] + convo_msgs
            if estimate_tokens(candidate) <= budget:
                result.append(msg)
            else:
                break
        return result + protected_msgs + convo_msgs

    if essential_system:
        sys_text = essential_system[0].get("content", "")
        if len(sys_text) > 2000:
            essential_system[0] = {"role": "system", "content": sys_text[:2000] + "\n[System prompt truncated for context limits]"}
            trimmed = essential_system + convo_msgs
            if estimate_tokens(trimmed) <= budget:
                return essential_system + protected_msgs + convo_msgs

    PROTECT_RECENT = 10
    current_msg = convo_msgs[-1:] if convo_msgs else []
    prior_convo = convo_msgs[:-1] if convo_msgs else []
    if len(prior_convo) >= PROTECT_RECENT:
        old_msgs = prior_convo[:-(PROTECT_RECENT - 1)]
        recent_msgs = prior_convo[-(PROTECT_RECENT - 1):] + current_msg
        while old_msgs and estimate_tokens(essential_system + old_msgs + recent_msgs) > budget:
            old_msgs.pop(0)
        convo_msgs = old_msgs + recent_msgs
    else:
        convo_msgs = prior_convo + current_msg
        while prior_convo and estimate_tokens(essential_system + prior_convo + current_msg) > budget:
            prior_convo.pop(0)
        convo_msgs = prior_convo + current_msg

    if current_msg and estimate_tokens(essential_system + protected_msgs + convo_msgs) > budget:
        prefix = essential_system + protected_msgs + convo_msgs[:-1]
        available_for_current = max(64, budget - estimate_tokens(prefix))
        convo_msgs[-1] = _truncate_message_to_token_budget(convo_msgs[-1], available_for_current)

    result = essential_system + protected_msgs + convo_msgs
    logger.info("Trimmed to %s tokens (%s messages)", estimate_tokens(result), len(result))
    return result

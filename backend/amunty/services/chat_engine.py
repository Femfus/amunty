"""Chat engine — orchestrates conversations, streaming, and tool calls."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import AsyncIterator

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from amunty.models.conversation import Conversation
from amunty.models.message import Message
from amunty.services.model_gateway.base import CompletionConfig, StreamChunk
from amunty.services.model_gateway.registry import gateway

logger = logging.getLogger("amunty.chat_engine")

MAX_TOOL_ROUNDS = 10


async def send_message(
    *,
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    content: str,
    model_id: str | None = None,
) -> AsyncIterator[dict]:
    """Process a user message and stream the assistant response."""
    from amunty.services.skills import skills_manager
    from amunty.services.tools.registry import tool_registry

    result = await db.execute(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.unique().scalar_one_or_none()
    if conv is None:
        yield {"type": "error", "content": "Conversation not found."}
        return

    effective_model = model_id or conv.model_id

    # Persist user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=content,
        created_at=datetime.now(UTC),
    )
    db.add(user_msg)
    await db.commit()

    # Add the newly created user message to the conversation's list
    all_messages = sorted(conv.messages, key=lambda m: m.created_at)
    all_messages.append(user_msg)

    messages = _build_message_list(all_messages, conv.system_prompt)

    # Trim for context window limits
    from amunty.services.context_compactor import trim_for_context
    messages = trim_for_context(messages, 8192)

    assistant_msg_id = str(uuid.uuid4())
    final_response = ""

    try:
        # ── Step 1: Check if user is teaching a new skill ──
        teach_result = _detect_teach_intent(content)
        if teach_result:
            skill_name, triggers, tool_name, tool_args = teach_result
            new_skill = skills_manager.add_skill(
                name=skill_name,
                description=f"Custom skill: {skill_name}",
                triggers=triggers,
                tool_name=tool_name,
                tool_args=tool_args,
                emoji="🧠",
                source="learned",
            )
            final_response = (
                f"🧠 **Learned a new skill!**\n\n"
                f"**{new_skill.name}**\n"
                f"Triggers: {', '.join(f'`{t}`' for t in new_skill.triggers)}\n"
                f"Action: `{new_skill.tool_name}`\n\n"
                f"Try saying one of the trigger phrases!"
            )
            yield {"type": "token", "content": final_response}

        # ── Step 2: Check for skill match ──
        elif match := skills_manager.match(content):
            skill, tool_args = match
            logger.info("Skill matched: %s → %s(%s)", skill.name, skill.tool_name, tool_args)

            # Show tool call card
            yield {
                "type": "tool_call",
                "name": skill.tool_name,
                "params": json.dumps(tool_args),
            }

            # Execute tool
            tool_output = await tool_registry.execute(skill.tool_name, json.dumps(tool_args))

            # Show tool result
            yield {
                "type": "tool_result",
                "name": skill.tool_name,
                "output": tool_output[:2000],
            }

            # Persist tool message
            tool_msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role="tool",
                content=tool_output,
                tool_call_id=f"skill_{skill.id[:8]}",
                created_at=datetime.now(UTC),
            )
            db.add(tool_msg)
            await db.commit()

            # Format result and give to model as context by appending to the last user message
            # rather than adding a trailing system message, which breaks LLaMA chat templates.
            try:
                data = json.loads(tool_output)
                formatted = _format_tool_output(skill.tool_name, data)
            except json.JSONDecodeError:
                formatted = tool_output

            if messages and messages[-1]["role"] == "user":
                last_user_msg = messages[-1]
                injection = (
                    f"\n\n[SYSTEM: The background tool automatically ran and returned this data:\n"
                    f"{formatted}\n\n"
                    f"Please respond to my request based on this data. **Crucial: You must include the exact numbers/details from the data in your response!** Be concise and friendly. Don't mention tools or skills.]"
                )
                
                if isinstance(last_user_msg["content"], str):
                    last_user_msg["content"] += injection
                elif isinstance(last_user_msg["content"], list):
                    last_user_msg["content"].append({
                        "type": "text",
                        "text": injection
                    })

            # Let model write natural response
            config = CompletionConfig()
            async for chunk in gateway.complete(effective_model, messages, config):
                if chunk.delta:
                    final_response += chunk.delta
                    yield {"type": "token", "content": chunk.delta}
                if chunk.finish_reason == "error":
                    yield {"type": "error", "content": chunk.delta}
                    return

        else:
            # ── Step 3: Normal chat (with agent loop) ──
            config = CompletionConfig(tools=tool_registry.get_schemas())
            
            for _round in range(MAX_TOOL_ROUNDS):
                round_tool_calls = []
                
                async for chunk in gateway.complete(effective_model, messages, config):
                    if chunk.tool_calls:
                        round_tool_calls.extend(chunk.tool_calls)
                        continue
                        
                    if chunk.delta:
                        final_response += chunk.delta
                        yield {"type": "token", "content": chunk.delta}
                        
                    if chunk.finish_reason == "error":
                        yield {"type": "error", "content": chunk.delta}
                        return
                        
                if not round_tool_calls:
                    break  # Done generating
                    
                # Model requested tool calls
                for tc in round_tool_calls:
                    t_name = tc.get("function", {}).get("name")
                    t_args_str = tc.get("function", {}).get("arguments", "{}")
                    
                    try:
                        t_args = json.loads(t_args_str)
                    except json.JSONDecodeError:
                        t_args = {}
                        
                    logger.info("Agent executing native tool: %s(%s)", t_name, t_args)
                    yield {"type": "tool_call", "name": t_name, "params": t_args_str}
                    
                    try:
                        tool_output = await tool_registry.execute(t_name, t_args_str)
                    except Exception as e:
                        tool_output = json.dumps({"error": str(e)})
                        
                    yield {"type": "tool_result", "name": t_name, "output": tool_output[:2000]}
                    
                    try:
                        data = json.loads(tool_output)
                        formatted = _format_tool_output(t_name, data)
                    except json.JSONDecodeError:
                        formatted = tool_output
                        
                    # Inject pseudo-history to avoid breaking Ollama templates
                    messages.append({
                        "role": "assistant",
                        "content": f"I am running the system tool: {t_name}"
                    })
                    messages.append({
                        "role": "user",
                        "content": f"[SYSTEM: Tool '{t_name}' returned the following data]\n{formatted}\n\nPlease proceed with answering my request using this data. **Crucial: include the exact numbers/details.**"
                    })

    except ValueError as exc:
        yield {"type": "error", "content": str(exc)}
        return
    except Exception as exc:
        logger.error("Chat engine error: %s", exc, exc_info=True)
        yield {"type": "error", "content": f"Internal error: {exc}"}
        return

    # Persist assistant message
    assistant_msg = Message(
        id=assistant_msg_id,
        conversation_id=conversation_id,
        role="assistant",
        content=final_response,
        model_id=effective_model,
        created_at=datetime.now(UTC),
    )
    db.add(assistant_msg)

    if len(all_messages) <= 2:
        conv.title = content[:80].strip() or "New Chat"

    conv.updated_at = datetime.now(UTC)
    await db.commit()

    yield {"type": "done", "message_id": assistant_msg_id}


def _detect_teach_intent(message: str) -> tuple[str, list[str], str, dict] | None:
    """Detect if the user is teaching a new skill.

    Patterns:
    - "learn that when I say 'good morning' you should check the weather"
    - "add a skill: when I say 'work mode', open notepad"
    - "remember when I say 'focus', open terminal"
    """
    msg = message.lower().strip()

    # Known tool mapping for natural descriptions
    action_map = {
        "check the time": ("get_current_time", {}),
        "check time": ("get_current_time", {}),
        "get the time": ("get_current_time", {}),
        "check the weather": ("get_weather", {"location": ""}),
        "get the weather": ("get_weather", {"location": ""}),
        "check weather": ("get_weather", {"location": ""}),
        "check battery": ("get_system_info", {}),
        "check system info": ("get_system_info", {}),
        "check my battery": ("get_system_info", {}),
        "open notepad": ("open_application", {"name": "notepad"}),
        "open calculator": ("open_application", {"name": "calculator"}),
        "open terminal": ("open_application", {"name": "terminal"}),
        "open paint": ("open_application", {"name": "paint"}),
        "open file explorer": ("open_application", {"name": "file explorer"}),
        "open settings": ("open_application", {"name": "settings"}),
        "open youtube": ("open_url", {"url": "youtube.com"}),
        "open google": ("open_url", {"url": "google.com"}),
        "open github": ("open_url", {"url": "github.com"}),
        "send a notification": ("show_notification", {"title": "Amunty", "message": "Hello!"}),
        "show notification": ("show_notification", {"title": "Amunty", "message": "Hello!"}),
        "check clipboard": ("get_clipboard", {}),
        "show processes": ("get_running_processes", {"sort_by": "memory", "limit": 10}),
    }

    patterns = [
        r"(?:learn|remember|add a skill|teach yourself)\s*(?:that\s+)?when\s+i\s+say\s+['\"](.+?)['\"]\s*[,.]?\s*(?:you\s+should\s+|you\s+)?(.+)",
        r"(?:learn|remember|add a skill)\s*:\s*when\s+i\s+say\s+['\"](.+?)['\"]\s*[,.]?\s*(.+)",
        r"when\s+i\s+say\s+['\"](.+?)['\"]\s*[,.]?\s*(?:you\s+should\s+|you\s+|please\s+)?(.+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            trigger = m.group(1).strip()
            action_text = m.group(2).strip().rstrip(".")

            # Try to match action to a known tool
            for desc, (tool_name, tool_args) in action_map.items():
                if desc in action_text:
                    skill_name = trigger.title()
                    return skill_name, [trigger], tool_name, tool_args

    return None


def _build_message_list(
    messages: list[Message], system_prompt: str | None
) -> list[dict]:
    """Convert database messages to OpenAI-format message dicts."""
    result: list[dict] = []

    base_prompt = system_prompt or ""
    system_text = (
        "You are Amunty, a friendly and highly capable PC assistant running natively on the user's Windows computer.\n\n"
        "## Your Capabilities\n"
        "You have FULL, REAL access to the user's computer, including their filesystem, via system tools. "
        "These tools run automatically when the user asks — you don't need to call them yourself. "
        "Just respond naturally based on the results you receive.\n\n"
        "What you can actually do:\n"
        "- Read, search, and edit files anywhere on the computer\n"
        "- Create new files and folders\n"
        "- Run shell commands and interact with the operating system\n"
        "- Check the current time and date\n"
        "- Check battery level, CPU, memory, and disk usage\n"
        "- Send real Windows notifications to the user's desktop\n"
        "- Set reminders that fire as Windows notifications\n"
        "- Open applications (Notepad, Calculator, Terminal, etc.) and close running applications by name\n"
        "- Open websites and search/play music, artists, or playlists on YouTube or Spotify\n"
        "- Inspect what song/video is currently playing on the computer\n"
        "- Control media playback (play, pause, next track, previous track, stop) and adjust system volume or mute status\n"
        "- Check the weather for any city\n"
        "- Read and write the clipboard\n"
        "- List running processes\n"
        "- Learn and automatically add custom skills/shortcuts for the user using the add_custom_skill tool to dynamically tailor the workspace environment to their specific recurring requests and habits.\n\n"
        "## Rules\n"
        "- When you receive tool results, present them naturally and concisely\n"
        "- NEVER pretend to do things — if you receive tool data, it was REAL\n"
        "- NEVER make up system data like battery levels, times, running apps, or temperatures\n"
        "- If the user asks for system data (like what apps are running) but you DO NOT see tool data injected below, you MUST reply: 'I'm sorry, my background tools didn't trigger. Could you rephrase your request?' DO NOT guess or hallucinate lists of apps.\n"
        "- Be warm, concise, and conversational\n"
        "- Use emojis occasionally to be friendly\n\n"
        + base_prompt
    ).strip()
    result.append({"role": "system", "content": system_text})

    for msg in messages:
        if msg.role == "tool":
            continue
        if msg.tool_calls:
            continue
        if msg.tool_call_id:
            continue

        content = msg.content
        pattern = r"!\[.*?\]\((data:image/[^;]+;base64,[^\)]+)\)"
        
        if re.search(pattern, content):
            parts = []
            last_idx = 0
            for m in re.finditer(pattern, content):
                text_part = content[last_idx:m.start()].strip()
                if text_part:
                    parts.append({"type": "text", "text": text_part})
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": m.group(1)}
                })
                last_idx = m.end()
            
            tail = content[last_idx:].strip()
            if tail:
                parts.append({"type": "text", "text": tail})
                
            entry = {"role": msg.role, "content": parts}
        else:
            entry = {"role": msg.role, "content": content}
            
        result.append(entry)

    return result


def _format_tool_output(tool_name: str, data: dict) -> str:
    """Format tool output into human-readable text."""
    if "error" in data:
        return f"Error: {data['error']}"

    try:
        if tool_name == "get_current_time":
            return f"Current time: {data.get('time', '?')}, Date: {data.get('date', '?')}, Timezone: {data.get('timezone', '?')}"

        if tool_name == "get_system_info":
            parts = []
            if "battery" in data:
                b = data["battery"]
                plug = "plugged in" if b.get("plugged_in") else "on battery"
                parts.append(f"Battery: {b.get('percent', '?')}% ({plug})")
            if "memory" in data:
                m = data["memory"]
                parts.append(f"Memory: {m.get('used_gb', '?')} / {m.get('total_gb', '?')} GB ({m.get('percent_used', '?')}% used)")
            if "disk_c" in data:
                d = data["disk_c"]
                parts.append(f"Disk C: {d.get('free_gb', '?')} GB free of {d.get('total_gb', '?')} GB")
            if "cpu_percent" in data:
                parts.append(f"CPU: {data.get('cpu_percent', '?')}% ({data.get('cpu_count', '?')} cores)")
            parts.append(f"OS: {data.get('os', '?')}")
            return "\n".join(parts)

        if tool_name == "get_weather":
            return (
                f"Location: {data.get('location', '?')}, {data.get('country', '')}\n"
                f"Temperature: {data.get('temperature_c', '?')}°C / {data.get('temperature_f', '?')}°F "
                f"(feels like {data.get('feels_like_c', '?')}°C)\n"
                f"Conditions: {data.get('description', '?')}\n"
                f"Wind: {data.get('wind_kmh', '?')} km/h, Humidity: {data.get('humidity', '?')}%"
            )

        if tool_name == "set_reminder":
            return f"Reminder set for {data.get('fire_at', '?')}: \"{data.get('message', '?')}\""

        if tool_name == "show_notification":
            return f"Notification sent: {data.get('title', '')} — {data.get('message', '')}"

        if tool_name == "open_application":
            return f"Opened {data.get('application', 'the app')}"

        if tool_name == "open_url":
            return f"Opened {data.get('url', 'the link')} in browser"

        if tool_name == "list_directory":
            entries = data.get("entries", [])
            lines = [f"Directory: {data.get('path', '?')} ({data.get('count', len(entries))} items)"]
            for e in entries[:20]:
                lines.append(f"  {'DIR' if e.get('type') == 'directory' else 'FILE'} {e.get('name', '?')}")
            return "\n".join(lines)

        if tool_name == "get_clipboard":
            return f"Clipboard ({data.get('length', '?')} chars): {data.get('content', '')[:500]}"

        if tool_name == "run_command":
            parts = [f"Exit code: {data.get('exit_code', '?')}"]
            if data.get("stdout"):
                parts.append(f"Output: {data['stdout'][:1000]}")
            return "\n".join(parts)

        if tool_name == "get_running_processes":
            procs = data.get("top", [])
            lines = [f"Top {len(procs)} processes:"]
            for p in procs:
                lines.append(f"  {p.get('name', '?')} — Mem: {p.get('memory_percent', '?')}%, CPU: {p.get('cpu_percent', '?')}%")
            return "\n".join(lines)

    except Exception:
        pass

    return json.dumps(data, indent=2)

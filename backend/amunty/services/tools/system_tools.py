"""Windows system tools — gives the AI access to the user's PC."""

from __future__ import annotations

import asyncio
import datetime
import glob
import json
import logging
import os
import platform
import subprocess
import webbrowser
from pathlib import Path

from amunty.config import settings

logger = logging.getLogger("amunty.tools.system")

# Store active reminders so we can reference them
_active_reminders: list[dict] = []


# ── Tool implementations ──────────────────────────────────────────────


async def get_current_time(**kwargs) -> str:
    """Get the current date, time, and timezone."""
    now = datetime.datetime.now()
    return json.dumps({
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "timezone": str(datetime.datetime.now().astimezone().tzinfo),
        "iso": now.isoformat(),
        "unix_timestamp": int(now.timestamp()),
    })


async def set_reminder(minutes: int = 1, message: str = "Reminder") -> str:
    """Set a reminder that shows a Windows notification after N minutes."""
    fire_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes)

    async def _fire():
        await asyncio.sleep(minutes * 60)
        await show_notification(title="⏰ Amunty Reminder", message=message)

    asyncio.create_task(_fire())
    _active_reminders.append({
        "message": message,
        "fire_at": fire_at.strftime("%I:%M %p"),
        "minutes": minutes,
    })

    return json.dumps({
        "status": "set",
        "message": message,
        "fire_at": fire_at.strftime("%I:%M %p"),
        "minutes_from_now": minutes,
    })


async def show_notification(title: str = "Amunty", message: str = "") -> str:
    """Show a Windows notification using the notify.ps1 script."""
    script_path = Path(__file__).resolve().parent.parent.parent.parent / "notify.ps1"
    logger.info("Notification script path: %s (exists: %s)", script_path, script_path.exists())

    if not script_path.exists():
        return json.dumps({"status": "error", "error": f"notify.ps1 not found at {script_path}"})

    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script_path),
            "-Title", title,
            "-Message", message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            logger.error("Notification script error (rc=%d): %s", proc.returncode, err)
            return json.dumps({"status": "error", "error": err[:200]})

        logger.info("Notification shown: %s — %s", title, message)
        return json.dumps({"status": "shown", "title": title, "message": message})
    except asyncio.TimeoutError:
        logger.warning("Notification script timed out")
        return json.dumps({"status": "shown", "title": title, "message": message, "note": "script timed out but may still display"})
    except Exception as exc:
        logger.error("Notification failed: %s", exc)
        return json.dumps({"status": "error", "error": str(exc)})


async def open_application(name: str = "") -> str:
    """Open an application by name."""
    app_map = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "files": "explorer.exe",
        "task manager": "taskmgr.exe",
        "settings": "ms-settings:",
        "control panel": "control.exe",
        "snipping tool": "SnippingTool.exe",
        "wordpad": "wordpad.exe",
    }

    key = name.lower().strip()
    exe = app_map.get(key, name)

    try:
        if exe.endswith(":"):
            os.startfile(exe)
        else:
            subprocess.Popen(exe, shell=True)
        return json.dumps({"status": "opened", "application": name})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def open_url(url: str = "") -> str:
    """Open a URL in the default web browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return json.dumps({"status": "opened", "url": url})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def get_system_info(**kwargs) -> str:
    """Get system information: OS, CPU, memory, disk, battery."""
    info: dict = {
        "os": platform.platform(),
        "hostname": platform.node(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }

    try:
        import psutil
        # Memory
        mem = psutil.virtual_memory()
        info["memory"] = {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent_used": mem.percent,
        }
        # Disk
        disk = psutil.disk_usage("C:\\")
        info["disk_c"] = {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "percent_used": round(disk.percent, 1),
        }
        # Battery
        batt = psutil.sensors_battery()
        if batt:
            info["battery"] = {
                "percent": round(batt.percent, 1),
                "plugged_in": batt.power_plugged,
                "time_left_minutes": round(batt.secsleft / 60) if batt.secsleft > 0 else None,
            }
        # CPU
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        info["cpu_count"] = psutil.cpu_count()
    except ImportError:
        info["note"] = "psutil not installed — limited info available"

    return json.dumps(info)


async def list_directory(path: str = ".", show_hidden: bool = False) -> str:
    """List files and directories in a given path."""
    try:
        p = Path(path).expanduser().resolve()
        workspace = settings.workspace_dir.resolve()
        if not p.is_relative_to(workspace):
            return json.dumps({"error": "Permission denied: Path is outside the workspace."})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not p.exists():
        return json.dumps({"error": f"Path does not exist: {p}"})
    if not p.is_dir():
        return json.dumps({"error": f"Not a directory: {p}"})

    entries = []
    try:
        for item in sorted(p.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_file():
                try:
                    entry["size_bytes"] = item.stat().st_size
                except OSError:
                    pass
            entries.append(entry)
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {p}"})

    return json.dumps({
        "path": str(p),
        "count": len(entries),
        "entries": entries[:100],  # cap at 100
    })


async def read_file(path: str = "", max_lines: int = 100) -> str:
    """Read the contents of a text file."""
    try:
        p = Path(path).expanduser().resolve()
        workspace = settings.workspace_dir.resolve()
        if not p.is_relative_to(workspace):
            return json.dumps({"error": "Permission denied: Path is outside the workspace."})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not p.exists():
        return json.dumps({"error": f"File not found: {p}"})
    if not p.is_file():
        return json.dumps({"error": f"Not a file: {p}"})
    if p.stat().st_size > 1_000_000:
        return json.dumps({"error": "File too large (>1MB). Use a more specific tool."})

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        truncated = len(lines) > max_lines
        return json.dumps({
            "path": str(p),
            "lines": len(lines),
            "truncated": truncated,
            "content": "\n".join(lines[:max_lines]),
        })
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def search_files(pattern: str = "*", directory: str = ".", max_results: int = 50) -> str:
    """Search for files matching a glob pattern."""
    try:
        base = Path(directory).expanduser().resolve()
        workspace = settings.workspace_dir.resolve()
        if not base.is_relative_to(workspace):
            return json.dumps({"error": "Permission denied: Path is outside the workspace."})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not base.exists():
        return json.dumps({"error": f"Directory not found: {base}"})

    results = []
    try:
        for match in base.rglob(pattern):
            results.append({
                "path": str(match),
                "type": "directory" if match.is_dir() else "file",
                "size_bytes": match.stat().st_size if match.is_file() else None,
            })
            if len(results) >= max_results:
                break
    except PermissionError:
        pass

    return json.dumps({
        "pattern": pattern,
        "directory": str(base),
        "count": len(results),
        "results": results,
    })


async def get_clipboard(**kwargs) -> str:
    """Read the current clipboard text content."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", "Get-Clipboard",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        text = stdout.decode("utf-8", errors="replace").strip()
        return json.dumps({"content": text, "length": len(text)})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def set_clipboard(text: str = "") -> str:
    """Write text to the clipboard."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "clip",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=text.encode("utf-8", errors="replace")), timeout=5)
        if proc.returncode != 0:
            return json.dumps({"error": stderr.decode("utf-8", errors="replace").strip()})
        return json.dumps({"status": "copied", "length": len(text)})
    except Exception as exc:
        return json.dumps({"error": str(exc)})





async def get_running_processes(sort_by: str = "memory", limit: int = 15) -> str:
    """List top running processes by memory or CPU usage."""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                info = p.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "memory_percent": round(info["memory_percent"] or 0, 1),
                    "cpu_percent": round(info["cpu_percent"] or 0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        key = "memory_percent" if sort_by == "memory" else "cpu_percent"
        procs.sort(key=lambda x: x[key], reverse=True)
        return json.dumps({"count": len(procs), "top": procs[:limit]})
    except ImportError:
        return json.dumps({"error": "psutil not installed"})


async def get_weather(location: str = "") -> str:
    """Get current weather for a location using wttr.in."""
    import urllib.request
    try:
        url = f"https://wttr.in/{location}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Amunty/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        return json.dumps({
            "location": area.get("areaName", [{}])[0].get("value", location),
            "country": area.get("country", [{}])[0].get("value", ""),
            "temperature_c": current.get("temp_C"),
            "temperature_f": current.get("temp_F"),
            "feels_like_c": current.get("FeelsLikeC"),
            "description": current.get("weatherDesc", [{}])[0].get("value", ""),
            "humidity": current.get("humidity"),
            "wind_kmh": current.get("windspeedKmph"),
            "wind_dir": current.get("winddir16Point"),
        })
    except Exception as exc:
        return json.dumps({"error": f"Weather lookup failed: {exc}"})

async def download_model(repo_id: str = "", include: str = "") -> str:
    """Download a HuggingFace model using huggingface-cli."""
    cmd = f"huggingface-cli download {repo_id}"
    if include:
        cmd += f" --include {include}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        return json.dumps({"status": "started background download", "cmd": cmd})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

async def serve_model(repo_id: str = "", cmd: str = "") -> str:
    """Start serving a model in the background."""
    try:
        subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return json.dumps({"status": "started", "model": repo_id, "cmd": cmd})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def search_web(query: str, limit: int = 5) -> str:
    """Search the web for a query."""
    from amunty.services.search.core import _call_provider
    try:
        # Default to duckduckgo for generic searches
        results = await asyncio.to_thread(_call_provider, "duckduckgo", query, limit)
        return json.dumps({"query": query, "results": results})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def read_url_tool(url: str) -> str:
    """Read and extract content from a URL."""
    from amunty.services.search import fetch_webpage_content
    try:
        page = await asyncio.to_thread(fetch_webpage_content, url, 10)
        return json.dumps({"url": url, "content": page.get("content", "")[:10000]})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def do_deep_research(question: str) -> str:
    """Run an automated deep research loop on the web for a complex question."""
    from amunty.services.deep_research import DeepResearcher
    
    # Normally we'd use settings, but hardcoding a standard fallback if gateway is missing
    researcher = DeepResearcher(
        llm_endpoint="http://localhost:11434/v1/chat/completions",
        llm_model="llama3.1:8b",
        max_rounds=3
    )
    try:
        report = await researcher.research(question)
        return json.dumps({"status": "success", "report": report})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def add_custom_skill(
    name: str,
    description: str,
    triggers: list[str],
    tool_name: str,
    tool_args: dict[str, Any] | None = None,
    emoji: str = "⚡",
    **kwargs
) -> str:
    """Add a new custom skill/shortcut triggers for a tool action."""
    from amunty.services.skills import skills_manager
    try:
        skill = skills_manager.add_skill(
            name=name,
            description=description,
            triggers=triggers,
            tool_name=tool_name,
            tool_args=tool_args,
            emoji=emoji,
            source="learned",
        )
        return json.dumps({
            "status": "success",
            "message": f"Successfully registered new skill '{name}'",
            "skill": skill.to_dict()
        })
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def get_current_playing_media(**kwargs) -> str:
    """Check what song is currently playing on the computer."""
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = manager.get_current_session()
        if not session:
            return json.dumps({"status": "no_active_session", "message": "No active media session found."})
        
        info = await session.try_get_media_properties_async()
        playback = session.get_playback_info()
        
        from winsdk.windows.media.control import GlobalSystemMediaPlaybackStatus
        status_map = {
            GlobalSystemMediaPlaybackStatus.CLOSED: "closed",
            GlobalSystemMediaPlaybackStatus.OPENED: "opened",
            GlobalSystemMediaPlaybackStatus.CHANGING: "changing",
            GlobalSystemMediaPlaybackStatus.STOPPED: "stopped",
            GlobalSystemMediaPlaybackStatus.PLAYING: "playing",
            GlobalSystemMediaPlaybackStatus.PAUSED: "paused",
        }
        
        status_str = status_map.get(playback.playback_status, "unknown")
        
        return json.dumps({
            "status": "active",
            "title": info.title,
            "artist": info.artist,
            "album_title": info.album_title,
            "playback_status": status_str,
            "source_app_id": session.source_app_user_model_id,
        })
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def control_media(action: str, **kwargs) -> str:
    """Control system media playback.
    
    Args:
        action: 'play', 'pause', 'toggle', 'next', 'previous', 'stop'
    """
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = manager.get_current_session()
        if not session:
            return json.dumps({"status": "no_active_session", "message": "No active media session to control."})
        
        act = action.lower().strip()
        success = False
        if act == "play":
            success = await session.try_play_async()
        elif act == "pause":
            success = await session.try_pause_async()
        elif act == "toggle":
            success = await session.try_toggle_play_pause_async()
        elif act == "next":
            success = await session.try_skip_next_async()
        elif act == "previous":
            success = await session.try_skip_previous_async()
        elif act == "stop":
            success = await session.try_stop_async()
        else:
            return json.dumps({"status": "error", "error": f"Unknown action '{action}'"})
            
        return json.dumps({"status": "success", "action": action, "result": "sent" if success else "failed"})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def control_volume(action: str, **kwargs) -> str:
    """Adjust system volume controls.
    
    Args:
        action: 'up', 'down', 'mute'
    """
    try:
        import keyboard
        act = action.lower().strip()
        if act == "up":
            keyboard.send("volume up")
        elif act == "down":
            keyboard.send("volume down")
        elif act == "mute":
            keyboard.send("volume mute")
        else:
            return json.dumps({"status": "error", "error": f"Unknown action '{action}'"})
        return json.dumps({"status": "success", "action": action})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def close_application(name: str, **kwargs) -> str:
    """Terminate running application processes by name (e.g. 'notepad', 'calc', 'chrome')."""
    try:
        import psutil
        closed_count = 0
        target = name.lower().strip()
        
        if not target.endswith(".exe") and target not in ["settings", "explorer"]:
            target_exe = target + ".exe"
        else:
            target_exe = target
            
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info["name"].lower()
                if pname == target_exe or target in pname:
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if closed_count > 0:
            return json.dumps({"status": "closed", "application": name, "instances_terminated": closed_count})
        else:
            return json.dumps({"status": "not_found", "message": f"No running instances of '{name}' found."})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


async def play_music(query: str, platform: str = "youtube", **kwargs) -> str:
    """Search and play a song or artist on YouTube or Spotify.
    
    Args:
        query: Song name, artist, or album.
        platform: 'youtube' or 'spotify'
    """
    import urllib.parse
    import webbrowser
    import os
    
    q_encoded = urllib.parse.quote(query)
    try:
        if platform.lower() == "spotify":
            url = f"spotify:search:{q_encoded}"
            os.startfile(url)
            return json.dumps({"status": "playing", "platform": "spotify", "query": query})
        else:
            url = f"https://www.youtube.com/results?search_query={q_encoded}"
            webbrowser.open(url)
            return json.dumps({"status": "playing", "platform": "youtube", "query": query})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})

# ── Tool schema definitions ──────────────────────────────────────────

SYSTEM_TOOLS = [
    {
        "name": "add_custom_skill",
        "description": "Register a new custom skill/shortcut that triggers a system tool action when specific phrases are matched.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the new skill (e.g. 'Work Mode')"},
                "description": {"type": "string", "description": "Description of what this skill does"},
                "triggers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Trigger phrases or shortcut keywords that will execute this skill (e.g. ['work mode', 'time to work'])"
                },
                "tool_name": {
                    "type": "string",
                    "description": "The name of the target tool to run (e.g. 'open_application', 'open_url', 'show_notification')"
                },
                "tool_args": {
                    "type": "object",
                    "description": "Optional fixed argument dictionary to pass to the tool (e.g. {'name': 'notepad'}, {'url': 'github.com'})"
                },
                "emoji": {"type": "string", "description": "An emoji representing the skill (e.g. '💻', '🎵')"}
            },
            "required": ["name", "description", "triggers", "tool_name"]
        },
        "execute": add_custom_skill,
    },
    {
        "name": "get_current_playing_media",
        "description": "Inspect and retrieve details about what music/video is currently playing on the user's computer.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execute": get_current_playing_media,
    },
    {
        "name": "control_media",
        "description": "Control playback of active media players (e.g. play, pause, toggle play/pause, next track, previous track, stop).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "toggle", "next", "previous", "stop"],
                    "description": "Playback control action to send"
                }
            },
            "required": ["action"]
        },
        "execute": control_media,
    },
    {
        "name": "control_volume",
        "description": "Adjust system volume (increase, decrease, or toggle mute status).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "mute"],
                    "description": "Volume action to perform: up, down, or toggle mute"
                }
            },
            "required": ["action"]
        },
        "execute": control_volume,
    },
    {
        "name": "close_application",
        "description": "Close and terminate a running application process by name (e.g. 'notepad', 'chrome', 'calc').",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the application process to terminate"}
            },
            "required": ["name"]
        },
        "execute": close_application,
    },
    {
        "name": "play_music",
        "description": "Search and play a song, artist, album, or playlist on YouTube or Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Song name, artist, or playlist to search for"},
                "platform": {
                    "type": "string",
                    "enum": ["youtube", "spotify"],
                    "description": "Platform to play music on (youtube searches web browser, spotify opens local app if available)"
                }
            },
            "required": ["query"]
        },
        "execute": play_music,
    },
    {
        "name": "get_current_time",
        "description": "Get the current date, time, day of the week, and timezone on the user's computer.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execute": get_current_time,
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder that will show a Windows notification after the specified number of minutes.",
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "Minutes from now to fire the reminder"},
                "message": {"type": "string", "description": "The reminder message to display"},
            },
            "required": ["minutes", "message"],
        },
        "execute": set_reminder,
    },
    {
        "name": "show_notification",
        "description": "Show a Windows toast notification immediately.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification message body"},
            },
            "required": ["title", "message"],
        },
        "execute": show_notification,
    },
    {
        "name": "open_application",
        "description": "Open a Windows application by name (e.g. 'notepad', 'calculator', 'terminal', 'file explorer', 'settings', 'paint').",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Application name to open"},
            },
            "required": ["name"],
        },
        "execute": open_application,
    },
    {
        "name": "open_url",
        "description": "Open a URL in the user's default web browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open"},
            },
            "required": ["url"],
        },
        "execute": open_url,
    },
    {
        "name": "get_system_info",
        "description": "Get system information including OS, CPU, memory usage, disk space, and battery level.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execute": get_system_info,
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory on the user's computer.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list (e.g. 'C:\\Users\\User\\Desktop')"},
                "show_hidden": {"type": "boolean", "description": "Whether to show hidden files"},
            },
            "required": ["path"],
        },
        "execute": list_directory,
    },
    {
        "name": "read_file",
        "description": "Read the text contents of a file on the user's computer. Max 1MB, 100 lines by default.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "max_lines": {"type": "integer", "description": "Maximum number of lines to return"},
            },
            "required": ["path"],
        },
        "execute": read_file,
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern recursively (e.g. '*.py', '*.txt').",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', 'report*.pdf')"},
                "directory": {"type": "string", "description": "Directory to search in"},
                "max_results": {"type": "integer", "description": "Maximum results to return"},
            },
            "required": ["pattern", "directory"],
        },
        "execute": search_files,
    },
    {
        "name": "get_clipboard",
        "description": "Read the current text content from the user's clipboard.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execute": get_clipboard,
    },
    {
        "name": "set_clipboard",
        "description": "Copy text to the user's clipboard.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to copy to clipboard"},
            },
            "required": ["text"],
        },
        "execute": set_clipboard,
    },

    {
        "name": "get_running_processes",
        "description": "List the top running processes on the user's computer, sorted by memory or CPU usage.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["memory", "cpu"], "description": "Sort by 'memory' or 'cpu'"},
                "limit": {"type": "integer", "description": "Number of processes to return"},
            },
            "required": [],
        },
        "execute": get_running_processes,
    },
    {
        "name": "get_weather",
        "description": "Get the current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or location (e.g. 'London', 'New York')"},
            },
            "required": ["location"],
        },
        "execute": get_weather,
    },
    {
        "name": "download_model",
        "description": "Download a HuggingFace model locally using huggingface-cli.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_id": {"type": "string", "description": "HuggingFace repo (e.g. 'Qwen/Qwen3-8B')"},
                "include": {"type": "string", "description": "Optional glob filter (e.g. '*Q4_K_M*')"},
            },
            "required": ["repo_id"],
        },
        "execute": download_model,
    },
    {
        "name": "serve_model",
        "description": "Start serving a model locally in a new console window (vLLM, llama.cpp, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_id": {"type": "string", "description": "Model repo (e.g. 'Qwen/Qwen3-8B')"},
                "cmd": {"type": "string", "description": "Full serve command to run"},
            },
            "required": ["repo_id", "cmd"],
        },
        "execute": serve_model,
    },
    {
        "name": "search_web",
        "description": "Search the web for information using DuckDuckGo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results to return"},
            },
            "required": ["query"],
        },
        "execute": search_web,
    },
    {
        "name": "read_url",
        "description": "Read the text content of a web page.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to read"},
            },
            "required": ["url"],
        },
        "execute": read_url_tool,
    },
    {
        "name": "deep_research",
        "description": "Run an automated, multi-step deep research loop to answer a complex question comprehensively.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The complex question to research"},
            },
            "required": ["question"],
        },
        "execute": do_deep_research,
    },
]


def register_system_tools(registry) -> None:
    """Register all system tools with the given registry."""
    for tool in SYSTEM_TOOLS:
        registry.register(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            execute=tool["execute"],
        )

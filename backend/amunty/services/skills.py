"""Skills system — persistent intent-action mappings for the AI."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("amunty.skills")

SKILLS_FILE = Path(__file__).resolve().parent.parent.parent / "skills.json"


@dataclass
class Skill:
    """A single skill — maps trigger phrases to a tool action."""

    id: str
    name: str
    description: str
    emoji: str
    triggers: list[str]  # keyword phrases to match
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    source: str = "built-in"  # "built-in", "user", "learned"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def matches(self, message: str) -> bool:
        """Check if the user message matches any trigger."""
        if not self.enabled:
            return False
        msg = message.lower().strip()
        return any(trigger.lower() in msg for trigger in self.triggers)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Skill:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SkillsManager:
    """Manages skills — loading, saving, matching, CRUD."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def load(self) -> None:
        """Load skills from file, then ensure built-ins exist."""
        if SKILLS_FILE.exists():
            try:
                data = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
                for item in data:
                    skill = Skill.from_dict(item)
                    self._skills[skill.id] = skill
                logger.info("Loaded %d skills from %s", len(self._skills), SKILLS_FILE)
            except Exception as exc:
                logger.warning("Failed to load skills: %s", exc)

        # Ensure all built-in skills exist
        self._ensure_builtins()
        self._loaded = True
        self.save()

    def save(self) -> None:
        """Persist skills to JSON file."""
        data = [s.to_dict() for s in self._skills.values()]
        SKILLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_builtins(self) -> None:
        """Add any missing built-in skills."""
        existing_names = {s.name for s in self._skills.values()}
        for skill in BUILTIN_SKILLS:
            if skill.name not in existing_names:
                self._skills[skill.id] = skill

    def list_skills(self) -> list[dict]:
        """Return all skills as dicts."""
        return [s.to_dict() for s in sorted(self._skills.values(), key=lambda s: (s.source != "built-in", s.name))]

    def get_skill(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def match(self, message: str) -> tuple[Skill, dict[str, Any]] | None:
        """Find the first matching skill for a message. Returns (skill, args) or None.

        Some skills need dynamic argument extraction (e.g. weather location,
        reminder time). This is handled here.
        """
        msg = message.lower().strip()

        # Dynamic patterns that need argument extraction (check these first)
        extracted = self._extract_dynamic(msg)
        if extracted:
            return extracted

        # Static skills — simple keyword matching
        for skill in self._skills.values():
            if skill.matches(message):
                return skill, dict(skill.tool_args)

        return None

    def _extract_dynamic(self, msg: str) -> tuple[Skill, dict[str, Any]] | None:
        """Handle skills that need dynamic argument extraction from the message."""
        import os

        # Reminder: "remind me in X min/sec/hours to ..."
        reminder_match = re.search(
            r'remind\s+me\s+in\s+(\d+)\s*(\w+)\s+(?:to\s+)?(.+)',
            msg, re.IGNORECASE
        )
        if reminder_match:
            amount = int(reminder_match.group(1))
            unit = reminder_match.group(2).lower()
            message = reminder_match.group(3).strip()
            if any(u in unit for u in ["sec", "s"]):
                minutes = max(1, amount // 60) if amount >= 60 else 1
            elif any(u in unit for u in ["hour", "hr", "h"]):
                minutes = amount * 60
            else:
                minutes = amount
            skill = self._find_by_tool("set_reminder")
            if skill:
                return skill, {"minutes": minutes, "message": message}

        # Notification with message: "notification saying X"
        if "notification" in msg or "toast" in msg or "notify me" in msg:
            notif_msg = None
            for pattern in [
                r'notification\s+(?:saying|with|that says)\s+(?:something\s+like\s+)?["\']?(.+?)["\']?\s*$',
                r'notification\s*[:\-]\s*["\']?(.+?)["\']?\s*$',
            ]:
                m = re.search(pattern, msg, re.IGNORECASE)
                if m:
                    notif_msg = m.group(1).strip().strip('"\'')
                    break
            skill = self._find_by_tool("show_notification")
            if skill:
                return skill, {"title": "Amunty", "message": notif_msg or "Hello from Amunty! 👋"}

        # Weather with location: "weather in London"
        weather_loc_match = re.search(r'weather\s+(?:in|for|at)\s+(.+?)[\?\.\!]?\s*$', msg)
        if weather_loc_match:
            skill = self._find_by_tool("get_weather")
            if skill:
                return skill, {"location": weather_loc_match.group(1).strip()}

        # Open URL: "open google.com"
        url_match = re.search(r'open\s+((?:https?://)?(?:www\.)?[\w.-]+\.\w{2,})', msg)
        if url_match:
            skill = self._find_by_tool("open_url")
            if skill:
                return skill, {"url": url_match.group(1)}

        # List directory: "what's on my desktop"
        dir_match = re.search(
            r"(?:list|show|what'?s?\s+(?:on|in))\s+(?:my\s+)?(?:files?\s+(?:on|in)\s+)?(.+?)[\?\.\!]?\s*$",
            msg, re.IGNORECASE
        )
        if dir_match:
            path = dir_match.group(1).strip()
            username = os.environ.get("USERNAME", os.environ.get("USER", "User"))
            path_map = {
                "desktop": f"C:\\Users\\{username}\\Desktop",
                "documents": f"C:\\Users\\{username}\\Documents",
                "downloads": f"C:\\Users\\{username}\\Downloads",
            }
            resolved = path_map.get(path.lower(), path)
            skill = self._find_by_tool("list_directory")
            if skill:
                return skill, {"path": resolved}

        # Media Control: play/pause/next/skip
        if any(w in msg for w in ["skip song", "next song", "next track", "skip track"]):
            skill = self._find_by_tool("control_media")
            if skill:
                return skill, {"action": "next"}
        if any(w in msg for w in ["previous song", "prev song", "previous track", "prev track", "go back a song"]):
            skill = self._find_by_tool("control_media")
            if skill:
                return skill, {"action": "previous"}
        if any(w in msg for w in ["pause music", "pause song", "pause playback"]):
            skill = self._find_by_tool("control_media")
            if skill:
                return skill, {"action": "pause"}
        if any(w in msg for w in ["resume music", "play music", "resume song", "resume playback"]):
            # Avoid matching play specific song here
            if not re.search(r'play\s+(?!music|song|playback|track\s*$)(.+)', msg, re.IGNORECASE):
                skill = self._find_by_tool("control_media")
                if skill:
                    return skill, {"action": "play"}

        # Volume Control
        if any(w in msg for w in ["volume up", "increase volume", "louder", "turn up", "raise volume", "higher volume"]):
            skill = self._find_by_tool("control_volume")
            if skill:
                return skill, {"action": "up"}
        if any(w in msg for w in ["volume down", "decrease volume", "quieter", "softer", "turn down", "lower volume"]):
            skill = self._find_by_tool("control_volume")
            if skill:
                return skill, {"action": "down"}
        if "mute" in msg or "unmute" in msg:
            skill = self._find_by_tool("control_volume")
            if skill:
                return skill, {"action": "mute"}

        # Close Application: "close notepad"
        close_match = re.search(r'(?:close|exit|terminate|kill)\s+(notepad|calculator|terminal|explorer|paint|chrome|settings)', msg, re.IGNORECASE)
        if close_match:
            skill = self._find_by_tool("close_application")
            if skill:
                return skill, {"name": close_match.group(1).strip()}

        # Play specific song: "play bohemian rhapsody on spotify", "play chill music on youtube"
        play_match = re.search(r'play\s+(.+?)(?:\s+on\s+(spotify|youtube))?[\?\.\!]?\s*$', msg, re.IGNORECASE)
        if play_match and not any(w in msg for w in ["remind", "reminder", "timer", "alarm"]):
            song_query = play_match.group(1).strip()
            if song_query not in ["music", "song", "playback", "track"]:
                platform = play_match.group(2) or "youtube"
                skill = self._find_by_tool("play_music")
                if skill:
                    return skill, {"query": song_query, "platform": platform}

        return None

    def _find_by_tool(self, tool_name: str) -> Skill | None:
        """Find the first enabled skill for a given tool."""
        for s in self._skills.values():
            if s.tool_name == tool_name and s.enabled:
                return s
        return None

    def add_skill(
        self,
        name: str,
        description: str,
        triggers: list[str],
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
        emoji: str = "⚡",
        source: str = "user",
    ) -> Skill:
        """Add a new skill."""
        skill = Skill(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            emoji=emoji,
            triggers=triggers,
            tool_name=tool_name,
            tool_args=tool_args or {},
            source=source,
        )
        self._skills[skill.id] = skill
        self.save()
        logger.info("Added skill: %s (%s)", name, tool_name)
        return skill

    def update_skill(self, skill_id: str, updates: dict) -> Skill | None:
        """Update a skill's properties."""
        skill = self._skills.get(skill_id)
        if not skill:
            return None
        for key, value in updates.items():
            if hasattr(skill, key) and key not in ("id", "source"):
                setattr(skill, key, value)
        self.save()
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill (only non-built-in)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return False
        if skill.source == "built-in":
            return False
        del self._skills[skill_id]
        self.save()
        return True

    def __len__(self) -> int:
        return len(self._skills)


# ── Built-in skills ──────────────────────────────────────────────────

BUILTIN_SKILLS = [
    # Time
    Skill(
        id="builtin-time", name="Check Time", emoji="🕐",
        description="Get the current date, time, and timezone",
        triggers=["what time", "current time", "time is it", "what's the time", "whats the time", "tell me the time"],
        tool_name="get_current_time", source="built-in",
    ),
    Skill(
        id="builtin-date", name="Check Date", emoji="📅",
        description="Get today's date and day of the week",
        triggers=["what day", "what date", "today's date", "what is today", "whats today"],
        tool_name="get_current_time", source="built-in",
    ),

    # System
    Skill(
        id="builtin-battery", name="Check Battery", emoji="🔋",
        description="Check laptop battery level and charging status",
        triggers=["battery", "charge level", "power level", "how much charge"],
        tool_name="get_system_info", source="built-in",
    ),
    Skill(
        id="builtin-sysinfo", name="System Info", emoji="💻",
        description="Get CPU, memory, disk usage, and system specs",
        triggers=["system info", "cpu usage", "ram usage", "memory usage", "disk space",
                   "how much storage", "how much memory", "how much ram", "free space",
                   "system status", "computer specs", "my specs"],
        tool_name="get_system_info", source="built-in",
    ),
    Skill(
        id="builtin-processes", name="Running Processes", emoji="📊",
        description="List top processes by memory or CPU usage",
        triggers=["running processes", "top processes", "what processes", "task manager",
                   "what's running", "whats running", "using the most memory", "using the most cpu"],
        tool_name="get_running_processes", tool_args={"sort_by": "memory", "limit": 10},
        source="built-in",
    ),

    # Notifications & Reminders
    Skill(
        id="builtin-notification", name="Send Notification", emoji="🔔",
        description="Send a Windows desktop notification",
        triggers=["notification", "toast", "notify me", "alert me", "send alert"],
        tool_name="show_notification", tool_args={"title": "Amunty", "message": "Hello from Amunty! 👋"},
        source="built-in",
    ),
    Skill(
        id="builtin-reminder", name="Set Reminder", emoji="⏰",
        description="Set a timed reminder with a Windows notification",
        triggers=["remind me", "set reminder", "set alarm", "reminder in"],
        tool_name="set_reminder", source="built-in",
    ),

    # Weather
    Skill(
        id="builtin-weather", name="Check Weather", emoji="🌤️",
        description="Get current weather for any city",
        triggers=["weather", "temperature outside", "is it going to rain", "how hot", "how cold"],
        tool_name="get_weather", tool_args={"location": ""},
        source="built-in",
    ),

    # Apps
    Skill(
        id="builtin-open-notepad", name="Open Notepad", emoji="📝",
        description="Launch Notepad text editor",
        triggers=["open notepad", "launch notepad", "start notepad"],
        tool_name="open_application", tool_args={"name": "notepad"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-calc", name="Open Calculator", emoji="🧮",
        description="Launch the Calculator app",
        triggers=["open calculator", "launch calculator", "open calc"],
        tool_name="open_application", tool_args={"name": "calculator"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-terminal", name="Open Terminal", emoji="⬛",
        description="Launch Windows Terminal or Command Prompt",
        triggers=["open terminal", "open cmd", "open command prompt", "launch terminal"],
        tool_name="open_application", tool_args={"name": "terminal"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-explorer", name="Open File Explorer", emoji="📁",
        description="Launch File Explorer",
        triggers=["open file explorer", "open explorer", "open files", "open my files"],
        tool_name="open_application", tool_args={"name": "file explorer"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-settings", name="Open Settings", emoji="⚙️",
        description="Open Windows Settings",
        triggers=["open settings", "open windows settings", "system settings"],
        tool_name="open_application", tool_args={"name": "settings"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-paint", name="Open Paint", emoji="🎨",
        description="Launch Paint",
        triggers=["open paint", "launch paint"],
        tool_name="open_application", tool_args={"name": "paint"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-taskmgr", name="Open Task Manager", emoji="📋",
        description="Launch Task Manager",
        triggers=["open task manager"],
        tool_name="open_application", tool_args={"name": "task manager"},
        source="built-in",
    ),

    # URLs
    Skill(
        id="builtin-open-youtube", name="Open YouTube", emoji="▶️",
        description="Open YouTube in the browser",
        triggers=["open youtube", "go to youtube"],
        tool_name="open_url", tool_args={"url": "youtube.com"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-google", name="Open Google", emoji="🔍",
        description="Open Google in the browser",
        triggers=["open google", "go to google"],
        tool_name="open_url", tool_args={"url": "google.com"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-github", name="Open GitHub", emoji="🐙",
        description="Open GitHub in the browser",
        triggers=["open github", "go to github"],
        tool_name="open_url", tool_args={"url": "github.com"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-gmail", name="Open Gmail", emoji="📧",
        description="Open Gmail in the browser",
        triggers=["open gmail", "check email", "check my email"],
        tool_name="open_url", tool_args={"url": "gmail.com"},
        source="built-in",
    ),
    Skill(
        id="builtin-open-reddit", name="Open Reddit", emoji="🤖",
        description="Open Reddit in the browser",
        triggers=["open reddit", "go to reddit"],
        tool_name="open_url", tool_args={"url": "reddit.com"},
        source="built-in",
    ),

    # Clipboard
    Skill(
        id="builtin-clipboard-read", name="Read Clipboard", emoji="📋",
        description="Read the current clipboard text content",
        triggers=["what's in my clipboard", "whats in my clipboard", "clipboard content",
                   "read clipboard", "show clipboard", "paste"],
        tool_name="get_clipboard", source="built-in",
    ),

    # Directory listing
    Skill(
        id="builtin-listdir", name="List Files", emoji="📂",
        description="List files and folders in a directory",
        triggers=["list files", "show files", "what's on my desktop"],
        tool_name="list_directory", tool_args={"path": "."},
        source="built-in",
    ),
    # Current Media Playing
    Skill(
        id="builtin-media-current", name="Check Playing Song", emoji="🎵",
        description="Get details about the song or media currently playing on the computer",
        triggers=["what song", "what's playing", "whats playing", "current song", "song is playing", "music is playing", "currently playing"],
        tool_name="get_current_playing_media", source="built-in",
    ),
    # Control Media
    Skill(
        id="builtin-media-control", name="Control Playback", emoji="⏯️",
        description="Play, pause, next, or skip system media tracks",
        triggers=["skip song", "next song", "next track", "skip track", "previous song", "prev song", "previous track", "pause music", "play music", "resume music"],
        tool_name="control_media", source="built-in",
    ),
    # Control Volume
    Skill(
        id="builtin-volume-control", name="Control Volume", emoji="🔊",
        description="Increase system volume, decrease it, or toggle mute",
        triggers=["volume up", "increase volume", "louder", "volume down", "decrease volume", "quieter", "softer", "mute", "unmute"],
        tool_name="control_volume", source="built-in",
    ),
    # Close App
    Skill(
        id="builtin-app-close", name="Close App", emoji="❌",
        description="Close and terminate a running application process by name",
        triggers=["close notepad", "exit calculator", "close chrome", "close settings"],
        tool_name="close_application", source="built-in",
    ),
    # Play Music
    Skill(
        id="builtin-music-play", name="Play Music", emoji="🎶",
        description="Search and play a song or artist on YouTube or Spotify",
        triggers=["play song", "play spotify", "play youtube"],
        tool_name="play_music", source="built-in",
    ),
]


# Singleton
skills_manager = SkillsManager()

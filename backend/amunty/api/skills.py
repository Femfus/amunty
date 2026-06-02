"""Skills API — CRUD endpoints for managing AI skills."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from amunty.deps import CurrentUser
from amunty.services.skills import skills_manager

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    emoji: str = "⚡"
    triggers: list[str]
    tool_name: str
    tool_args: dict = {}


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    emoji: str | None = None
    triggers: list[str] | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    enabled: bool | None = None


@router.get("")
async def list_skills(user: CurrentUser):
    """List all skills."""
    return skills_manager.list_skills()


@router.get("/{skill_id}")
async def get_skill(skill_id: str, user: CurrentUser):
    """Get a single skill by ID."""
    skill = skills_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.to_dict()


@router.post("", status_code=201)
async def create_skill(body: SkillCreate, user: CurrentUser):
    """Create a new user skill."""
    skill = skills_manager.add_skill(
        name=body.name,
        description=body.description,
        emoji=body.emoji,
        triggers=body.triggers,
        tool_name=body.tool_name,
        tool_args=body.tool_args,
        source="user",
    )
    return skill.to_dict()


@router.put("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpdate, user: CurrentUser):
    """Update a skill."""
    updates = body.model_dump(exclude_none=True)
    skill = skills_manager.update_skill(skill_id, updates)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.to_dict()


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user: CurrentUser):
    """Delete a user-created skill."""
    skill = skills_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.source == "built-in":
        raise HTTPException(status_code=403, detail="Cannot delete built-in skills")
    skills_manager.delete_skill(skill_id)
    return {"status": "deleted", "id": skill_id}

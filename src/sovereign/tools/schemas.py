"""
src/sovereign/tools/schemas.py
Pydantic schemas and RBAC models for Tool Registry per TOOL-01 and D-32.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """Hierarchical user access roles for tool execution authorization."""
    ADMIN = "admin"
    ENGINEER = "engineer"
    AUDITOR = "auditor"


ROLE_HIERARCHY: Dict[UserRole, int] = {
    UserRole.ADMIN: 3,
    UserRole.ENGINEER: 2,
    UserRole.AUDITOR: 1,
}


def has_clearance(user_role: UserRole, required_role: UserRole) -> bool:
    """
    Check whether a user's role satisfies or exceeds the required clearance level.
    Admin (3) >= Engineer (2) >= Auditor (1).
    """
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= required_level


class ToolParameter(BaseModel):
    """Specification for a single tool argument."""
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str  # "string", "number", "integer", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """
    Structured tool definition with JSON Schema parameters, RBAC requirements,
    and output schema.
    """
    model_config = ConfigDict(extra="allow")

    name: str
    description: str
    parameters_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []}
    )
    return_schema: Optional[Dict[str, Any]] = None
    required_role: UserRole = UserRole.ENGINEER

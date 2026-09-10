"""
src/sovereign/tools/__init__.py
Tool registry and structured execution package exports.
"""
from sovereign.tools.schemas import (
    UserRole,
    ROLE_HIERARCHY,
    has_clearance,
    ToolParameter,
    ToolDefinition,
)
from sovereign.tools.registry import ToolRegistry, ToolExecutionError
from sovereign.tools.builtin import (
    register_builtin_tools,
    PathSecurityViolation,
    CalculationSecurityError,
)

__all__ = [
    "UserRole",
    "ROLE_HIERARCHY",
    "has_clearance",
    "ToolParameter",
    "ToolDefinition",
    "ToolRegistry",
    "ToolExecutionError",
    "register_builtin_tools",
    "PathSecurityViolation",
    "CalculationSecurityError",
]

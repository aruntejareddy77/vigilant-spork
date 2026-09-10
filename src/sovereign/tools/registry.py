"""
src/sovereign/tools/registry.py
Rigid JSON Schema Tool Registry with RBAC authorization and execution dispatching.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
import jsonschema
from sovereign.tools.schemas import ToolDefinition, UserRole, has_clearance


class ToolExecutionError(Exception):
    """Raised when tool execution fails during runtime."""
    pass


class ToolRegistry:
    """
    Central registry for sovereign agent tools.
    Enforces JSON Schema input validation and role-based clearance before dispatch.
    """

    def __init__(self):
        self._tools: Dict[str, Tuple[ToolDefinition, Callable]] = {}

    def register_tool(self, definition: ToolDefinition, handler: Callable) -> None:
        """
        Register a tool definition and its execution handler.
        """
        if not definition.name or not definition.name.strip():
            raise ValueError("Tool name must be non-empty")
        
        name = definition.name.strip()
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        self._tools[name] = (definition, handler)

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Look up a tool definition by name."""
        entry = self._tools.get(name)
        if not entry:
            return None
        return entry[0]

    def list_tools(self, user_role: Optional[UserRole] = None) -> List[ToolDefinition]:
        """
        List all registered tool definitions, optionally filtering by caller's clearance.
        """
        tools = [defn for defn, _ in self._tools.values()]
        if user_role is not None:
            tools = [t for t in tools if has_clearance(user_role, t.required_role)]
        return sorted(tools, key=lambda t: t.name)

    def get_tool_schemas_for_model(self, user_role: Optional[UserRole] = None) -> List[Dict[str, Any]]:
        """
        Export tool schemas in OpenAI / SGLang standard function-calling structure.
        """
        tools = self.list_tools(user_role=user_role)
        schemas = []
        for t in tools:
            schemas.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                },
            })
        return schemas

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        user_role: UserRole = UserRole.ENGINEER,
    ) -> Any:
        """
        Execute a registered tool after verifying RBAC clearance and argument schema validity.
        """
        entry = self._tools.get(name)
        if not entry:
            raise KeyError(f"Tool '{name}' is not registered in ToolRegistry")

        definition, handler = entry

        # 1. RBAC Clearance Check
        if not has_clearance(user_role, definition.required_role):
            raise PermissionError(
                f"User role '{user_role.value}' does not have sufficient clearance to execute tool '{name}'. "
                f"Requires '{definition.required_role.value}' role."
            )

        # 2. JSON Schema Argument Validation
        if definition.parameters_schema:
            try:
                jsonschema.validate(instance=arguments, schema=definition.parameters_schema)
            except jsonschema.ValidationError as val_err:
                raise ValueError(
                    f"Argument validation failed for tool '{name}': {val_err.message}"
                ) from val_err

        # 3. Execution Dispatch
        try:
            return handler(**arguments)
        except Exception as exc:
            raise ToolExecutionError(
                f"Error executing tool '{name}': {str(exc)}"
            ) from exc

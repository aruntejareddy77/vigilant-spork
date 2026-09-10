"""
tests/test_tools/test_tool_registry.py
Unit tests for ToolRegistry, JSON Schema validation, and RBAC authorization.
"""
import pytest
from sovereign.tools.schemas import ToolDefinition, UserRole, has_clearance
from sovereign.tools.registry import ToolRegistry, ToolExecutionError


def test_rbac_clearance_hierarchy():
    """Verify role clearance hierarchy (Admin >= Engineer >= Auditor)."""
    assert has_clearance(UserRole.ADMIN, UserRole.ADMIN) is True
    assert has_clearance(UserRole.ADMIN, UserRole.ENGINEER) is True
    assert has_clearance(UserRole.ADMIN, UserRole.AUDITOR) is True

    assert has_clearance(UserRole.ENGINEER, UserRole.ADMIN) is False
    assert has_clearance(UserRole.ENGINEER, UserRole.ENGINEER) is True
    assert has_clearance(UserRole.ENGINEER, UserRole.AUDITOR) is True

    assert has_clearance(UserRole.AUDITOR, UserRole.ADMIN) is False
    assert has_clearance(UserRole.AUDITOR, UserRole.ENGINEER) is False
    assert has_clearance(UserRole.AUDITOR, UserRole.AUDITOR) is True


def test_tool_registration_and_retrieval():
    """Test registering tools and inspecting metadata."""
    registry = ToolRegistry()

    calc_def = ToolDefinition(
        name="add_numbers",
        description="Add two numbers together",
        parameters_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
        required_role=UserRole.AUDITOR,
    )

    registry.register_tool(calc_def, lambda a, b: a + b)

    tool = registry.get_tool("add_numbers")
    assert tool is not None
    assert tool.name == "add_numbers"
    assert tool.required_role == UserRole.AUDITOR

    # Duplicate registration should raise
    with pytest.raises(ValueError, match="already registered"):
        registry.register_tool(calc_def, lambda a, b: a + b)

    # Empty name should raise
    with pytest.raises(ValueError, match="Tool name must be non-empty"):
        registry.register_tool(ToolDefinition(name="", description=""), lambda: None)


def test_tool_listing_by_role():
    """Test filtering tools based on user clearance level."""
    registry = ToolRegistry()

    registry.register_tool(
        ToolDefinition(name="audit_logs", description="view logs", required_role=UserRole.AUDITOR),
        lambda: "logs",
    )
    registry.register_tool(
        ToolDefinition(name="run_sim", description="run physics sim", required_role=UserRole.ENGINEER),
        lambda: "sim",
    )
    registry.register_tool(
        ToolDefinition(name="wipe_db", description="admin cleanup", required_role=UserRole.ADMIN),
        lambda: "wiped",
    )

    # Auditor sees only auditor tools
    auditor_tools = [t.name for t in registry.list_tools(user_role=UserRole.AUDITOR)]
    assert auditor_tools == ["audit_logs"]

    # Engineer sees auditor + engineer tools
    engineer_tools = [t.name for t in registry.list_tools(user_role=UserRole.ENGINEER)]
    assert engineer_tools == ["audit_logs", "run_sim"]

    # Admin sees all tools
    admin_tools = [t.name for t in registry.list_tools(user_role=UserRole.ADMIN)]
    assert admin_tools == ["audit_logs", "run_sim", "wipe_db"]


def test_model_tool_schema_export():
    """Test OpenAI / SGLang compatible function-calling export."""
    registry = ToolRegistry()
    registry.register_tool(
        ToolDefinition(
            name="get_weather",
            description="Get current temperature",
            parameters_schema={
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda location: f"Sunny in {location}",
    )

    schemas = registry.get_tool_schemas_for_model(user_role=UserRole.ENGINEER)
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "get_weather"
    assert schemas[0]["function"]["parameters"]["properties"]["location"]["type"] == "string"


def test_tool_execution_success_and_validation():
    """Test tool execution validation guards and handler dispatch."""
    registry = ToolRegistry()

    def divide(numerator: float, denominator: float) -> float:
        if denominator == 0:
            raise ZeroDivisionError("Division by zero")
        return numerator / denominator

    div_def = ToolDefinition(
        name="divide",
        description="Divide two numbers",
        parameters_schema={
            "type": "object",
            "properties": {
                "numerator": {"type": "number"},
                "denominator": {"type": "number"},
            },
            "required": ["numerator", "denominator"],
        },
        required_role=UserRole.ENGINEER,
    )
    registry.register_tool(div_def, divide)

    # 1. Valid execution by engineer
    result = registry.execute_tool(
        "divide",
        {"numerator": 10.0, "denominator": 2.0},
        user_role=UserRole.ENGINEER,
    )
    assert result == 5.0

    # 2. RBAC check: auditor is denied
    with pytest.raises(PermissionError, match="does not have sufficient clearance"):
        registry.execute_tool(
            "divide",
            {"numerator": 10.0, "denominator": 2.0},
            user_role=UserRole.AUDITOR,
        )

    # 3. Schema validation: missing required field
    with pytest.raises(ValueError, match="Argument validation failed"):
        registry.execute_tool(
            "divide",
            {"numerator": 10.0},
            user_role=UserRole.ENGINEER,
        )

    # 4. Schema validation: wrong data type
    with pytest.raises(ValueError, match="Argument validation failed"):
        registry.execute_tool(
            "divide",
            {"numerator": "ten", "denominator": 2.0},
            user_role=UserRole.ENGINEER,
        )

    # 5. Handler exception wrapped in ToolExecutionError
    with pytest.raises(ToolExecutionError, match="Division by zero"):
        registry.execute_tool(
            "divide",
            {"numerator": 10.0, "denominator": 0.0},
            user_role=UserRole.ENGINEER,
        )

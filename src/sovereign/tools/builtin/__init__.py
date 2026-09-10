"""
src/sovereign/tools/builtin/__init__.py
Registration factory for built-in industrial tools.
"""
from pathlib import Path
from typing import Union
from sovereign.tools.schemas import ToolDefinition, UserRole
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.builtin.files import read_file, write_file, list_directory, PathSecurityViolation
from sovereign.tools.builtin.parsing import parse_table, extract_text
from sovereign.tools.builtin.calculator import execute_calculation, CalculationSecurityError


def register_builtin_tools(registry: ToolRegistry, workspace_root: Union[str, Path]) -> ToolRegistry:
    """
    Register all built-in industrial tools into the given ToolRegistry bound to workspace_root.
    """
    ws_root = Path(workspace_root).resolve()

    # 1. read_file (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="read_file",
            description="Read content of a file located within the workspace boundary.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to file inside workspace",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum number of bytes to read",
                        "default": 65536,
                    },
                },
                "required": ["path"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda path, max_bytes=65536: read_file(path, ws_root, max_bytes=max_bytes),
    )

    # 2. write_file (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="write_file",
            description="Write text content to a file within the workspace boundary.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to file inside workspace",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Whether to overwrite existing file",
                        "default": True,
                    },
                },
                "required": ["path", "content"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda path, content, overwrite=True: write_file(path, content, ws_root, overwrite=overwrite),
    )

    # 3. list_directory (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="list_directory",
            description="List files and directories inside a workspace folder.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path (defaults to workspace root)",
                        "default": ".",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to recursively list all nested files",
                        "default": False,
                    },
                },
                "required": [],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda path=".", recursive=False: list_directory(path, ws_root, recursive=recursive),
    )

    # 4. parse_table (Auditor)
    registry.register_tool(
        ToolDefinition(
            name="parse_table",
            description="Parse CSV or TSV tabular data into structured columns and rows.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Raw tabular string content",
                    },
                    "delimiter": {
                        "type": "string",
                        "description": "Column delimiter character (default ',')",
                        "default": ",",
                    },
                },
                "required": ["content"],
            },
            required_role=UserRole.AUDITOR,
        ),
        lambda content, delimiter=",": parse_table(content, delimiter=delimiter),
    )

    # 5. extract_text (Auditor)
    registry.register_tool(
        ToolDefinition(
            name="extract_text",
            description="Extract and normalize plain text from raw unstructured or HTML document string.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Raw document content to clean and normalize",
                    },
                },
                "required": ["content"],
            },
            required_role=UserRole.AUDITOR,
        ),
        lambda content: extract_text(content),
    )

    # 6. execute_calculation (Auditor)
    registry.register_tool(
        ToolDefinition(
            name="execute_calculation",
            description="Safely evaluate a mathematical formula using AST parsing with trace history.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression (e.g. 'sqrt(a**2 + b**2)')",
                    },
                    "variables": {
                        "type": "object",
                        "description": "Key-value dictionary of numeric variables",
                        "default": {},
                    },
                },
                "required": ["expression"],
            },
            required_role=UserRole.AUDITOR,
        ),
        lambda expression, variables=None: execute_calculation(expression, variables=variables),
    )

    return registry


__all__ = [
    "read_file",
    "write_file",
    "list_directory",
    "PathSecurityViolation",
    "parse_table",
    "extract_text",
    "execute_calculation",
    "CalculationSecurityError",
    "register_builtin_tools",
]

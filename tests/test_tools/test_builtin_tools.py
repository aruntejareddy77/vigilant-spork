"""
tests/test_tools/test_builtin_tools.py
Comprehensive unit tests for built-in industrial tools: fenced file I/O, parsing, and AST calculation.
"""
from pathlib import Path
import pytest
from sovereign.tools.schemas import UserRole
from sovereign.tools.registry import ToolRegistry, ToolExecutionError
from sovereign.tools.builtin.files import (
    read_file,
    write_file,
    list_directory,
    _resolve_fenced_path,
    PathSecurityViolation,
)
from sovereign.tools.builtin.parsing import parse_table, extract_text
from sovereign.tools.builtin.calculator import (
    execute_calculation,
    CalculationSecurityError,
)
from sovereign.tools.builtin import register_builtin_tools


def test_fenced_filesystem_operations(tmp_path: Path):
    """Test safe file operations within workspace boundary."""
    workspace = tmp_path / "sandbox_workspace"
    workspace.mkdir()

    # 1. Write file
    res = write_file("reports/test.txt", "Hello Sovereign World", workspace)
    assert res["path"] == "reports/test.txt"
    assert res["bytes_written"] == 21
    assert len(res["sha256"]) == 64

    # 2. Read file
    content = read_file("reports/test.txt", workspace)
    assert content == "Hello Sovereign World"

    # 3. List directory
    items = list_directory(".", workspace, recursive=True)
    paths = [item["path"] for item in items]
    assert "reports" in paths or "reports/test.txt" in paths

    # 4. Read non-existent
    with pytest.raises(FileNotFoundError):
        read_file("nonexistent.txt", workspace)


def test_path_traversal_attacks_blocked(tmp_path: Path):
    """Verify that any path traversal escaping workspace is immediately blocked."""
    workspace = tmp_path / "safe_zone"
    workspace.mkdir()

    # Attempt ../ escape
    with pytest.raises(PathSecurityViolation, match="Access denied"):
        _resolve_fenced_path(workspace, "../outside.txt")

    with pytest.raises(PathSecurityViolation, match="Access denied"):
        read_file("../../secret.key", workspace)

    with pytest.raises(PathSecurityViolation, match="Access denied"):
        write_file("../../../root.txt", "attack", workspace)

    # Attempt absolute path escape
    outside_abs = (tmp_path / "outside_dir").resolve()
    with pytest.raises(PathSecurityViolation, match="Access denied"):
        _resolve_fenced_path(workspace, outside_abs)

    # Attempt null byte injection
    with pytest.raises(PathSecurityViolation, match="Null byte"):
        _resolve_fenced_path(workspace, "file.txt\x00.png")


def test_parse_table_csv_and_tsv():
    """Test structured parsing of CSV and TSV strings with numeric typing."""
    csv_data = """id,pressure_psi,temperature_c,status
101,145.5,350,NORMAL
102,152.0,362,WARNING
"""
    result = parse_table(csv_data)
    assert result["columns"] == ["id", "pressure_psi", "temperature_c", "status"]
    assert result["row_count"] == 2
    assert result["rows"][0]["id"] == 101
    assert result["rows"][0]["pressure_psi"] == 145.5
    assert result["rows"][1]["status"] == "WARNING"

    # TSV parsing
    tsv_data = "colA\tcolB\n1\t2"
    tsv_res = parse_table(tsv_data, delimiter="\t")
    assert tsv_res["columns"] == ["colA", "colB"]
    assert tsv_res["rows"][0]["colA"] == 1

    # Empty data
    empty_res = parse_table("")
    assert empty_res["row_count"] == 0


def test_extract_text_cleaning():
    """Test text cleaning, tag stripping, and whitespace normalization."""
    html_input = """
    <html>
        <body>
            <h1>Refinery Yield Report</h1>
            <p>Unit 4   operating at  98% capacity.</p>
        </body>
    </html>
    """
    cleaned = extract_text(html_input)
    assert "Refinery Yield Report" in cleaned
    assert "Unit 4 operating at 98% capacity." in cleaned
    assert "<html>" not in cleaned
    assert "<h1>" not in cleaned


def test_safe_ast_calculation_success():
    """Test legitimate mathematical formulas with variables and functions."""
    # 1. Standard arithmetic
    res1 = execute_calculation("2 + 3 * 4 - (10 / 2)")
    assert res1["result"] == 9.0

    # 2. Variables and power
    res2 = execute_calculation(
        "sqrt(a**2 + b**2)",
        variables={"a": 3.0, "b": 4.0},
    )
    assert res2["result"] == 5.0
    assert "Substituted variable a" in res2["trace"]

    # 3. Trigonometry and constants
    res3 = execute_calculation("sin(pi / 2)")
    assert pytest.approx(res3["result"]) == 1.0


def test_calculation_security_rejections():
    """Test that arbitrary code execution, imports, and system calls are strictly blocked."""
    # OS import injection
    with pytest.raises(CalculationSecurityError):
        execute_calculation("__import__('os').system('calc')")

    # Eval injection
    with pytest.raises(CalculationSecurityError):
        execute_calculation("eval('1 + 1')")

    # Open file injection
    with pytest.raises(CalculationSecurityError):
        execute_calculation("open('passwords.txt').read()")

    # Lambda expression
    with pytest.raises(CalculationSecurityError):
        execute_calculation("(lambda x: x + 1)(5)")

    # Exponent DoS attack
    with pytest.raises(CalculationSecurityError, match="exceeds safe computational limit"):
        execute_calculation("9999 ** 9999")


def test_register_builtin_tools_integration(tmp_path: Path):
    """Test end-to-end registration and execution of built-in tools in ToolRegistry."""
    registry = ToolRegistry()
    register_builtin_tools(registry, tmp_path)

    tools = registry.list_tools()
    tool_names = [t.name for t in tools]
    expected_tools = [
        "execute_calculation",
        "extract_text",
        "list_directory",
        "parse_table",
        "read_file",
        "write_file",
    ]
    assert sorted(tool_names) == sorted(expected_tools)

    # Execute write_file via registry (Engineer clearance)
    write_res = registry.execute_tool(
        "write_file",
        {"path": "data.csv", "content": "col1,col2\nval1,val2"},
        user_role=UserRole.ENGINEER,
    )
    assert write_res["path"] == "data.csv"

    # Execute read_file via registry
    read_res = registry.execute_tool(
        "read_file",
        {"path": "data.csv"},
        user_role=UserRole.ENGINEER,
    )
    assert "val1,val2" in read_res

    # Execute parse_table via registry (Auditor clearance)
    parse_res = registry.execute_tool(
        "parse_table",
        {"content": read_res},
        user_role=UserRole.AUDITOR,
    )
    assert parse_res["columns"] == ["col1", "col2"]

    # Execute calculate via registry (Auditor clearance)
    calc_res = registry.execute_tool(
        "execute_calculation",
        {"expression": "100 * 1.05"},
        user_role=UserRole.AUDITOR,
    )
    assert calc_res["result"] == 105.0

"""
src/sovereign/tools/builtin/calculator.py
Safe mathematical calculation engine using AST traversal per TOOL-03 and D-33.
Strictly disallows eval(), exec(), imports, and arbitrary statement execution.
"""
import ast
import math
import operator
from typing import Any, Callable, Dict, Optional, Union


ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

ALLOWED_MATH_FUNCS: Dict[str, Callable[..., Any]] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "floor": math.floor,
    "ceil": math.ceil,
    "abs": abs,
    "round": round,
    "pow": pow,
    "min": min,
    "max": max,
}

ALLOWED_CONSTANTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


class CalculationSecurityError(Exception):
    """Raised when an expression contains forbidden AST syntax or malicious calls."""
    pass


class SafeMathEvaluator:
    """
    Evaluates mathematical expressions by traversing the Python AST.
    Guarantees hermetic execution with zero exposure to arbitrary code execution.
    """

    def __init__(self, variables: Optional[Dict[str, Union[int, float]]] = None):
        self.variables = dict(variables or {})
        self.trace_steps = []

    def evaluate(self, node: ast.AST) -> Union[int, float]:
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)

        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise CalculationSecurityError(
                    f"Forbidden constant type: {type(node.value).__name__}. Only numbers are allowed."
                )
            return node.value

        elif isinstance(node, ast.Name):
            name = node.id
            if name in self.variables:
                val = self.variables[name]
                self.trace_steps.append(f"Substituted variable {name} = {val}")
                return val
            elif name in ALLOWED_CONSTANTS:
                val = ALLOWED_CONSTANTS[name]
                self.trace_steps.append(f"Substituted constant {name} = {val}")
                return val
            else:
                raise CalculationSecurityError(f"Undefined variable or constant: '{name}'")

        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPERATORS:
                raise CalculationSecurityError(f"Forbidden binary operator: {op_type.__name__}")
            left_val = self.evaluate(node.left)
            right_val = self.evaluate(node.right)

            # Prevent exponential Denial of Service attacks (e.g. 9999 ** 9999)
            if op_type is ast.Pow and (abs(right_val) > 1000 or (abs(left_val) > 1000 and right_val > 100)):
                raise CalculationSecurityError("Exponent or base exceeds safe computational limit")

            op_fn = ALLOWED_OPERATORS[op_type]
            result = op_fn(left_val, right_val)
            self.trace_steps.append(f"Evaluated {left_val} {op_type.__name__} {right_val} -> {result}")
            return result

        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPERATORS:
                raise CalculationSecurityError(f"Forbidden unary operator: {op_type.__name__}")
            val = self.evaluate(node.operand)
            op_fn = ALLOWED_OPERATORS[op_type]
            return op_fn(val)

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise CalculationSecurityError("Only direct function calls by name are permitted")
            func_name = node.func.id
            if func_name not in ALLOWED_MATH_FUNCS:
                raise CalculationSecurityError(
                    f"Forbidden or unrecognized function call: '{func_name}'. "
                    f"Allowed functions: {list(ALLOWED_MATH_FUNCS.keys())}"
                )
            arg_vals = [self.evaluate(arg) for arg in node.args]
            func_fn = ALLOWED_MATH_FUNCS[func_name]
            result = func_fn(*arg_vals)
            self.trace_steps.append(f"Called {func_name}({', '.join(map(str, arg_vals))}) -> {result}")
            return result

        else:
            raise CalculationSecurityError(
                f"Forbidden AST node type: {type(node).__name__}. Expression must be purely mathematical."
            )


def execute_calculation(
    expression: str,
    variables: Optional[Dict[str, Union[int, float]]] = None,
) -> Dict[str, Any]:
    """
    Safely evaluate a mathematical expression using AST parsing with formula trace logs.
    """
    if not expression or not expression.strip():
        raise ValueError("Expression must be a non-empty string")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as syn_err:
        raise ValueError(f"Invalid mathematical syntax: {syn_err.msg}") from syn_err

    evaluator = SafeMathEvaluator(variables=variables)
    result = evaluator.evaluate(tree)

    return {
        "result": result,
        "expression": expression.strip(),
        "variables": variables or {},
        "trace": "\n".join(evaluator.trace_steps),
    }

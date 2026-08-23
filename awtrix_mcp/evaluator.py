"""Restricted expression evaluator and sandboxed template renderer for manifest
`transform`/`condition`/`show_if` fields and Jinja2 text segments."""

import ast
import operator
from typing import Any

from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

_ENV = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)

_ALLOWED_CALLABLES: dict[str, Any] = {
    "len": len,
    "sum": sum,
    "any": any,
    "all": all,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}

# Attribute-bound methods that expose reflective mini-languages (e.g. str.format's
# {0.__class__} field-access syntax) reaching outside the ast.Attribute nodes
# _eval_Attribute inspects. Must stay blocked even though the attribute name
# itself doesn't start with "_".
_BLOCKED_ATTR_METHODS = {"format", "format_map"}

_BIN_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_CMP_OPS: dict[type, Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}


class ExpressionError(Exception):
    """Raised for parse failures, disallowed syntax, or evaluation errors."""


class AttrDict(dict):
    """dict subclass allowing `d.foo` as an alias for `d["foo"]`. Nested dict/list
    values are recursively wrapped. Not a security boundary itself — see evaluator's
    dunder-attribute-name filter for the actual sandbox boundary."""

    def __init__(self, data: dict) -> None:
        super().__init__({key: _wrap(value) for key, value in data.items()})

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _wrap(value: Any) -> Any:
    if isinstance(value, AttrDict):
        return value
    if isinstance(value, dict):
        return AttrDict(value)
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value


class _Evaluator:
    def __init__(self, context: dict) -> None:
        self._context = context

    def evaluate(self, node: ast.AST, scope: dict) -> Any:
        method = getattr(self, f"_eval_{type(node).__name__}", None)
        if method is None:
            raise ExpressionError(f"disallowed syntax: {type(node).__name__}")
        return method(node, scope)  # pylint: disable=not-callable

    def _eval_Expression(self, node: ast.Expression, scope: dict) -> Any:  # pylint: disable=invalid-name
        return self.evaluate(node.body, scope)

    def _eval_Constant(self, node: ast.Constant, _scope: dict) -> Any:  # pylint: disable=invalid-name
        return node.value

    def _eval_Name(self, node: ast.Name, scope: dict) -> Any:  # pylint: disable=invalid-name
        if node.id in scope:
            return scope[node.id]
        raise ExpressionError(f"undefined name '{node.id}'")

    def _eval_Attribute(self, node: ast.Attribute, scope: dict) -> Any:  # pylint: disable=invalid-name
        if node.attr.startswith("_"):
            raise ExpressionError("attribute access to private/dunder names is not allowed")
        value = self.evaluate(node.value, scope)
        return getattr(value, node.attr)

    def _eval_Call(self, node: ast.Call, scope: dict) -> Any:  # pylint: disable=invalid-name
        args = [self.evaluate(arg, scope) for arg in node.args]
        kwargs = {kw.arg: self.evaluate(kw.value, scope) for kw in node.keywords if kw.arg}
        if isinstance(node.func, ast.Name):
            if node.func.id not in _ALLOWED_CALLABLES:
                raise ExpressionError(f"call to disallowed function '{node.func.id}'")
            return _ALLOWED_CALLABLES[node.func.id](*args, **kwargs)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in _BLOCKED_ATTR_METHODS:
                raise ExpressionError(f"call to disallowed method '{node.func.attr}'")
            bound = self._eval_Attribute(node.func, scope)
            return bound(*args, **kwargs)
        raise ExpressionError("disallowed call target")

    def _eval_BoolOp(self, node: ast.BoolOp, scope: dict) -> Any:  # pylint: disable=invalid-name
        values = [self.evaluate(value, scope) for value in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for value in values:
                result = value
                if not value:
                    break
            return result
        result = False
        for value in values:
            result = value
            if value:
                break
        return result

    def _eval_BinOp(self, node: ast.BinOp, scope: dict) -> Any:  # pylint: disable=invalid-name
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ExpressionError(f"disallowed operator: {type(node.op).__name__}")
        return op(self.evaluate(node.left, scope), self.evaluate(node.right, scope))

    def _eval_UnaryOp(self, node: ast.UnaryOp, scope: dict) -> Any:  # pylint: disable=invalid-name
        operand = self.evaluate(node.operand, scope)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise ExpressionError(f"disallowed operator: {type(node.op).__name__}")

    def _eval_Compare(self, node: ast.Compare, scope: dict) -> Any:  # pylint: disable=invalid-name
        left = self.evaluate(node.left, scope)
        result = True
        for op, comparator_node in zip(node.ops, node.comparators):
            comparator = self.evaluate(comparator_node, scope)
            cmp_fn = _CMP_OPS.get(type(op))
            if cmp_fn is None:
                raise ExpressionError(f"disallowed comparison: {type(op).__name__}")
            if not cmp_fn(left, comparator):
                result = False
                break
            left = comparator
        return result

    def _eval_IfExp(self, node: ast.IfExp, scope: dict) -> Any:  # pylint: disable=invalid-name
        if self.evaluate(node.test, scope):
            return self.evaluate(node.body, scope)
        return self.evaluate(node.orelse, scope)

    def _eval_List(self, node: ast.List, scope: dict) -> Any:  # pylint: disable=invalid-name
        return [self.evaluate(elt, scope) for elt in node.elts]

    def _eval_Tuple(self, node: ast.Tuple, scope: dict) -> Any:  # pylint: disable=invalid-name
        return tuple(self.evaluate(elt, scope) for elt in node.elts)

    def _eval_Dict(self, node: ast.Dict, scope: dict) -> Any:  # pylint: disable=invalid-name
        result = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                raise ExpressionError("disallowed syntax: dict unpacking")
            result[self.evaluate(key_node, scope)] = self.evaluate(value_node, scope)
        return result

    def _eval_GeneratorExp(self, node: ast.GeneratorExp, scope: dict) -> Any:  # pylint: disable=invalid-name
        # Validate eagerly: _run_comprehension is a generator function (it
        # yields), so its body — including these checks — would otherwise not
        # run until the returned generator is iterated, letting an unconsumed
        # bare genexpr bypass validation entirely.
        generator = node.generators[0] if len(node.generators) == 1 else None
        if generator is None:
            raise ExpressionError("disallowed syntax: multiple 'for' clauses in comprehension")
        if not isinstance(generator.target, ast.Name):
            raise ExpressionError("disallowed syntax: unpacking loop target in comprehension")
        if generator.is_async:
            raise ExpressionError("disallowed syntax: async comprehension")
        return self._run_comprehension(node, scope)

    def _run_comprehension(self, node: ast.GeneratorExp, scope: dict) -> Any:
        generator = node.generators[0]
        iterable = self.evaluate(generator.iter, scope)
        for item in iterable:
            child_scope = dict(scope)
            child_scope[generator.target.id] = item
            if all(self.evaluate(if_node, child_scope) for if_node in generator.ifs):
                yield self.evaluate(node.elt, child_scope)


def evaluate_expression(expr: str, context: dict) -> object:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"syntax error: {exc}") from exc
    evaluator = _Evaluator(context)
    try:
        return evaluator.evaluate(tree, context)
    except ExpressionError:
        raise
    except Exception as exc:
        raise ExpressionError(str(exc)) from exc


def render_template(template: str, context: dict) -> str:
    try:
        return _ENV.from_string(template).render(**context)
    except TemplateError as exc:
        raise ExpressionError(str(exc)) from exc


def evaluate_condition(condition: str, context: dict) -> bool:
    if condition == "default":
        return True
    return bool(evaluate_expression(condition, context))

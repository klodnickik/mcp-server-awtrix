import pytest

from awtrix_mcp.evaluator import (
    AttrDict,
    ExpressionError,
    evaluate_condition,
    evaluate_expression,
    render_template,
)


def test_len_builtin():
    assert evaluate_expression("len(data)", {"data": [1, 2, 3]}) == 3


def test_checkly_failures_transform():
    data = [
        AttrDict({"hasFailures": True}),
        AttrDict({"hasFailures": False}),
        AttrDict({"hasFailures": True}),
    ]
    expr = "sum(1 for c in data if c.get('hasFailures'))"
    assert evaluate_expression(expr, {"data": data}) == 2


def test_checkly_degraded_transform():
    data = [
        AttrDict({"hasFailures": True, "isDegraded": True}),
        AttrDict({"hasFailures": False, "isDegraded": True}),
        AttrDict({"hasFailures": False, "isDegraded": False}),
    ]
    expr = "sum(1 for c in data if c.get('isDegraded') and not c.get('hasFailures'))"
    assert evaluate_expression(expr, {"data": data}) == 1


def test_evaluate_condition_default_is_always_true():
    assert evaluate_condition("default", {}) is True


@pytest.mark.parametrize(
    "failures,expected",
    [(1, True), (0, False)],
)
def test_evaluate_condition_comparison(failures, expected):
    assert evaluate_condition("failures > 0", {"failures": failures}) is expected


def test_evaluate_condition_saas_metrics_show_if():
    context = {"data": AttrDict({"tickets_open": 3})}
    assert evaluate_condition("data.tickets_open > 0", context) is True
    context = {"data": AttrDict({"tickets_open": 0})}
    assert evaluate_condition("data.tickets_open > 0", context) is False


def test_render_template_dot_access():
    context = {"data": AttrDict({"users_total": 5})}
    assert render_template("{{data.users_total}}", context) == "5"


def test_attrdict_nested_dict_and_list_wrapping():
    wrapped = AttrDict({"a": [{"b": 1}]})
    assert wrapped.a[0].b == 1


def test_attrdict_missing_attribute_raises_attribute_error():
    wrapped = AttrDict({"a": 1})
    with pytest.raises(AttributeError):
        _ = wrapped.missing


def test_undefined_name_raises_expression_error():
    with pytest.raises(ExpressionError):
        evaluate_expression("faliures > 0", {})


# --- Security boundary tests -----------------------------------------------


def test_dunder_attribute_access_is_blocked():
    with pytest.raises(ExpressionError):
        evaluate_expression("().__class__", {})


def test_import_builtin_is_blocked():
    with pytest.raises(ExpressionError):
        evaluate_expression("__import__('os').system('id')", {})


def test_open_builtin_is_blocked():
    with pytest.raises(ExpressionError):
        evaluate_expression("open('/etc/passwd').read()", {})


def test_multiple_for_clauses_in_comprehension_are_rejected():
    with pytest.raises(ExpressionError):
        evaluate_expression("[x for x in range(3) for y in range(3)]", {})


def test_import_statement_is_rejected():
    with pytest.raises(ExpressionError):
        evaluate_expression("import os", {})


def test_lambda_is_rejected():
    with pytest.raises(ExpressionError):
        evaluate_expression("(lambda: 1)()", {})

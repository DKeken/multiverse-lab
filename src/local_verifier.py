from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any, Mapping

import sympy as sp

from hypothesis_compiler import CandidateError, verify_compiled_integrity

ZERO_DIM = (Fraction(0),) * 4


class LocalScreenError(CandidateError):
    pass


def _fraction(value: int | float) -> Fraction:
    return Fraction(str(value))


def _number(value: int | float) -> sp.Expr:
    rational = _fraction(value)
    return sp.Rational(rational.numerator, rational.denominator)


def _combine_sign_mul(signs: list[str]) -> str:
    if all(sign in {"positive", "nonnegative"} for sign in signs):
        return "positive" if all(sign == "positive" for sign in signs) else "nonnegative"
    return "unknown"


def _compile_expr(node: Mapping[str, Any], declarations: Mapping[str, Any], symbols: Mapping[str, sp.Symbol]) -> tuple[sp.Expr, tuple[Fraction, ...], str]:
    if "number" in node:
        value = _fraction(node["number"])
        sign = "positive" if value > 0 else "nonnegative" if value == 0 else "unknown"
        return _number(node["number"]), ZERO_DIM, sign
    if "symbol" in node:
        name = node["symbol"]
        declaration = declarations[name]
        dimension = tuple(_fraction(value) for value in declaration["dimension"])
        domain = declaration["domain"]
        sign = "positive" if domain == "positive" else "nonnegative" if domain == "nonnegative" else "unknown"
        return symbols[name], dimension, sign
    op = node["op"]
    if op in {"add", "mul"}:
        parts = [_compile_expr(arg, declarations, symbols) for arg in node["args"]]
        expressions, dimensions, signs = zip(*parts)
        if op == "add":
            if len(set(dimensions)) != 1:
                raise LocalScreenError("ADD_DIMENSION_MISMATCH")
            sign = "positive" if all(item == "positive" for item in signs) else "nonnegative" if all(item in {"positive", "nonnegative"} for item in signs) else "unknown"
            return sp.Add(*expressions, evaluate=False), dimensions[0], sign
        dimension = tuple(sum(values, Fraction(0)) for values in zip(*dimensions))
        return sp.Mul(*expressions, evaluate=False), dimension, _combine_sign_mul(list(signs))
    if op == "neg":
        expression, dimension, _ = _compile_expr(node["arg"], declarations, symbols)
        return sp.Mul(sp.Integer(-1), expression, evaluate=False), dimension, "unknown"
    if op == "pow":
        expression, dimension, sign = _compile_expr(node["base"], declarations, symbols)
        exponent = _fraction(node["exponent"])
        if exponent.denominator != 1 and dimension != ZERO_DIM:
            raise LocalScreenError("FRACTIONAL_POWER_DIMENSIONFUL")
        if exponent < 0 and sign != "positive":
            raise LocalScreenError("POWER_DOMAIN_UNPROVEN")
        if exponent.denominator != 1 and sign not in {"positive", "nonnegative"}:
            raise LocalScreenError("POWER_DOMAIN_UNPROVEN")
        result_dimension = tuple(value * exponent for value in dimension)
        result_sign = sign if sign in {"positive", "nonnegative"} else "unknown"
        return sp.Pow(expression, sp.Rational(exponent.numerator, exponent.denominator), evaluate=False), result_dimension, result_sign
    expression, dimension, sign = _compile_expr(node["arg"], declarations, symbols)
    if dimension != ZERO_DIM:
        raise LocalScreenError("TRANSCENDENTAL_DIMENSIONFUL")
    if op == "log" and sign != "positive":
        raise LocalScreenError("LOG_DOMAIN_UNPROVEN")
    constructors = {"sin": sp.sin, "cos": sp.cos, "exp": sp.exp, "log": sp.log}
    result_sign = "positive" if op in {"exp", "log"} and op == "exp" else "unknown"
    return constructors[op](expression, evaluate=False), ZERO_DIM, result_sign


def verify_local(compiled: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(compiled))
    try:
        candidate = verify_compiled_integrity(compiled)
        declarations = candidate["symbols"]
        symbols = {name: sp.Symbol(f"Hyp_{name}", real=True) for name in declarations}
        equation_reports = []
        for index, equation in enumerate(candidate["equations"]):
            lhs, lhs_dimension, _ = _compile_expr(equation["lhs"], declarations, symbols)
            rhs, rhs_dimension, _ = _compile_expr(equation["rhs"], declarations, symbols)
            if lhs_dimension != rhs_dimension:
                raise LocalScreenError("EQUATION_DIMENSION_MISMATCH")
            equation_reports.append({
                "index": index,
                "role": equation["role"],
                "dimension": [str(value) for value in lhs_dimension],
                "sympy_lhs": sp.srepr(lhs),
                "sympy_rhs": sp.srepr(rhs),
            })
        result["status"] = "locally_screened"
        result["status_history"] = ["generated", "schema_valid", "locally_screened"]
        result["rejection_codes"] = []
        result["local_report"] = {
            "engine": "SymPy",
            "engine_version": sp.__version__,
            "equations": equation_reports,
            "boundary_checks": "declared domains checked conservatively; unknown sign/domain fails closed",
        }
    except CandidateError as exc:
        result["status"] = "rejected"
        result["status_history"] = list(dict.fromkeys([*result.get("status_history", ["generated"]), "rejected"]))
        result["rejection_codes"] = list(sorted(set(exc.codes)))
        result.pop("local_report", None)
    return result


def _wl_symbol(name: str) -> str:
    return "Hyp$" + name.encode("utf-8").hex().upper()


def _wl_number(value: int | float) -> str:
    fraction = _fraction(value)
    return f"Integer[{fraction.numerator}]" if fraction.denominator == 1 else f"Rational[{fraction.numerator},{fraction.denominator}]"


def _wl_expr(node: Mapping[str, Any]) -> str:
    if "number" in node:
        return _wl_number(node["number"])
    if "symbol" in node:
        return _wl_symbol(node["symbol"])
    op = node["op"]
    if op in {"add", "mul"}:
        head = "Plus" if op == "add" else "Times"
        return f"{head}[{','.join(_wl_expr(item) for item in node['args'])}]"
    if op == "pow":
        return f"Power[{_wl_expr(node['base'])},{_wl_number(node['exponent'])}]"
    if op == "neg":
        return f"Times[Integer[-1],{_wl_expr(node['arg'])}]"
    heads = {"sin": "Sin", "cos": "Cos", "exp": "Exp", "log": "Log"}
    return f"{heads[op]}[{_wl_expr(node['arg'])}]"


def to_wolfram(compiled: Mapping[str, Any]) -> str:
    candidate = verify_compiled_integrity(compiled)
    if compiled.get("status") != "locally_screened":
        raise CandidateError("WOLFRAM_REQUIRES_LOCAL_SCREEN")
    equations = [f"Equal[{_wl_expr(item['lhs'])},{_wl_expr(item['rhs'])}]" for item in candidate["equations"]]
    assumptions = []
    for name, declaration in sorted(candidate["symbols"].items()):
        symbol = _wl_symbol(name)
        assumptions.append(f"Element[{symbol},Reals]")
        if declaration["domain"] == "positive":
            assumptions.append(f"Greater[{symbol},Integer[0]]")
        elif declaration["domain"] == "nonnegative":
            assumptions.append(f"GreaterEqual[{symbol},Integer[0]]")
        if "min" in declaration:
            assumptions.append(f"GreaterEqual[{symbol},{_wl_number(declaration['min'])}]")
        if "max" in declaration:
            assumptions.append(f"LessEqual[{symbol},{_wl_number(declaration['max'])}]")
    expression = equations[0] if len(equations) == 1 else f"And[{','.join(equations)}]"
    assumption = "True" if not assumptions else f"And[{','.join(assumptions)}]"
    return f"FullSimplify[{expression},{assumption}]"

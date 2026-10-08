"""Reasoning visualization (--explain bonus).

Produces two views per query:
    * a readable, natural-language chain ("A is true. Since A | B => C ...").
    * a formal modus-ponens trace using logic notation (¬ ∧ ∨ ⊕ → ⊢ ∴).

It reuses the `reason` recorded on each fact node during evaluation, so the
explanation always matches what the engine actually computed. A `seen` set
prevents infinite recursion if the dependency graph has cycles.
"""
from __future__ import annotations

from ast_nodes import And, Fact, Node, Not, Or, Xor, collect_facts
from engine import Engine
from logic import Value

# Map AST operators to formal logic symbols for the formal trace.
_FORMAL_BINOP = {And: "∧", Or: "∨", Xor: "⊕"}
_FORMAL_PREC = {Xor: 1, Or: 2, And: 3, Not: 4}


def formal(node: Node) -> str:
    """Render an AST in formal logic notation (for the formal trace)."""
    if isinstance(node, Fact):
        return node.name
    if isinstance(node, Not):
        inner = formal(node.child)
        if isinstance(node.child, (And, Or, Xor)):
            inner = f"({inner})"
        return f"¬{inner}"
    my = _FORMAL_PREC[type(node)]
    sym = _FORMAL_BINOP[type(node)]

    def side(child: Node) -> str:
        txt = formal(child)
        if isinstance(child, (And, Or, Xor)) and _FORMAL_PREC[type(child)] < my:
            return f"({txt})"
        return txt

    return f"{side(node.left)} {sym} {side(node.right)}"


def _rule_formal(engine: Engine, rule) -> str:
    """Formal implication for a rule, with '↔' hint if it came from a <=>."""
    arrow = "↔" if rule.from_biconditional else "→"
    return f"{formal(rule.premise)} {arrow} {formal(rule.conclusion)}"


def explain_readable(engine: Engine, name: str, seen: set[str],
                     depth: int = 0) -> list[str]:
    """Natural-language reasoning chain for one fact."""
    value = engine.value_of(name)
    node = engine.graph.node(name)
    reason = node.reason
    pad = "  " * depth
    lines: list[str] = []

    if reason is None or reason.kind == "initial":
        src = "an initial fact" if value is Value.TRUE else "forced by the user"
        lines.append(f"{pad}{name} is {value} ({src}).")
        return lines

    if reason.kind == "closed-world":
        lines.append(f"{pad}{name} is false "
                     f"(no rule concludes it — closed-world assumption).")
        return lines

    # kind is "rule" or "undetermined": explain the deciding rule's premises.
    rule = reason.rule
    for dep in sorted(collect_facts(rule.premise)):
        if dep not in seen:
            seen.add(dep)
            lines += explain_readable(engine, dep, seen, depth + 1)
    premise_val = engine._eval_expr(rule.premise)
    if reason.kind == "rule":
        lines.append(f"{pad}Since \"{rule.text}\" and its premise is "
                     f"{premise_val}, {name} is {value}.")
    else:
        lines.append(f"{pad}\"{rule.text}\" applies (premise {premise_val}) but "
                     f"its conclusion does not pin {name} down, "
                     f"so {name} is undetermined.")
    return lines


def explain_formal(engine: Engine, name: str, seen: set[str]) -> list[str]:
    """Formal modus-ponens style trace for one fact."""
    value = engine.value_of(name)
    node = engine.graph.node(name)
    reason = node.reason
    lines: list[str] = []

    if reason is None or reason.kind == "initial":
        lines.append(f"    axiom: {name} = {value}")
        return lines
    if reason.kind == "closed-world":
        lines.append(f"    closed-world: ⊬ {name}  ∴ {name} = false")
        return lines

    rule = reason.rule
    for dep in sorted(collect_facts(rule.premise)):
        if dep not in seen:
            seen.add(dep)
            lines += explain_formal(engine, dep, seen)
    premise_val = engine._eval_expr(rule.premise)
    lines.append(f"    {formal(rule.premise)} = {premise_val};  "
                 f"[{_rule_formal(engine, rule)}]  ∴ {name} = {value}")
    return lines


def explain_query(engine: Engine, name: str) -> list[str]:
    """Full explanation block (readable + formal) for a single query."""
    out: list[str] = []
    out.append(f"--- Why is {name} {engine.value_of(name)}? ---")
    out.append("Readable:")
    out += explain_readable(engine, name, {name})
    out.append("Formal:")
    out += explain_formal(engine, name, {name})
    out.append("")
    return out

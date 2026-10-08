"""AST node definitions for logical expressions.

WHY these are dumb dataclasses with no methods: the parser must be fully
independent from the engine (subject requirement). The nodes only describe
*structure*; evaluation lives in the engine. Keeping them frozen also lets us
hash/compare them freely and guarantees the tree is immutable once parsed.

Grammar operators (A-Z facts are the atoms):
    !   NOT   (unary, highest priority)
    +   AND
    |   OR
    ^   XOR         (lowest priority among expression operators)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """A single uppercase propositional variable, e.g. ``A``."""
    name: str


@dataclass(frozen=True)
class Not:
    """Logical negation: ``!child``."""
    child: "Node"


@dataclass(frozen=True)
class And:
    """Logical AND: ``left + right``."""
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Or:
    """Logical OR: ``left | right``."""
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Xor:
    """Logical exclusive OR: ``left ^ right``."""
    left: "Node"
    right: "Node"


# A node is any of the above. (Python 3.10+ union syntax.)
Node = Fact | Not | And | Or | Xor


def collect_facts(node: Node) -> set[str]:
    """Return every fact letter that appears anywhere in the subtree."""
    if isinstance(node, Fact):
        return {node.name}
    if isinstance(node, Not):
        return collect_facts(node.child)
    # And / Or / Xor all have .left and .right
    return collect_facts(node.left) | collect_facts(node.right)


# Binding power, used only to decide when to add parentheses while printing.
# Higher = binds tighter. Matches the precedence in the subject.
_PREC = {Xor: 1, Or: 2, And: 3, Not: 4}
_BINOP_SYMBOL = {And: "+", Or: "|", Xor: "^"}


def to_str(node: Node) -> str:
    """Render a node back to source-like text with minimal parentheses.

    Used by --debug and --explain so the output matches the input notation.
    """
    if isinstance(node, Fact):
        return node.name
    if isinstance(node, Not):
        inner = to_str(node.child)
        # A NOT over a binary operator needs parentheses: !(A + B) != !A + B.
        if isinstance(node.child, (And, Or, Xor)):
            inner = f"({inner})"
        return f"!{inner}"
    my_prec = _PREC[type(node)]
    symbol = _BINOP_SYMBOL[type(node)]

    def side(child: Node) -> str:
        text = to_str(child)
        # Parenthesize a child only if it binds *looser* than us, so the
        # reconstructed string parses back to the same tree.
        if isinstance(child, (And, Or, Xor)) and _PREC[type(child)] < my_prec:
            return f"({text})"
        return text

    return f"{side(node.left)} {symbol} {side(node.right)}"

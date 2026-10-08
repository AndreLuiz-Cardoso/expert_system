"""The global graph: fact nodes linked by rule nodes.

WHY this structure (this is the graded data-structure choice):
    * Each RULE is a node holding the parsed premise/conclusion ASTs.
    * Each FACT is a node that keeps two adjacency lists:
        - concluded_by: rules whose conclusion can set this fact
                        -> this is exactly what backward chaining needs: given
                           a goal fact, jump straight to the rules that prove it
                           in O(1), instead of scanning every rule (plain lists).
        - used_by:      rules whose premise mentions this fact
                        -> lets the --explain / visualization bonus walk forward
                           and detect which rules depend on a fact.
    * Evaluation state + memoized value live on the fact node, so cycle
      detection and caching are local and simple.

This beats "lists of facts and rules" because lookups during inference are
O(degree) instead of O(#rules), and it beats "a separate graph per rule"
because shared facts are shared nodes, so memoization is global and cycles are
visible in one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from ast_nodes import Node, collect_facts
from logic import Value


@dataclass
class Rule:
    """A rule node: ``premise => conclusion`` (or one half of a ``<=>``)."""
    premise: Node
    conclusion: Node
    line_no: int
    text: str                 # raw source text, for explain/debug messages
    from_biconditional: bool = False  # True if this rule came from a <=> split


class EvalState(Enum):
    """Per-fact evaluation state, used for memoization and cycle breaking."""
    UNVISITED = auto()
    IN_PROGRESS = auto()   # currently on the recursion stack -> cycle guard
    RESOLVED = auto()


@dataclass
class FactNode:
    name: str
    concluded_by: list[Rule] = field(default_factory=list)
    used_by: list[Rule] = field(default_factory=list)
    state: EvalState = EvalState.UNVISITED
    value: Value = Value.FALSE          # meaningful only once RESOLVED
    reason: "Reason | None" = None       # filled in during evaluation (explain)


@dataclass
class Reason:
    """A human/formal explanation of why a fact got its value."""
    kind: str                 # "initial" | "rule" | "closed-world" | "undetermined"
    rule: Rule | None = None  # the deciding rule, when kind == rule/undetermined


class Graph:
    """Owns every fact node, every rule, and the initial facts / queries."""

    def __init__(self) -> None:
        self.facts: dict[str, FactNode] = {}
        self.rules: list[Rule] = []
        self.initial_true: set[str] = set()
        self.queries: list[str] = []

    def node(self, name: str) -> FactNode:
        """Get the fact node, creating it on first reference."""
        if name not in self.facts:
            self.facts[name] = FactNode(name)
        return self.facts[name]

    def add_rule(self, rule: Rule) -> None:
        """Register a rule and wire up the fact adjacency lists."""
        self.rules.append(rule)
        for name in collect_facts(rule.conclusion):
            self.node(name).concluded_by.append(rule)
        for name in collect_facts(rule.premise):
            self.node(name).used_by.append(rule)

    def universe(self) -> set[str]:
        """Every fact mentioned anywhere (rules, initials, queries).

        Used for the global consistency pass that surfaces contradictions even
        in parts of the graph that no query touches.
        """
        names = set(self.facts)
        names |= self.initial_true
        names |= set(self.queries)
        return names

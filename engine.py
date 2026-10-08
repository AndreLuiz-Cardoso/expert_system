"""The backward-chaining inference engine (three-valued, least fixpoint).

HOW A SINGLE FACT IS PROVEN (backward chaining):
    To value a fact F we look only at the rules that *conclude* F (the graph
    gives us that list directly), evaluate each rule's PREMISE by recursively
    proving the facts it mentions, and combine the results:
        - F initial/overridden true           -> contributes TRUE
        - rule premise TRUE  + conclusion forces F=v  -> contributes v
        - rule premise UNDET + would make F true      -> contributes UNDET
                                                         (it *might* fire)
        - rule premise FALSE                          -> contributes nothing
    Combine: definite TRUE and definite FALSE together => CONTRADICTION (error);
    else TRUE if any TRUE; else FALSE if any definite FALSE; else UNDET if any
    UNDET; else FALSE (closed-world: unproven facts are false).

WHY A FIXPOINT LOOP (cycle handling, the subtle part):
    Plain memoization is wrong for cyclic rules (A=>B, B=>A, =A): whichever
    fact is evaluated first sees the other as "in progress" and would cache a
    premature FALSE. So we instead compute the LEAST FIXPOINT:
      * every fact starts at its lower bound FALSE;
      * we run one backward-chaining pass over all goals; a cycle back-edge
        reads the current *estimate* of the in-progress fact (not a hard FALSE);
      * we repeat passes until no estimate changes.
    We join each new estimate with the old one (FALSE < UNDET < TRUE) so values
    only ever grow. For positive (negation-free-in-cycles) programs this is a
    no-op and we get the exact least fixpoint; the join only serves to guarantee
    termination if a negation inside a cycle would otherwise oscillate (a
    documented, non-stratified edge case).
"""
from __future__ import annotations

from ast_nodes import And, Fact, Node, Not, Or, Xor, collect_facts
from errors import ContradictionError
from graph import EvalState, FactNode, Graph, Reason, Rule
from logic import Value, v_and, v_not, v_or, v_xor


def _negate(v: Value) -> Value:
    """Flip a required truth value when descending through a NOT."""
    return v_not(v)


def _join(a: Value, b: Value) -> Value:
    """Lattice join on FALSE < UNDET < TRUE (keeps the more-informative value)."""
    return a if a.value >= b.value else b


def derive(node: Node, must_be: Value) -> dict[str, Value]:
    """Forced fact values so that `node` evaluates to `must_be`.

    A fact mapped to UNDET means the conclusion constrains it but cannot pin it
    down (e.g. ``B | C`` being true). Raises ContradictionError if a single
    conclusion is self-contradictory (``=> A + !A``).
    """
    if isinstance(node, Fact):
        return {node.name: must_be}
    if isinstance(node, Not):
        return derive(node.child, _negate(must_be))
    if isinstance(node, And):
        if must_be is Value.TRUE:
            # Both conjuncts must be TRUE -> pins both.
            return _merge(derive(node.left, Value.TRUE),
                          derive(node.right, Value.TRUE))
        return _all_undet(node)        # "AND is false" -> which side? ambiguous
    if isinstance(node, Or):
        if must_be is Value.FALSE:
            # Both disjuncts must be FALSE -> pins both.
            return _merge(derive(node.left, Value.FALSE),
                          derive(node.right, Value.FALSE))
        return _all_undet(node)        # "OR is true" -> which side? ambiguous
    if isinstance(node, Xor):
        return _all_undet(node)        # XOR never pins one operand alone
    raise AssertionError(f"unknown node type: {type(node)!r}")


def _all_undet(node: Node) -> dict[str, Value]:
    return {name: Value.UNDET for name in collect_facts(node)}


def _merge(a: dict[str, Value], b: dict[str, Value]) -> dict[str, Value]:
    out = dict(a)
    for name, val in b.items():
        if name in out and out[name] is not val:
            if {out[name], val} == {Value.TRUE, Value.FALSE}:
                raise ContradictionError(
                    f"a single conclusion forces {name} both true and false")
            # definite value beats UNDET within the same conclusion
            out[name] = val if out[name] is Value.UNDET else out[name]
        else:
            out[name] = val
    return out


class Engine:
    """Owns the graph and computes the least-fixpoint three-valued model."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.overrides: dict[str, bool] = {}  # interactive forced facts
        self._solved = False

    # --- memo / override control ---------------------------------------
    def reset_memo(self) -> None:
        for node in self.graph.facts.values():
            node.state = EvalState.UNVISITED
            node.value = Value.FALSE
            node.reason = None
        self._solved = False

    def set_override(self, name: str, truth: bool | None) -> None:
        if truth is None:
            self.overrides.pop(name, None)
        else:
            self.overrides[name] = truth
        self.reset_memo()

    def clear_overrides(self) -> None:
        self.overrides.clear()
        self.reset_memo()

    def _initial(self, name: str) -> Value | None:
        if name in self.overrides:
            return Value.TRUE if self.overrides[name] else Value.FALSE
        if name in self.graph.initial_true:
            return Value.TRUE
        return None

    # --- the fixpoint driver -------------------------------------------
    def solve(self) -> None:
        """Compute the least-fixpoint value of every fact in the universe.

        Contradictions raise ContradictionError from inside _compute.
        """
        for node in self.graph.facts.values():
            node.value = Value.FALSE
            node.reason = None

        names = sorted(self.graph.universe())
        # Make sure every universe fact has a node (queries/initials may be new).
        for name in names:
            self.graph.node(name)

        while True:
            for node in self.graph.facts.values():
                node.state = EvalState.UNVISITED
            before = {n: node.value for n, node in self.graph.facts.items()}

            for name in names:
                self._pass_eval_fact(name)

            # Monotone growth guarantees this loop terminates.
            if all(self.graph.facts[n].value is before[n] for n in before):
                break

        self._solved = True

    def _pass_eval_fact(self, name: str) -> Value:
        """Evaluate one fact within the current pass (memoized per pass)."""
        node = self.graph.node(name)
        if node.state is EvalState.RESOLVED:
            return node.value
        if node.state is EvalState.IN_PROGRESS:
            # Cycle back-edge: use the current estimate, not a hard FALSE.
            return node.value

        node.state = EvalState.IN_PROGRESS
        value, reason = self._compute(node)
        # Join with the previous estimate so values never decrease.
        joined = _join(node.value, value)
        if joined is value:
            node.reason = reason      # new value is at least as informative
        node.value = joined
        node.state = EvalState.RESOLVED
        return joined

    # --- per-fact computation (the backward-chaining step) -------------
    def _compute(self, node: FactNode) -> tuple[Value, Reason]:
        name = node.name

        contrib_true: Rule | None = None
        contrib_false: Rule | None = None
        contrib_undet: Rule | None = None

        forced_initial = self._initial(name)
        is_initial_true = forced_initial is Value.TRUE
        is_override_false = (name in self.overrides and not self.overrides[name])

        for rule in node.concluded_by:
            forced = derive(rule.conclusion, Value.TRUE).get(name)
            if forced is None:
                continue
            premise = self._pass_eval_expr(rule.premise)

            if premise is Value.TRUE:
                if forced is Value.TRUE:
                    contrib_true = contrib_true or rule
                elif forced is Value.FALSE:
                    contrib_false = contrib_false or rule
                else:
                    contrib_undet = contrib_undet or rule
            elif premise is Value.UNDET:
                # Rule might fire; only a possible-true changes the outcome.
                if forced in (Value.TRUE, Value.UNDET):
                    contrib_undet = contrib_undet or rule
            # premise FALSE -> no contribution

        has_true = is_initial_true or contrib_true is not None
        has_false = contrib_false is not None
        has_undet = contrib_undet is not None

        if has_true and has_false:
            who_true = "the initial facts" if is_initial_true else \
                f"rule '{contrib_true.text}' (line {contrib_true.line_no})"
            who_false = f"rule '{contrib_false.text}' (line {contrib_false.line_no})"
            raise ContradictionError(
                f"{name} is forced true by {who_true} "
                f"but false by {who_false}")

        if has_true:
            if is_initial_true:
                return Value.TRUE, Reason("initial")
            return Value.TRUE, Reason("rule", contrib_true)
        if has_false:
            return Value.FALSE, Reason("rule", contrib_false)
        if has_undet:
            return Value.UNDET, Reason("undetermined", contrib_undet)
        if is_override_false:
            return Value.FALSE, Reason("initial")
        return Value.FALSE, Reason("closed-world")

    # --- three-valued evaluation of an expression ----------------------
    def _pass_eval_expr(self, node: Node) -> Value:
        """Evaluate an expression during a fixpoint pass (may recurse facts)."""
        if isinstance(node, Fact):
            return self._pass_eval_fact(node.name)
        if isinstance(node, Not):
            return v_not(self._pass_eval_expr(node.child))
        if isinstance(node, And):
            return v_and(self._pass_eval_expr(node.left),
                         self._pass_eval_expr(node.right))
        if isinstance(node, Or):
            return v_or(self._pass_eval_expr(node.left),
                        self._pass_eval_expr(node.right))
        if isinstance(node, Xor):
            return v_xor(self._pass_eval_expr(node.left),
                         self._pass_eval_expr(node.right))
        raise AssertionError(f"unknown node type: {type(node)!r}")

    # --- public, read-only API (post-solve) ----------------------------
    def value_of(self, name: str) -> Value:
        if not self._solved:
            self.solve()
        return self.graph.node(name).value

    def _eval_expr(self, node: Node) -> Value:
        """Read-only expression evaluation over the solved model (for explain)."""
        if isinstance(node, Fact):
            return self.value_of(node.name)
        if isinstance(node, Not):
            return v_not(self._eval_expr(node.child))
        if isinstance(node, And):
            return v_and(self._eval_expr(node.left), self._eval_expr(node.right))
        if isinstance(node, Or):
            return v_or(self._eval_expr(node.left), self._eval_expr(node.right))
        if isinstance(node, Xor):
            return v_xor(self._eval_expr(node.left), self._eval_expr(node.right))
        raise AssertionError(f"unknown node type: {type(node)!r}")

    def check_consistency(self) -> None:
        """Run the fixpoint; contradictions surface here before any answer."""
        self.solve()

#!/usr/bin/env python3
"""Brute-force cross-checker.

For many random *positive definite* programs (head = a single positive atom;
premises = AND/OR of positive atoms; no negation, no XOR, no OR/XOR in the
conclusion) we compare the engine's TRUE/FALSE answers against an INDEPENDENT
truth-table model checker.

Why this family of programs: such programs are classic Horn programs (an
``A | B => C`` body is just two Horn rules). Horn models are closed under
intersection, so there is a unique least model, and the engine's least fixpoint
must equal it. The independent checker computes that least model by brute force:
enumerate every full truth assignment that (a) contains the initial facts and
(b) satisfies every rule read as material implication, then intersect them all.
A fact is TRUE in the least model iff it is in that intersection.

Run:  python3 tests/bruteforce.py [iterations] [seed]
"""
from __future__ import annotations

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import And, Fact, Node, Or  # noqa: E402
from engine import Engine  # noqa: E402
from graph import Graph, Rule  # noqa: E402
from logic import Value  # noqa: E402

ATOMS = "ABCDE"


def _random_body(rng: random.Random) -> Node:
    """A small AND/OR tree over 1-3 positive atoms (no negation)."""
    size = rng.randint(1, 3)
    node: Node = Fact(rng.choice(ATOMS))
    for _ in range(size - 1):
        other = Fact(rng.choice(ATOMS))
        node = (And if rng.random() < 0.5 else Or)(node, other)
    return node


def _random_program(rng: random.Random):
    """Return (rules_as_pairs, initial_true_set). Head is one positive atom."""
    n_rules = rng.randint(1, 6)
    rules = []
    for i in range(n_rules):
        body = _random_body(rng)
        head = rng.choice(ATOMS)
        rules.append((body, head, i + 1))
    n_init = rng.randint(0, 2)
    initial = set(rng.sample(list(ATOMS), n_init))
    return rules, initial


def _eval_classic(node: Node, model: set[str]) -> bool:
    """Two-valued evaluation of a body under a full assignment `model`."""
    if isinstance(node, Fact):
        return node.name in model
    if isinstance(node, And):
        return _eval_classic(node.left, model) and _eval_classic(node.right, model)
    if isinstance(node, Or):
        return _eval_classic(node.left, model) or _eval_classic(node.right, model)
    raise AssertionError("brute-force only handles AND/OR/Fact bodies")


def _least_model(rules, initial: set[str]) -> set[str]:
    """Independent ground truth: intersection of all Horn models containing I."""
    atoms = list(ATOMS)
    models: list[set[str]] = []
    for bits in itertools.product([False, True], repeat=len(atoms)):
        assignment = {a for a, b in zip(atoms, bits) if b}
        if not initial <= assignment:
            continue
        # A model must satisfy every rule as a material implication.
        ok = all((not _eval_classic(body, assignment)) or (head in assignment)
                 for body, head, _ in rules)
        if ok:
            models.append(assignment)
    # Horn => models closed under intersection => this is the least model.
    least = set(atoms)
    for m in models:
        least &= m
    return least


def _engine_answer(rules, initial: set[str]) -> dict[str, Value]:
    graph = Graph()
    graph.initial_true = set(initial)
    graph.queries = list(ATOMS)
    for body, head, line in rules:
        graph.add_rule(Rule(body, Fact(head), line, f"rule{line}"))
    engine = Engine(graph)
    engine.solve()
    return {a: engine.value_of(a) for a in ATOMS}


def main() -> int:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 12345
    rng = random.Random(seed)

    mismatches = 0
    for it in range(iterations):
        rules, initial = _random_program(rng)
        truth = _least_model(rules, initial)
        answers = _engine_answer(rules, initial)
        for atom in ATOMS:
            want = Value.TRUE if atom in truth else Value.FALSE
            if answers[atom] is not want:
                mismatches += 1
                if mismatches <= 10:
                    print(f"MISMATCH on {atom}: engine={answers[atom]} "
                          f"expected={want}")
                    print("  initial:", "".join(sorted(initial)) or "(none)")
                    for body, head, line in rules:
                        from ast_nodes import to_str
                        print(f"    {to_str(body)} => {head}")

    if mismatches:
        print(f"\nFAILED: {mismatches} mismatches over {iterations} programs")
        return 1
    print(f"OK: {iterations} random programs agree with the truth-table model "
          f"checker (seed={seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

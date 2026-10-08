"""Command-line interface: argument parsing and the main run flow.

Flow:
    1. load + validate the file (loader) -> Graph
    2. (--debug) print the parsed AST of every rule and the graph adjacency
    3. consistency pass (surfaces contradictions as errors before answering)
    4. print one line per query: "<FACT> is true|false|undetermined"
    5. (--explain) print the reasoning chain for each query
    6. (--interactive) drop into the REPL

All expected errors (InputError, ContradictionError) are caught here and sent
to stderr with a non-zero exit code -- never a Python traceback.
"""
from __future__ import annotations

import argparse
import sys

from ast_nodes import to_str
from engine import Engine
from errors import ExpertSystemError
from explain import explain_query
from graph import Graph
from interactive import repl
from loader import load


def _print_debug(graph: Graph) -> None:
    print("=== DEBUG: rules (parsed AST) ===")
    for rule in graph.rules:
        tag = "  [from <=>]" if rule.from_biconditional else ""
        print(f"  line {rule.line_no}: {to_str(rule.premise)} "
              f"=> {to_str(rule.conclusion)}{tag}")
        print(f"      premise AST    : {rule.premise!r}")
        print(f"      conclusion AST : {rule.conclusion!r}")
    print("=== DEBUG: graph (fact -> rules) ===")
    for name in sorted(graph.facts):
        node = graph.facts[name]
        cb = [f"L{r.line_no}" for r in node.concluded_by]
        ub = [f"L{r.line_no}" for r in node.used_by]
        print(f"  {name}: concluded_by={cb or '[]'}  used_by={ub or '[]'}")
    print(f"=== DEBUG: initial true = "
          f"{''.join(sorted(graph.initial_true)) or '(none)'}, "
          f"queries = {''.join(graph.queries)} ===")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expert_system",
        description="Backward-chaining inference engine for propositional calculus.")
    parser.add_argument("input_file", help="path to the rules/facts/queries file")
    parser.add_argument("--explain", action="store_true",
                        help="print the reasoning chain for each query")
    parser.add_argument("--debug", action="store_true",
                        help="print the parsed AST and the graph")
    parser.add_argument("--interactive", action="store_true",
                        help="enter a REPL to change facts and re-query")
    return parser


def run(argv: list[str]) -> int:
    # The formal-logic trace (--explain) uses Unicode symbols (→ ∧ ∨ ...).
    # On Windows the default console codec is cp1252 and would crash, so we
    # switch the streams to UTF-8 (no-op where they already are).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    try:
        graph = load(args.input_file)

        if args.debug:
            _print_debug(graph)

        engine = Engine(graph)
        # Consistency first: a contradiction must be reported instead of answers.
        engine.check_consistency()

        for name in graph.queries:
            print(f"{name} is {engine.value_of(name)}")

        if args.explain:
            print()
            for name in graph.queries:
                for line in explain_query(engine, name):
                    print(line)

        if args.interactive:
            print()
            repl(engine)

        return 0

    except ExpertSystemError as exc:
        # Clean, expected error: message to stderr, non-zero exit.
        print(f"error: {exc}", file=sys.stderr)
        return 1

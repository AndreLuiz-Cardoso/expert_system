"""Load an input file into a Graph.

Responsibilities:
    * strip comments (everything from '#') and blank lines,
    * classify each remaining line (rule / initial-facts / query),
    * validate the overall structure (exactly one '=' line, exactly one '?'
      line, uppercase facts only, ...),
    * expand '<=>' into two '=>' rules,
    * build the fact/rule graph.

Keeping this separate from parser.py means the expression parser stays a pure
tokens->AST function with no file or I/O concerns.
"""
from __future__ import annotations

from ast_nodes import And, Node
from errors import InputError
from graph import Graph, Rule
from parser import parse_rule_line


def _strip_comment(line: str) -> str:
    """Remove a trailing (or whole-line) comment starting at '#'."""
    idx = line.find("#")
    return line if idx == -1 else line[:idx]


def _parse_letter_line(body: str, line_no: int, raw: str, what: str) -> list[str]:
    """Parse the body of a '=' or '?' line into a list of fact letters.

    Spacing is ignored. Any non-uppercase, non-space character is an error.
    """
    letters: list[str] = []
    for i, ch in enumerate(body):
        if ch in " \t":
            continue
        if "A" <= ch <= "Z":
            letters.append(ch)
        else:
            # +1 for the leading '='/'?' we stripped, +1 for 1-indexing.
            raise InputError(f"{what} may only contain uppercase facts, "
                             f"found '{ch}'", line_no, i + 2, raw)
    return letters


def _split_biconditional(premise: Node, conclusion: Node,
                         line_no: int, text: str) -> list[Rule]:
    """A '<=>' means both directions, so we materialize two '=>' rules.

    E.g. ``A + B <=> !C`` becomes ``A + B => !C`` and ``!C => A + B``.
    """
    forward = Rule(premise, conclusion, line_no, text, from_biconditional=True)
    backward = Rule(conclusion, premise, line_no, text, from_biconditional=True)
    return [forward, backward]


def load(path: str) -> Graph:
    """Read and validate an input file; return a ready-to-query Graph."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw_lines = handle.readlines()
    except OSError as exc:
        raise InputError(f"cannot read file '{path}': {exc.strerror}")

    graph = Graph()
    facts_line_seen = False
    query_line_seen = False

    for line_no, raw in enumerate(raw_lines, start=1):
        raw = raw.rstrip("\n")
        content = _strip_comment(raw).strip()
        if not content:
            continue  # blank line or comment-only line

        first = content[0]

        if first == "?":
            if query_line_seen:
                raise InputError("more than one query ('?') line", line_no,
                                 1, raw)
            query_line_seen = True
            graph.queries = _parse_letter_line(content[1:], line_no, raw, "query")

        elif first == "=":
            # Careful: a rule premise can be empty-looking but a rule always
            # contains '=>' / '<=>', so a line *starting* with '=' and not being
            # '=>' is the initial-facts line. '=>...' at column 0 is a dangling
            # rule and is rejected here as a facts line with bad characters.
            if facts_line_seen:
                raise InputError("more than one initial-facts ('=') line",
                                 line_no, 1, raw)
            facts_line_seen = True
            graph.initial_true = set(
                _parse_letter_line(content[1:], line_no, raw, "initial facts"))

        else:
            # It's a rule line.
            premise, conclusion, is_iff = parse_rule_line(content, line_no)
            if is_iff:
                for rule in _split_biconditional(premise, conclusion, line_no,
                                                 content):
                    graph.add_rule(rule)
            else:
                graph.add_rule(Rule(premise, conclusion, line_no, content))

    if not facts_line_seen:
        raise InputError("missing initial-facts line (a line starting with '=')")
    if not query_line_seen:
        raise InputError("missing query line (a line starting with '?')")
    if not graph.queries:
        raise InputError("the query line is empty; at least one fact is required")

    return graph

# Expert System — backward-chaining inference engine

A propositional-calculus expert system (42 project, subject v3.3). It reads a
text file of rules, initial facts and queries, and answers each query as
`true`, `false` or `undetermined` using **backward chaining** over a global
**fact/rule graph** with **three-valued (Kleene) logic**.

Python 3.10+ (standard library only — no parsing/SAT/logic libraries).

## Usage

```sh
python3 expert_system.py <input_file> [--explain] [--debug] [--interactive]
```

Example:

```sh
python3 expert_system.py examples/spec_consistent.txt
# G is true
# V is undetermined
# X is undetermined
```

Via make (interpreter is configurable):

```sh
make run FILE=examples/chain.txt          # run on a file
make test                                 # examples + unit + brute-force
make bonus                                # demo the bonus features
# on Windows / Anaconda, pass the interpreter:
make test PYTHON="/c/Users/you/anaconda3/python.exe"
```

### Flags

| Flag            | Effect                                                             |
|-----------------|--------------------------------------------------------------------|
| `--explain`     | Print the reasoning for each query (readable + formal logic).      |
| `--debug`       | Print the parsed AST of every rule and the fact/rule graph.        |
| `--interactive` | REPL to change facts and re-query without editing the file.        |

Errors (bad syntax, contradictions, …) go to **stderr** and the program exits
with a **non-zero** status. Normal answers go to stdout.

## Input file format

- `#` starts a comment (to end of line). Blank lines are ignored. Spacing is
  irrelevant.
- **Facts** are single uppercase letters `A`–`Z`.
- **Rules**: `<expr> => <expr>` (implies) or `<expr> <=> <expr>` (iff).
- **Initial facts** line: starts with `=`, e.g. `=ABG` (A, B, G true; everything
  else false by default). A lone `=` means "no initial facts".
- **Query** line: starts with `?`, e.g. `?GVX`.
- Exactly one `=` line and exactly one `?` line are required.

### Operators (decreasing priority)

| Symbol | Meaning | Example        |
|--------|---------|----------------|
| `( )`  | group   | `A + (B \| C)` |
| `!`    | NOT     | `!B`           |
| `+`    | AND     | `A + B`        |
| `\|`   | OR      | `A \| B`       |
| `^`    | XOR     | `A ^ B`        |
| `=>`   | implies | `A + B => C`   |
| `<=>`  | iff     | `A + B <=> C`  |

Example input:

```
C => E
A | B => C
A + !B => F
V ^ W => X
A + B => Y + Z      # AND in conclusion
C | D => X | V      # OR in conclusion (bonus)
A + B <=> C         # biconditional (bonus)
=ABG
?GVX
```

## Semantics (summary)

- **Closed world**: every fact is `false` unless it is an initial fact or a rule
  proves it.
- **Undetermined**: a fact is `undetermined` only when the rule set is ambiguous
  about it — e.g. `A` true and `A => B | C` leaves `B` and `C` undetermined.
  Undetermined propagates through `!`, `+`, `|`, `^` via Kleene logic.
- **AND in conclusion** asserts every conjunct (`A => B + C` ⇒ B and C true).
  **Negation in conclusion** forces false (`E + F => !V` ⇒ V false).
- **Multiple rules** may conclude the same fact; a fact is true if *any*
  applicable rule proves it.
- **Contradictions** (a fact forced true and false) are reported as errors.
- **Cycles** (`A => B`, `B => A`) terminate and give the least-fixpoint result.

See `DESIGN.md` for the data structure, algorithm and complexity, and the truth
tables. See `DEFENSE.md` for the defense cheat-sheet.

## Project layout

```
expert_system.py   entry point
cli.py             argument parsing + run flow
lexer.py           characters -> tokens
parser.py          tokens -> AST (precedence climbing); engine-independent
ast_nodes.py       AST node types + helpers (collect_facts, to_str)
loader.py          file -> validated Graph (comments, '=', '?', <=> expansion)
logic.py           three-valued (Kleene) truth values + operators
graph.py           the global fact/rule graph
engine.py          backward chaining + least-fixpoint + contradiction detection
explain.py         --explain reasoning (readable + formal)
interactive.py     --interactive REPL
examples/          ~38 input files, one per feature / error (+ expected/)
tests/run_tests.py example-based end-to-end tests (diff vs expected/)
tests/test_unit.py unit tests (lexer, parser precedence, logic, cycles)
tests/bruteforce.py random programs vs truth-table model checker
```

## Known limitations

- **Non-stratified negation inside a cycle** (e.g. `!A => A`) has no stable
  model; the fixpoint join keeps us terminating but the result is a safe
  monotone approximation, not a stable-model semantics. Positive and
  acyclic-negation programs are exact.
- **OR/XOR in conclusions** are treated as ambiguous (the facts become
  undetermined) rather than performing disjunction elimination against other
  rules. The `--interactive` mode lets you resolve them by hand (`set B true`).
- Facts are single letters `A`–`Z`, as the subject specifies (max 26 facts).

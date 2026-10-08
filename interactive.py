"""Interactive mode (--interactive bonus).

A tiny REPL that lets the user change facts and re-query without editing the
file. Overrides live in the engine and shadow the file's initial facts; every
change clears the memo so the next query recomputes from scratch.

Commands:
    set X true | set X false   force fact X
    unset X                    drop the override on X (back to file default)
    query X [Y ...] | ? X ...   evaluate one or more facts
    show                       list current facts/overrides
    rules                      list the rules
    reset                      drop all overrides (back to the file)
    help                       show this help
    exit | quit                leave interactive mode
"""
from __future__ import annotations

from ast_nodes import to_str
from engine import Engine
from errors import ContradictionError

_HELP = __doc__


def _is_fact(tok: str) -> bool:
    return len(tok) == 1 and "A" <= tok <= "Z"


def _run_query(engine: Engine, names: list[str]) -> None:
    engine.reset_memo()
    try:
        engine.check_consistency()
        for name in names:
            if not _is_fact(name):
                print(f"  '{name}' is not a valid fact (A-Z)")
                continue
            print(f"  {name} is {engine.value_of(name)}")
    except ContradictionError as exc:
        print(f"  {exc}")


def repl(engine: Engine) -> None:
    print("Interactive mode. Type 'help' for commands, 'exit' to quit.")
    while True:
        try:
            raw = input("expert> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        if cmd in ("exit", "quit"):
            return
        if cmd == "help":
            print(_HELP)
        elif cmd == "reset":
            engine.clear_overrides()
            print("  all overrides cleared")
        elif cmd == "show":
            print(f"  file initial facts: "
                  f"{''.join(sorted(engine.graph.initial_true)) or '(none)'}")
            if engine.overrides:
                for name, truth in sorted(engine.overrides.items()):
                    print(f"  override: {name} = {str(truth).lower()}")
            else:
                print("  overrides: (none)")
        elif cmd == "rules":
            for rule in engine.graph.rules:
                tag = " [<=> half]" if rule.from_biconditional else ""
                print(f"  {to_str(rule.premise)} => {to_str(rule.conclusion)}{tag}")
        elif cmd == "set":
            if len(parts) != 3 or not _is_fact(parts[1]) or \
                    parts[2].lower() not in ("true", "false"):
                print("  usage: set <FACT> true|false")
                continue
            engine.set_override(parts[1], parts[2].lower() == "true")
            print(f"  {parts[1]} forced {parts[2].lower()}")
        elif cmd == "unset":
            if len(parts) != 2 or not _is_fact(parts[1]):
                print("  usage: unset <FACT>")
                continue
            engine.set_override(parts[1], None)
            print(f"  {parts[1]} override removed")
        elif cmd in ("query", "?") or _is_fact(cmd.upper()) and len(cmd) == 1:
            # Accept "query X", "? X", or a bare list of fact letters.
            if cmd in ("query", "?"):
                names = [p.upper() for p in parts[1:]]
            else:
                names = [p.upper() for p in parts]
            if not names:
                print("  usage: query <FACT> [<FACT> ...]")
                continue
            _run_query(engine, names)
        else:
            print(f"  unknown command '{cmd}' (type 'help')")

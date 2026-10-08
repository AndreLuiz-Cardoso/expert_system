#!/usr/bin/env python3
"""Example-based end-to-end test runner.

For every examples/*.txt it runs the program, captures stdout+stderr merged,
and diffs against examples/expected/<name>.out. Files named ``err_*`` are
expected to fail (non-zero exit); all others must exit 0.

Usage:
    python3 tests/run_tests.py            # run and diff
    python3 tests/run_tests.py --update   # (re)generate the expected files
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXAMPLES = os.path.join(ROOT, "examples")
EXPECTED = os.path.join(EXAMPLES, "expected")
ENTRY = os.path.join(ROOT, "expert_system.py")


def run_one(path: str) -> tuple[str, int]:
    """Run the engine on one input file, return (merged_output, exit_code)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, ENTRY, path],
        capture_output=True, text=True, encoding="utf-8", env=env)
    return proc.stdout + proc.stderr, proc.returncode


def main() -> int:
    update = "--update" in sys.argv
    os.makedirs(EXPECTED, exist_ok=True)

    inputs = sorted(f for f in os.listdir(EXAMPLES) if f.endswith(".txt"))
    passed = failed = 0

    for name in inputs:
        base = name[:-4]
        in_path = os.path.join(EXAMPLES, name)
        exp_path = os.path.join(EXPECTED, base + ".out")
        output, code = run_one(in_path)

        if update:
            with open(exp_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(output)
            # An error run must exit non-zero; a normal run must exit zero.
            want_fail = output.lstrip().startswith("error:")
            tag = "OK " if (code != 0) == want_fail else "BAD-EXIT"
            print(f"[update] {tag} {base}")
            passed += 1
            continue

        if not os.path.exists(exp_path):
            print(f"[MISS ] {base}: no expected file (run with --update)")
            failed += 1
            continue
        with open(exp_path, "r", encoding="utf-8") as fh:
            expected = fh.read()

        # The expected output tells us whether this run should fail.
        should_fail = expected.lstrip().startswith("error:")
        code_ok = (code != 0) if should_fail else (code == 0)

        if output == expected and code_ok:
            passed += 1
        else:
            failed += 1
            print(f"[FAIL ] {base} (exit={code}, expected_fail={should_fail})")
            print("  --- expected ---")
            for line in expected.splitlines():
                print(f"  | {line}")
            print("  --- got ---")
            for line in output.splitlines():
                print(f"  | {line}")

    print(f"\n{passed} passed, {failed} failed "
          f"({len(inputs)} examples)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Entry point: `python3 expert_system.py <input_file> [flags]`.

Thin wrapper so the actual logic stays in importable modules (easier to test).
"""
import sys

from cli import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))

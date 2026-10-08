#!/usr/bin/env python3
"""Unit tests for the lexer, parser precedence, three-valued logic,
the `derive` helper, and cycle handling.

Run with:  python3 -m unittest tests.test_unit      (from the project root)
       or:  python3 tests/test_unit.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# Make the project modules importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import And, Fact, Not, Or, Xor  # noqa: E402
from engine import Engine, derive  # noqa: E402
from errors import ContradictionError, InputError  # noqa: E402
from lexer import TokKind, lex  # noqa: E402
from loader import load  # noqa: E402
from logic import Value, v_and, v_not, v_or, v_xor  # noqa: E402
from parser import parse_rule_line  # noqa: E402

T, F, U = Value.TRUE, Value.FALSE, Value.UNDET


def _engine_from_text(text: str) -> Engine:
    """Build a solved engine from an inline input-file string."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        engine = Engine(load(path))
        engine.solve()
        return engine
    finally:
        os.unlink(path)


class TestLexer(unittest.TestCase):
    def test_all_operators(self):
        kinds = [t.kind for t in lex("A + B | C ^ !D => E <=> F", 1)]
        self.assertEqual(kinds, [
            TokKind.FACT, TokKind.AND, TokKind.FACT, TokKind.OR, TokKind.FACT,
            TokKind.XOR, TokKind.NOT, TokKind.FACT, TokKind.IMPLIES,
            TokKind.FACT, TokKind.IFF, TokKind.FACT])

    def test_comment_is_ignored(self):
        self.assertEqual(len(lex("A + B # this is a comment => Z", 1)), 3)

    def test_unknown_char_raises(self):
        with self.assertRaises(InputError):
            lex("A & B", 1)

    def test_lowercase_raises(self):
        with self.assertRaises(InputError):
            lex("a => B", 1)


class TestParserPrecedence(unittest.TestCase):
    def _premise(self, text: str):
        premise, _concl, _iff = parse_rule_line(text + " => Z", 1)
        return premise

    def test_plus_or_xor_precedence(self):
        # +  >  |  >  ^   =>   ((A + B) | C) ^ D
        self.assertEqual(self._premise("A + B | C ^ D"),
                         Xor(Or(And(Fact("A"), Fact("B")), Fact("C")), Fact("D")))

    def test_not_binds_tighter_than_and(self):
        # !A + B  =>  (!A) + B
        self.assertEqual(self._premise("!A + B"),
                         And(Not(Fact("A")), Fact("B")))

    def test_nested_parentheses(self):
        # A + (B | (C ^ D))
        self.assertEqual(self._premise("A + (B | (C ^ D))"),
                         And(Fact("A"), Or(Fact("B"),
                                           Xor(Fact("C"), Fact("D")))))

    def test_parens_override_precedence(self):
        # (A + B) | C  differs from A + B | C only in intent, same tree here;
        # but A + (B | C) must group the OR first.
        self.assertEqual(self._premise("A + (B | C)"),
                         And(Fact("A"), Or(Fact("B"), Fact("C"))))

    def test_double_implication_rejected(self):
        with self.assertRaises(InputError):
            parse_rule_line("A => B => C", 1)

    def test_dangling_operator_rejected(self):
        with self.assertRaises(InputError):
            parse_rule_line("A + => B", 1)

    def test_unbalanced_paren_rejected(self):
        with self.assertRaises(InputError):
            parse_rule_line("A + (B | C => D", 1)


class TestThreeValuedLogic(unittest.TestCase):
    def test_not(self):
        self.assertEqual(v_not(T), F)
        self.assertEqual(v_not(F), T)
        self.assertEqual(v_not(U), U)

    def test_and_table(self):
        self.assertEqual(v_and(T, T), T)
        self.assertEqual(v_and(T, F), F)
        self.assertEqual(v_and(T, U), U)
        self.assertEqual(v_and(F, U), F)   # one false short-circuits
        self.assertEqual(v_and(U, U), U)

    def test_or_table(self):
        self.assertEqual(v_or(F, F), F)
        self.assertEqual(v_or(T, F), T)
        self.assertEqual(v_or(T, U), T)    # one true short-circuits
        self.assertEqual(v_or(F, U), U)
        self.assertEqual(v_or(U, U), U)

    def test_xor_table(self):
        self.assertEqual(v_xor(T, F), T)
        self.assertEqual(v_xor(T, T), F)
        self.assertEqual(v_xor(F, F), F)
        self.assertEqual(v_xor(T, U), U)   # unknown poisons xor
        self.assertEqual(v_xor(F, U), U)
        self.assertEqual(v_xor(U, U), U)


class TestDerive(unittest.TestCase):
    def test_single_fact(self):
        self.assertEqual(derive(Fact("B"), T), {"B": T})

    def test_negated_conclusion_forces_false(self):
        self.assertEqual(derive(Not(Fact("V")), T), {"V": F})

    def test_and_conclusion_pins_both(self):
        self.assertEqual(derive(And(Fact("B"), Fact("C")), T), {"B": T, "C": T})

    def test_or_conclusion_is_ambiguous(self):
        self.assertEqual(derive(Or(Fact("B"), Fact("C")), T), {"B": U, "C": U})

    def test_xor_conclusion_is_ambiguous(self):
        self.assertEqual(derive(Xor(Fact("B"), Fact("C")), T), {"B": U, "C": U})

    def test_self_contradictory_conclusion_raises(self):
        with self.assertRaises(ContradictionError):
            derive(And(Fact("A"), Not(Fact("A"))), T)


class TestEngineSemantics(unittest.TestCase):
    def test_simple_chain(self):
        e = _engine_from_text("A => B\nB => C\n=A\n?C\n")
        self.assertEqual(e.value_of("C"), T)

    def test_closed_world_false(self):
        e = _engine_from_text("A => B\n=\n?B\n")
        self.assertEqual(e.value_of("B"), F)

    def test_undetermined_or_conclusion(self):
        e = _engine_from_text("A => B | C\n=A\n?B\n")
        self.assertEqual(e.value_of("B"), U)
        self.assertEqual(e.value_of("C"), U)

    def test_cycle_without_facts_is_false(self):
        e = _engine_from_text("A => B\nB => A\n=\n?A\n")
        self.assertEqual(e.value_of("A"), F)
        self.assertEqual(e.value_of("B"), F)

    def test_cycle_with_fact_is_true(self):
        # The regression that broke a naive single-pass memo: A given, A<->B.
        e = _engine_from_text("A => B\nB => A\n=A\n?B\n")
        self.assertEqual(e.value_of("B"), T)

    def test_contradiction_detected(self):
        with self.assertRaises(ContradictionError):
            _engine_from_text("A => X\nB => !X\n=AB\n?X\n")

    def test_biconditional_both_directions(self):
        fwd = _engine_from_text("A + B <=> C\n=AB\n?C\n")
        self.assertEqual(fwd.value_of("C"), T)
        bwd = _engine_from_text("A + B <=> C\n=C\n?A\n")
        self.assertEqual(bwd.value_of("A"), T)


if __name__ == "__main__":
    unittest.main(verbosity=2)

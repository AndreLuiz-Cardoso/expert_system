"""Three-valued (Kleene) logic.

WHY three values: the subject distinguishes TRUE, FALSE and UNDETERMINED.
A fact is UNDETERMINED when the rule set is ambiguous about it (e.g. a rule
concludes ``B | C`` without pinning which one). We propagate that "unknown"
through the operators using Kleene's strong three-valued logic, which is the
standard, well-defined way to reason with an "unknown" truth value.

Truth tables (T = true, F = false, U = undetermined):

    NOT:   !T=F   !F=T   !U=U

    AND (+)  | T U F        OR (|)   | T U F        XOR (^) | T U F
        -----+------            -----+------            ----+------
          T  | T U F              T  | T T T              T | F U T
          U  | U U F              U  | T U U              U | U U U
          F  | F F F              F  | T U F              F | T U F

    Intuition:
      * AND is F as soon as one side is F; else U if any side is U; else T.
      * OR  is T as soon as one side is T; else U if any side is U; else F.
      * XOR is U whenever *either* side is U, because flipping the unknown
        side would flip the result -- so the result cannot be pinned down.
        Otherwise it is the usual parity (true iff the sides differ).
"""
from __future__ import annotations

from enum import Enum


class Value(Enum):
    """A three-valued truth value. Ordering is intentional but unused for math."""
    FALSE = 0
    UNDET = 1
    TRUE = 2

    def __str__(self) -> str:
        return {
            Value.TRUE: "true",
            Value.FALSE: "false",
            Value.UNDET: "undetermined",
        }[self]


def v_not(a: Value) -> Value:
    if a is Value.UNDET:
        return Value.UNDET
    return Value.TRUE if a is Value.FALSE else Value.FALSE


def v_and(a: Value, b: Value) -> Value:
    if a is Value.FALSE or b is Value.FALSE:
        return Value.FALSE
    if a is Value.UNDET or b is Value.UNDET:
        return Value.UNDET
    return Value.TRUE


def v_or(a: Value, b: Value) -> Value:
    if a is Value.TRUE or b is Value.TRUE:
        return Value.TRUE
    if a is Value.UNDET or b is Value.UNDET:
        return Value.UNDET
    return Value.FALSE


def v_xor(a: Value, b: Value) -> Value:
    # Unknown on either side poisons the result (see module docstring).
    if a is Value.UNDET or b is Value.UNDET:
        return Value.UNDET
    return Value.TRUE if a is not b else Value.FALSE

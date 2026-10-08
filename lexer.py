"""Lexer: turn a rule line into a flat list of tokens.

The lexer only knows about *characters*; it does not understand precedence or
structure (that is the parser's job). It records a 1-indexed column for every
token so that syntax errors can point at the exact character.

Only rule lines go through this lexer. The ``=`` initial-facts line and the
``?`` query line are handled separately in loader.py because their grammar is
trivial (just a run of uppercase letters).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from errors import InputError


class TokKind(Enum):
    LPAREN = auto()
    RPAREN = auto()
    NOT = auto()       # !
    AND = auto()       # +
    OR = auto()        # |
    XOR = auto()       # ^
    IMPLIES = auto()   # =>
    IFF = auto()       # <=>
    FACT = auto()      # A single uppercase letter


@dataclass(frozen=True)
class Token:
    kind: TokKind
    col: int            # 1-indexed column where the token starts
    value: str = ""     # the fact letter, for FACT tokens


# Single-character operators map directly to a token kind.
_SINGLE = {
    "(": TokKind.LPAREN,
    ")": TokKind.RPAREN,
    "!": TokKind.NOT,
    "+": TokKind.AND,
    "|": TokKind.OR,
    "^": TokKind.XOR,
}


def lex(text: str, line_no: int) -> list[Token]:
    """Tokenize one rule line. Raises InputError on any unknown character."""
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        col = i + 1  # 1-indexed for human-friendly messages

        if ch in " \t":          # spacing is irrelevant per the subject
            i += 1
            continue
        if ch == "#":            # comment: ignore the rest of the line
            break
        if ch in _SINGLE:
            tokens.append(Token(_SINGLE[ch], col))
            i += 1
            continue
        if ch == "=":            # must be "=>"
            if text[i + 1:i + 2] == ">":
                tokens.append(Token(TokKind.IMPLIES, col))
                i += 2
                continue
            raise InputError("expected '>' after '=' (did you mean '=>'?)",
                             line_no, col, text)
        if ch == "<":            # must be "<=>"
            if text[i + 1:i + 3] == "=>":
                tokens.append(Token(TokKind.IFF, col))
                i += 3
                continue
            raise InputError("expected '=>' after '<' (did you mean '<=>'?)",
                             line_no, col, text)
        if "A" <= ch <= "Z":
            tokens.append(Token(TokKind.FACT, col, ch))
            i += 1
            continue
        if "a" <= ch <= "z":
            raise InputError(f"facts must be uppercase, found '{ch}'",
                             line_no, col, text)
        raise InputError(f"unknown character '{ch}'", line_no, col, text)

    return tokens

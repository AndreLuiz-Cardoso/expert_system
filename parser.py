"""Parser: tokens -> AST, by recursive descent with precedence climbing.

The grammar encodes operator precedence directly (one function per level),
which is the clearest way to defend it at a review. From loosest to tightest
binding, matching the subject's "decreasing priority" list read bottom-up:

    expr      := xor_expr
    xor_expr  := or_expr   ( '^' or_expr   )*      # XOR binds loosest
    or_expr   := and_expr  ( '|' and_expr  )*
    and_expr  := not_expr  ( '+' not_expr  )*
    not_expr  := '!' not_expr | primary            # NOT binds tightest (unary)
    primary   := FACT | '(' expr ')'

A full rule line is:  expr ( '=>' | '<=>' ) expr   and nothing else.

The parser is deliberately independent from the engine: it only builds the AST
defined in ast_nodes.py and never evaluates anything.
"""
from __future__ import annotations

from ast_nodes import And, Fact, Node, Not, Or, Xor
from errors import InputError
from lexer import Token, TokKind, lex


class _Parser:
    """A tiny cursor over the token list for one rule line."""

    def __init__(self, tokens: list[Token], line_no: int, text: str) -> None:
        self.tokens = tokens
        self.line_no = line_no
        self.text = text
        self.pos = 0

    # --- cursor helpers -------------------------------------------------
    def _peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _error(self, msg: str, tok: Token | None) -> InputError:
        # Point at the token's column, or just past the end if we ran out.
        col = tok.col if tok is not None else (len(self.text) + 1)
        return InputError(msg, self.line_no, col, self.text)

    # --- grammar (one method per precedence level) ----------------------
    def parse_expr(self) -> Node:
        return self._xor()

    def _xor(self) -> Node:
        node = self._or()
        while self._peek() and self._peek().kind is TokKind.XOR:
            self._advance()
            node = Xor(node, self._or())
        return node

    def _or(self) -> Node:
        node = self._and()
        while self._peek() and self._peek().kind is TokKind.OR:
            self._advance()
            node = Or(node, self._and())
        return node

    def _and(self) -> Node:
        node = self._not()
        while self._peek() and self._peek().kind is TokKind.AND:
            self._advance()
            node = And(node, self._not())
        return node

    def _not(self) -> Node:
        tok = self._peek()
        if tok and tok.kind is TokKind.NOT:
            self._advance()
            return Not(self._not())  # right-recursive: !!A is valid
        return self._primary()

    def _primary(self) -> Node:
        tok = self._peek()
        if tok is None:
            raise self._error("unexpected end of expression (operand expected)", None)
        if tok.kind is TokKind.FACT:
            self._advance()
            return Fact(tok.value)
        if tok.kind is TokKind.LPAREN:
            self._advance()
            node = self.parse_expr()
            closing = self._peek()
            if closing is None or closing.kind is not TokKind.RPAREN:
                raise self._error("unbalanced parentheses: ')' expected", closing)
            self._advance()
            return node
        # IMPLIES/IFF/operators/RPAREN here mean a missing operand.
        raise self._error("expected a fact or '(' here", tok)


# The two implication kinds that separate premise from conclusion.
_IMPLICATION = {TokKind.IMPLIES, TokKind.IFF}


def parse_rule_line(text: str, line_no: int) -> tuple[Node, Node, bool]:
    """Parse one rule line into (premise, conclusion, is_biconditional).

    Enforces exactly one top-level implication and no leftover tokens.
    """
    tokens = lex(text, line_no)
    if not tokens:
        raise InputError("empty rule", line_no, 1, text)

    # A valid rule has exactly one implication token (parentheses only group
    # expression operators, never implications), so counting them is a cheap,
    # defensible structural check.
    impl_positions = [i for i, t in enumerate(tokens) if t.kind in _IMPLICATION]
    if len(impl_positions) == 0:
        raise InputError("a rule must contain '=>' or '<=>'", line_no, 1, text)
    if len(impl_positions) > 1:
        second = tokens[impl_positions[1]]
        raise InputError("a rule may contain only one '=>' or '<=>'",
                         line_no, second.col, text)

    parser = _Parser(tokens, line_no, text)
    premise = parser.parse_expr()

    op = parser._peek()
    if op is None or op.kind not in _IMPLICATION:
        raise InputError("expected '=>' or '<=>' after the premise",
                         line_no, op.col if op else len(text) + 1, text)
    is_biconditional = op.kind is TokKind.IFF
    parser._advance()

    conclusion = parser.parse_expr()

    leftover = parser._peek()
    if leftover is not None:
        raise InputError("unexpected token after conclusion", line_no,
                         leftover.col, text)

    return premise, conclusion, is_biconditional

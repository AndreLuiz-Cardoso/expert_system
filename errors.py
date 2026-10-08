"""Error types for the expert system.

We use a single base class (``ExpertSystemError``) so the CLI can catch every
"expected" problem (bad input, logical contradiction, ...) in one place and
print a clean message to stderr instead of crashing with a Python traceback.
That is exactly what the subject asks for: "Never crash with a traceback on
bad input".
"""
from __future__ import annotations


class ExpertSystemError(Exception):
    """Base class for all errors we raise on purpose."""


class InputError(ExpertSystemError):
    """A problem in the input file: syntax error, lexing error, bad structure.

    We carry the line number (and optionally the column and the raw line) so
    the message can point the user to the exact spot.
    """

    def __init__(self, message: str, line_no: int | None = None,
                 col: int | None = None, line_text: str | None = None) -> None:
        self.message = message
        self.line_no = line_no
        self.col = col
        self.line_text = line_text
        super().__init__(self._format())

    def _format(self) -> str:
        where = ""
        if self.line_no is not None:
            where = f" (line {self.line_no}"
            if self.col is not None:
                where += f", col {self.col}"
            where += ")"
        out = f"Syntax error{where}: {self.message}"
        if self.line_text is not None:
            out += f"\n    {self.line_text}"
            if self.col is not None:
                # Point a caret under the offending column (1-indexed col).
                out += "\n    " + " " * (self.col - 1) + "^"
        return out


class ContradictionError(ExpertSystemError):
    """The rule set is logically inconsistent (a fact is forced true and false).

    This is a semantic error, not a syntax error, so it gets its own type.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Contradiction: {message}")

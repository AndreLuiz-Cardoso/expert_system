# DEFENSE cheat-sheet

## Hand-computation of the subject's showcase file

The appendix file (`examples/spec_full.txt`) contains, with `=ABG` and `?GVX`:

```
C => E
A + B + C => D
A | B => C
A + !B => F
C | !G => H
V ^ W => X
A + B => Y + Z
C | D => X | V
E + F => !V
A + B <=> C
A + B <=> !C
```

Initial facts: `A, B, G` true; everything else false by default.

**Key observation — the file is contradictory by construction.** The last two
rules are `A + B <=> C` and `A + B <=> !C`. Expanding the forward directions:

- `A + B => C`  — since `A,B` are true, `A + B` is true ⇒ **C must be true**.
- `A + B => !C` — same premise is true ⇒ **C must be false**.

So `C` is forced both true and false: a genuine contradiction. Our engine
detects it during the consistency pass and reports:

```
error: Contradiction: C is forced true by rule 'A | B => C' (line 7) but false by rule 'A + B <=> !C' (line 15)
```

(Lines 7/15 are the rule lines in the file; the `<=>` rules are split into two
`=>` rules internally.) Exit status is non-zero. **This is the correct
behavior** — the showcase file mixes every operator for syntax demonstration,
not a consistent knowledge base.

### The same file, made consistent (`examples/spec_consistent.txt`)

Drop the contradictory `A + B <=> !C`. Now trace the three queries by hand:

- `C`: `A | B => C`, premise `A|B = T|T = T` ⇒ **C = true**. (`A+B => C` agrees.)
- `E`: `C => E`, C true ⇒ **E = true**.
- `F`: `A + !B => F`, premise `A + !B = T + !T = T + F = F` ⇒ rule does not fire;
  no other rule concludes F ⇒ **F = false** (closed world).
- `V`: concluded by
  - `E + F => !V`: premise `E + F = T + F = F` ⇒ does not fire;
  - `C | D => X | V`: premise `C|D = T` ⇒ fires, conclusion `X | V` is an OR,
    which is ambiguous ⇒ V gets **undetermined**.
  ⇒ **V = undetermined**.
- `X`: concluded by
  - `V ^ W => X`: premise `V ^ W = U ^ F = U` (undetermined poisons XOR) ⇒
    premise undetermined, rule would make X true ⇒ contributes undetermined;
  - `C | D => X | V`: premise true, conclusion `X | V` ambiguous ⇒ undetermined.
  ⇒ **X = undetermined**.
- `G`: `G` is an initial fact and no rule forces it false ⇒ **G = true**.

Final answers:

```
G is true
V is undetermined
X is undetermined
```

Both match the program output exactly (verified by the test suite).

---

## 10 questions an evaluator will likely ask

**1. Why backward chaining, and where is it in the code?**
To answer a query we start from the goal fact and look only at the rules that
*conclude* it (`FactNode.concluded_by`), then recursively prove their premises.
That is `Engine._compute` + `_pass_eval_expr`. We never blindly fire all rules
forward; we expand goals on demand.

**2. Then why is there a loop over all facts (`solve`)?**
Because a naive memo gives wrong answers on cyclic rules: a fact evaluated while
a cycle ancestor is still "in progress" would cache a premature `false`. `solve`
recomputes passes until the estimates stop changing, yielding the least
fixpoint. Each pass is still goal-directed backward chaining; the loop only
makes the memo correct under cycles.

**3. How exactly are cycles handled and why does it terminate?**
A fact's state is UNVISITED/IN_PROGRESS/RESOLVED per pass. A back-edge to an
IN_PROGRESS fact returns its current estimate instead of recursing forever.
Values are joined on `FALSE < UNDET < TRUE` so they only grow; the lattice has
height 3 and there are `n` facts, so the pass loop runs at most `O(n)` times.

**4. What is "undetermined" and when does it occur?**
A third truth value for "the rule set is ambiguous about this fact." It appears
when a conclusion cannot pin a fact: `A => B | C` (OR), `A => B ^ C` (XOR), or a
premise that is itself undetermined. By default facts are false (closed world),
never undetermined.

**5. Give the three-valued truth tables, especially XOR with an unknown.**
See DESIGN.md §2. The subtle one: `X ^ U = U` for any X, because flipping the
unknown operand flips the result, so it can't be determined.

**6. How do you parse, and how is precedence enforced?**
`lexer.py` turns characters into tokens; `parser.py` is recursive descent with
one function per precedence level (`xor → or → and → not → primary`), so
`A + B | C ^ D` parses as `((A+B)|C)^D` and `!A + B` as `(!A)+B`. The parser
only builds the AST; it has no dependency on the engine.

**7. How is a conclusion like `A => B + C` or `E + F => !V` applied?**
`derive(conclusion, TRUE)` walks the conclusion AST and returns the value each
fact is forced to: `B + C` ⇒ both true, `!V` ⇒ V false. Ambiguous shapes map
every involved fact to undetermined.

**8. How are contradictions detected?**
In `_compute`, if a fact collects a definite `TRUE` (initial fact or a fired
rule) *and* a definite `FALSE` (a fired rule concluding its negation), we raise
`ContradictionError`. We run a consistency pass over every fact first, so a
contradiction is caught even if no query touches it.

**9. How does `<=>` work?**
`loader.py` expands `L <=> R` into two rules `L => R` and `R => L` at load time
(including negations, e.g. `A + B <=> !C`), so the engine only ever deals with
`=>`. The explain output marks these as coming from a biconditional.

**10. How do you know the logic is correct?**
Three layers: ~38 end-to-end example files diffed against expected output
(`tests/run_tests.py`); unit tests for the lexer, parser precedence, truth
tables, `derive`, and cycles (`tests/test_unit.py`); and a brute-force
cross-checker that compares the engine against an independent truth-table least-
model computation over 2000 random programs (`tests/bruteforce.py`).

---

## Quick demo script for the defense

```sh
make test                                              # everything is green
python3 expert_system.py examples/spec_full.txt        # contradiction (exit 1)
python3 expert_system.py examples/spec_consistent.txt  # G true, V/X undetermined
python3 expert_system.py examples/undetermined.txt --explain
python3 expert_system.py examples/parentheses.txt --debug
python3 expert_system.py examples/cycle_true.txt       # terminates, B true
python3 expert_system.py examples/bonus_or_conclusion.txt --interactive
#   > set B true   (resolves the undetermined fact)
#   > query B
```

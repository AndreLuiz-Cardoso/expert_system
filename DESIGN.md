# DESIGN — data structure, algorithm, complexity

## 1. Data structure: a global graph of fact nodes linked by rule nodes

This is the most-complex option the subject offers, and it is the one we
implement (see `graph.py`).

```
          premise AST                     conclusion AST
   (facts) ───────▶  [ RULE node ]  ───────▶ (facts)
      ▲                                           │
      │ used_by                      concluded_by │
      └───────────────  FACT node  ◀──────────────┘
```

- **Rule node** (`Rule`): holds the parsed `premise` AST, the `conclusion` AST,
  the source line and raw text, and a flag telling whether it came from a
  `<=>` expansion.
- **Fact node** (`FactNode`): holds two adjacency lists plus evaluation state:
  - `concluded_by`: the rules whose conclusion can set this fact,
  - `used_by`: the rules whose premise mentions this fact,
  - `state` (UNVISITED / IN_PROGRESS / RESOLVED), `value`, and a `reason`.

### Why this beats the simpler options

- **vs. plain lists of facts/rules:** backward chaining constantly asks "which
  rules can prove fact F?". With `concluded_by` that is an **O(1)** jump to a
  short adjacency list; with plain lists it is an **O(#rules)** scan *every
  time* we expand a goal. For a query of depth *d* branching over *b* rules,
  lists give O(d·b·#rules) vs. the graph's O(edges visited).
- **vs. a separate graph per rule:** shared facts would be duplicated across
  per-rule graphs, so memoization could not be global and a cycle spanning two
  rules would be invisible. Here every fact is a single shared node, so the
  memo and cycle detection are global and local to the node.
- `used_by` is what powers the `--explain` / visualization bonus and would let
  a forward pass propagate changes (useful for `--interactive`).

The AST inside each rule node is built by a parser that never touches the
engine, so the structure (what the rules *are*) is cleanly separated from the
inference (what the engine *does* with them).

## 2. Three-valued (Kleene) logic

Values: `TRUE`, `FALSE`, `UNDETERMINED`. A fact is `UNDETERMINED` only when the
rule set genuinely cannot pin it down (ambiguous conclusion such as `B | C`).
`UNDETERMINED` then propagates through the operators:

```
NOT:  !T=F   !F=T   !U=U

AND(+) | T U F        OR(|) | T U F        XOR(^) | T U F
   ----+------           ---+------           ----+------
    T  | T U F            T | T T T            T  | F U T
    U  | U U F            U | T U U            U  | U U U
    F  | F F F            F | T U F            F  | T U F
```

- AND is false as soon as one side is false; else undetermined if any side is;
  else true. (Dually for OR.)
- XOR is undetermined whenever **either** side is undetermined: flipping the
  unknown side would flip the result, so it cannot be pinned down.

## 3. Algorithm: backward chaining to a least fixpoint

### Proving one fact (backward chaining)

To value a fact `F` (`Engine._compute`):

1. `F` is an initial fact / overridden-true ⇒ contributes `TRUE`.
2. For each rule in `F.concluded_by`:
   - evaluate the rule's **premise** (recursively proving the facts it mentions),
   - `derive(conclusion, TRUE)` tells us what value the conclusion *forces* on
     `F` if the rule fires,
   - premise `TRUE` ⇒ contribute that forced value;
     premise `UNDETERMINED` ⇒ the rule *might* fire, so a would-be-true
     contributes `UNDETERMINED`;
     premise `FALSE` ⇒ nothing.
3. Combine: a definite `TRUE` **and** a definite `FALSE` ⇒ **contradiction**;
   else `TRUE` if any true; else `FALSE` if any definite false; else
   `UNDETERMINED` if any; else `FALSE` (closed world).

`derive(node, must_be)` maps conclusion facts to forced values. Conjunctions of
literals pin their facts (`A + B` ⇒ both true, `!V` ⇒ V false). Ambiguous shapes
(`OR` true, `XOR`, `AND` false) mark every involved fact `UNDETERMINED` — this
is exactly why `A => B | C` leaves `B`, `C` undetermined.

### Cycles and why a plain memo is wrong

Consider `A => B`, `B => A`, `=A`, `?B`. With naive memoization, if the engine
happens to evaluate `A` first, it recurses into `B` while `A` is still "in
progress", so `B` sees `A` as not-yet-true and gets **memoized false** — a
permanent wrong answer that depends on evaluation order.

So instead we compute the **least fixpoint** (`Engine.solve`):

- every fact starts at its lower bound `FALSE`;
- one backward-chaining **pass** evaluates all goals; a cycle back-edge returns
  the in-progress fact's **current estimate** (not a hard false);
- we repeat passes until no estimate changes.

Each new estimate is **joined** with the old one on the lattice
`FALSE < UNDETERMINED < TRUE`, so values only ever grow. For positive programs
(no negation in cycles) new ≥ old always, the join is a no-op, and we get the
**exact** least fixpoint. The join only matters to guarantee termination if a
negation inside a cycle would otherwise oscillate (a documented, non-stratified
edge case — see Limitations in the README).

Backward chaining is preserved: each pass is still goal-directed (start at the
query, recurse into premises). The outer loop is only there to make the memo
correct under cycles; it is not a blind forward fixpoint over all facts.

### Contradiction detection

Before printing any answer we run a consistency pass (`check_consistency`) that
solves every fact in the universe (all facts mentioned, plus initials and
queries). A contradiction anywhere — e.g. an initial fact a rule forces false,
or two rules deriving `X` and `!X` — raises and is reported, instead of being
silently resolved or missed because no query touched it.

## 4. Complexity

Let `n` = number of facts, `m` = number of rules, `e` = number of fact↔rule
edges (≈ total literals in all rules).

- One pass visits each fact once (memoized) and, per fact, scans its
  `concluded_by` rules and evaluates their premises: total **O(n + e)**.
- The fixpoint runs at most `2n + 1` passes: each pass that changes anything
  raises at least one fact one step up the 3-level lattice, and there are `n`
  facts × 2 possible steps. So overall **O(n · (n + e))** worst case, and a
  single pass (**O(n + e)**) for the common acyclic/positive case.
- Parsing is linear in the input size; building the graph is **O(e)**.

Memory is **O(n + e)** for the graph plus the rule ASTs.

# splc Approach: `.spl` as Spec, NDD Closure as Compiler Correctness

**Date:** 2026-04-13
**Status:** Design — pre-implementation
**Author:** Wen G. Gong + Claude

---

## The Core Insight

Treat the `.spl` script as the **specification** (`S`) in the NDD closure loop:

```
S        = workflow.spl          (the spec — precise, formal, executable)
G(S)     = splc output           (Go binary, Python module, TypeScript, …)
E(G(S))  = behavior of G(S)      (observed output on test inputs)
J(S, G)  = do spl3-run and G produce the same committed value?
```

This shifts `splc` correctness from a fuzzy problem (semantic comparison of
natural-language specs) to an **exact, deterministic problem**: the reference
interpreter `spl3 run` is the oracle, and the judge `J` is a `diff`.

---

## Why This Changes Everything

In binary-search NDD closure, `S` is natural language and `J` must be an LLM
judge — the comparison is inherently fuzzy.

When `S` is a `.spl` script, the judge is exact:

```bash
# With the echo adapter, both sides are fully deterministic
output_ref=$(spl3 run workflow.spl --adapter echo --param task="...")
output_bin=$(./compiled-binary            --param task="...")
diff <(echo "$output_ref") <(echo "$output_bin")
```

No LLM needed to judge correctness. With `--adapter echo` the comparison is
byte-level. Every test is reproducible and automatable.

| Property | Natural-language NDD | `.spl`-as-spec NDD |
|---|---|---|
| Spec precision | Fuzzy (natural language) | Exact (formal semantics) |
| Judge `J` | LLM (semantic comparison) | `diff` (deterministic) |
| Oracle | None — judge is probabilistic | `spl3 run` (reference interpreter) |
| Test cases | Must be written manually | Every cookbook recipe is a free test case |
| Coverage | Hard to measure | Measurable: which SPL constructs does the binary cover? |

---

## The Development Methodology

Build `splc` one construct subset at a time, with NDD closure as the gate
after each increment:

```
Step 1:  Pick a recipe as the first closure target
         → self_refine.spl  (simplest: WORKFLOW, GENERATE, WHILE, EVALUATE, RETURN, EXCEPTION)

Step 2:  Identify the SPL construct subset it exercises
         → define the grammar subset splc v1 must handle

Step 3:  Write the splc spec (what it must produce for each construct)
         → the hand-crafted self_refine.go is the reference for the Go target

Step 4:  Build splc to emit the target for that subset

Step 5:  Run NDD closure:
         spl3 run self_refine.spl --adapter echo --param ...
         vs
         ./self_refine --param ...
         diff → must be empty

Step 6:  Pick the next recipe (more constructs); find the next gap
         → code_pipeline adds CALL, IMPORT, LOGGING, f-strings, CALL PARALLEL
```

This is the LLVM approach: one IR construct at a time, with a reference
interpreter as the oracle. It produces a rigorous, incremental build path
rather than trying to compile the full language at once.

---

## Construct Subsets by Recipe

Each cookbook recipe is a natural increment. The construct coverage grows
monotonically:

| Recipe | New SPL constructs introduced | splc increment |
|--------|------------------------------|---------------|
| `self_refine.spl` | `WORKFLOW`, `GENERATE`, `WHILE`, `EVALUATE`, `RETURN`, `EXCEPTION` | v1 — baseline |
| `code_pipeline.spl` | `CALL` (sub-workflow), `IMPORT`, `LOGGING`, f-strings, `BOOL` literals | v2 |
| Any parallel recipe | `CALL PARALLEL` | v3 |
| Any storage recipe | `STORAGE` type, `@var['key'] :=` | v4 |

`self_refine.spl` is the right first target: it is the paper's canonical DODA
proof-of-concept, it has a hand-crafted Go reference (`targets/go/self_refine.go`),
and its construct set is small enough to implement completely.

---

## The NDD Closure Test for splc

Once `splc --target go self_refine.spl` emits a Go binary:

```bash
# 1. Run the reference interpreter
ref=$(spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter echo \
    --param task="What are the benefits of meditation?" \
    --param max_iterations=2)

# 2. Run the compiled binary (same echo adapter, same params)
bin=$(./self_refine \
    --adapter echo \
    --param task="What are the benefits of meditation?" \
    --param max_iterations=2)

# 3. Judge: diff is the closure criterion
diff <(echo "$ref") <(echo "$bin") && echo "[CLOSED]" || echo "[DIVERGED]"
```

`[CLOSED]` means the compiler is correct for this recipe and this construct
subset. `[DIVERGED]` means there is a translation gap — which construct, which
line — and that is the targeted fix.

---

## The Non-Determinism Caveat

Real LLM adapters are non-deterministic: `spl3 run` and the compiled binary
calling the same Ollama endpoint will produce different token sequences even
for identical prompts.

Resolution:
- **Development-time correctness:** use `--adapter echo` — fully deterministic,
  byte-level comparable, no LLM cost.
- **Production correctness claim:** *for the same sequence of LLM responses,
  the compiled binary produces the same committed value as the interpreter.*
  Verifiable by injecting a mock adapter that returns scripted responses in
  both the interpreter and the compiled binary.

The `--adapter echo` gate is sufficient to validate all control-flow, variable
binding, branching, and output construction logic — everything except the LLM
call itself, which is the adapter's responsibility and is not `splc`'s concern.

---

## Why Build splc at All

If `spl3 run` is the oracle and already works, why compile?

The DODA answer: the `.spl` logical view must produce **portable, dependency-free
physical artifacts** for deployment targets where Python and `spl3` are not
available — Intel Mini-PCs running Ubuntu Snap, edge nodes, iOS apps via Swift.

The NDD closure framing makes this rigorous: `splc` is correct when it preserves
the semantics of the `.spl` spec on every target. The reference interpreter is
the ground truth; the compiled binary must pass the same closure test.

---

## Pre-Conditions Before Starting splc v1

Before writing a line of `splc` code, these should be true:

- [ ] End-to-end `code_pipeline` test passes (`spl3 run code_pipeline.spl ...`)
- [ ] `self_refine.spl` runs cleanly with `--adapter echo`
- [ ] `self_refine.go` (hand-crafted) passes the NDD closure diff test manually
- [ ] `splc` spec written: grammar subset for v1, Go output format, test oracle

The NDD closure check on `self_refine.go` against `spl3 run` is the validation
that the *reference* Go target is correct before the compiler needs to produce it.
If the hand-crafted Go already fails the diff test, the compiler has no valid
target to aim for.

```Gemini
✦ I have completed the task.

  Summary of Changes:
   1. Go Transpiler: Created spl3/splc/transpiler_go.py, a robust deterministic transpiler that maps SPL 3.0 AST nodes to idiomatic Go.
   2. CLI Integration: Added the --deterministic flag to spl3/splc/cli.py to enable the structural transpiler path.
   3. Documentation:
       * Updated docs/FEATURES.md: Marked splc --target go as [DONE] and updated the NDD closure test status.
       * Updated docs/ROADMAP.md: Promoted splc compiler to Stable (Go) status and updated the current implementation state.

  How to use:
   * Deterministic Mode (Transpiler):
   1     python3 spl3/splc/cli.py --spl <file.spl> --lang go --deterministic
   * LLM Mode (Agentic):
   1     python3 spl3/splc/cli.py --spl <file.spl> --lang go

  This milestone provides the exact, reproducible path required for SPL's Agentic Integrity and NDD closure goals.

```
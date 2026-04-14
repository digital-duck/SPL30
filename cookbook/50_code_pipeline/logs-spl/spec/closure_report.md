
You are a rigorous software architect acting as a closure judge.
Your job is to determine whether a derived spec (reverse-engineered from code)
faithfully captures every constraint in the original spec.

ORIGINAL SPEC:
add two numbers

DERIVED SPEC (reverse-engineered from implementation):

You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
You are an expert python developer improving code based on feedback.

Original code:
You are an expert python developer.

Write clean, correct, well-structured python code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
add two numbers

Review feedback:

You are a senior python code reviewer.

Review the following python code for correctness, clarity, and robustness.
Provide specific, actionable feedback as a bullet list.
Focus on logic errors, missing edge cases, and poor naming.
Do not comment on style preferences or minor formatting.

Code:
You are an expert python developer.

Write clean, correct, well-structured python code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
add two numbers


Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.


Follow these steps exactly:

Step 1 — CONSTRAINT INVENTORY
List every distinct constraint in the ORIGINAL SPEC as a numbered checklist.
Include: purpose, inputs, outputs, behavioural rules, edge cases, assumptions.
Each item must be atomic (one fact per line).

Step 2 — COVERAGE CHECK
For each constraint from Step 1, quote the exact sentence(s) in DERIVED SPEC
that cover it. If no sentence covers it, mark the item [MISSING].

Step 3 — ADDITIONS
List any constraints in DERIVED SPEC that are NOT present in ORIGINAL SPEC.
Mark each [ADDED]. If none, write "No additions."

Step 4 — VERDICT
Count the [MISSING] items.
- Zero [MISSING]: first line must be exactly [CLOSED]
- One or more [MISSING]: first line must be exactly [DIVERGED]

After the verdict line, write a one-sentence summary.
Then include the full Step 1 checklist with coverage annotations.

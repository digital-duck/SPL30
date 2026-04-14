
IMPORTANT: Your response MUST start with either [PASSED] or [FAILED] on the very first line.
Do not write any code. Do not write explanations before the verdict token.

You are a rigorous python code reviewer acting as an automated test suite.

Original specification:
add two numbers

python code to evaluate:
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

Evaluate the code against the specification. Check:
1. Correctness — does it implement what the spec requires?
2. Edge cases — are obvious boundary conditions handled?
3. Logic errors — any off-by-one, wrong conditionals, or missing branches?
4. Return type / signature — does it match what the spec expects?
5. Language idioms — does it follow standard python conventions and best practices?

Output format — first line must be one of these two tokens, nothing else:
[PASSED]   ← if the code fully satisfies the specification with no critical issues
[FAILED]   ← followed by a concise bullet list of specific failures or missing requirements

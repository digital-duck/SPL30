// splc-generated: deterministic typescript target
// Run: npx tsx self_refine_ts.ts --task "What are the benefits of meditation?"

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

// ── Runtime types & helpers ───────────────────────────────────────────────────

interface WorkflowResult {
  result: string;
  status: string;
  iterations: number;
}

class SPLError extends Error {
  constructor(public splType: string, message?: string) {
    super(message ?? splType);
    this.name = 'SPLError';
  }
}

/** Positional prompt formatter — replaces {param} placeholders left-to-right. */
function fmt(template: string, ...args: (string | number)[]): string {
  let i = 0;
  return template.replace(/\{[^}]+\}/g, () => String(args[i++] ?? ''));
}

async function generate(
  ollamaHost: string,
  model: string,
  prompt: string,
  numPredict = 0,
): Promise<string> {
  const body: Record<string, unknown> = { model, prompt, stream: false };
  if (numPredict > 0) body['options'] = { num_predict: numPredict };
  const res = await fetch(`${ollamaHost}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const raw = await res.text();
    throw new Error(`Ollama HTTP ${res.status}: ${raw}`);
  }
  const data = await res.json() as { response: string };
  return (data.response ?? '').trim();
}

function writeFile(path: string, content: string): void {
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content, 'utf-8');
  } catch (e) {
    console.error(`writeFile: ${e}`);
  }
}


// ── Prompt templates ────────────────────────────────────────────────────────

const draftPrompt = `
You are a professional writer. Write a comprehensive article on the topic below.
Output only the article — no preamble, no notes after.

Topic: {task}
`;

const critiquePrompt = `
You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else.

ARTICLE:
{current}

IMPROVEMENTS:
1.

`;

const refinedPrompt = `
You are a seasoned writer. Rewrite the draft below incorporating the feedback.
Stay true to the original topic: {task}
Output only the rewritten article — no preamble, no notes after.

DRAFT:
\`\`\`
{current}
\`\`\`

FEEDBACK:
\`\`\`
{feedback}
\`\`\`
`;

// ── Workflows ────────────────────────────────────────────────────────────────

// SPL: WORKFLOW critique_workflow
async function critiqueWorkflow(
  current: string,
  output_budget: number = 2000,
  critic_model: string = 'llama3.2',
  ollamaHost = 'http://localhost:11434',
): Promise<WorkflowResult> {
  let feedback: string = '';

  try {
    // SPL: GENERATE critique(current) USING MODEL @critic_model WITH OUTPUT BUDGET @output_budget TOKENS INTO feedback
    feedback = await generate(ollamaHost, critic_model, fmt(critiquePrompt, current), output_budget);
    // SPL: COMMIT feedback
    return { result: feedback, status: 'complete', iterations: 0 };
  } catch (e) {
    // SPL: EXCEPTION
    if (e instanceof SPLError) {
      switch (e.splType) {
      case 'BudgetExceeded':
        // SPL: WHEN BudgetExceeded THEN
        // SPL: COMMIT '[APPROVED]'
        return { result: '[APPROVED]', status: 'budget_limit', iterations: 0 };
        break;
      }
    }
    throw e;
  }
}

// SPL: WORKFLOW self_refine
async function selfRefine(
  task: string = 'What are the benefits of meditation?',
  output_budget: number = 2000,
  max_iterations: number = 3,
  writer_model: string = 'llama3.2',
  critic_model: string = 'llama3.2',
  log_dir: string = 'cookbook/05_self_refine/logs-spl',
  ollamaHost = 'http://localhost:11434',
): Promise<WorkflowResult> {
  let current: string = '';
  let feedback: string = '';
  let iteration: number = 0;

  try {
    // SPL: iteration := 0
    iteration = 0;
    // SPL: LOGGING f'Self-refine started | max_iterations={@max_iterations} for task:\n {@task}'
    console.log(`Self-refine started | max_iterations=${max_iterations} for task:
 ${task}`);
    // SPL: GENERATE draft(task) USING MODEL @writer_model WITH OUTPUT BUDGET @output_budget TOKENS INTO current
    current = await generate(ollamaHost, writer_model, fmt(draftPrompt, task), output_budget);
    // SPL: LOGGING 'Initial draft ready'
    console.log('Initial draft ready');
    // SPL: CALL write_file(f'{@log_dir}/draft_0.md', current)
    writeFile(`${log_dir}/draft_0.md`, current);
    // SPL: WHILE iteration < max_iterations DO
    while (iteration < max_iterations) {
      // SPL: LOGGING f'\nIteration {@iteration} | critiquing ...'
      console.log(`
Iteration ${iteration} | critiquing ...`);
      // SPL: CALL critique_workflow(current, output_budget, critic_model) INTO feedback
      const _r0 = await critiqueWorkflow(current, output_budget, critic_model, ollamaHost);
      feedback = _r0.result;
      // SPL: CALL write_file(f'{@log_dir}/feedback_{@iteration}.md', feedback)
      writeFile(`${log_dir}/feedback_${iteration}.md`, feedback);
      // SPL: EVALUATE feedback ...
      if (feedback.includes('[APPROVED]')) {
        // SPL: LOGGING f'Approved at iteration {@iteration}'
        console.log(`Approved at iteration ${iteration}`);
        // SPL: CALL write_file(f'{@log_dir}/final.md', current)
        writeFile(`${log_dir}/final.md`, current);
        // SPL: COMMIT current
        return { result: current, status: 'complete', iterations: iteration };
      } else {
        // SPL: GENERATE refined(task, current, feedback) USING MODEL @writer_model WITH OUTPUT BUDGET @output_budget TOKENS INTO current
        current = await generate(ollamaHost, writer_model, fmt(refinedPrompt, task, current, feedback), output_budget);
        // SPL: iteration := BinaryOp(left=ParamRef(name='iteration'), op='+', right=Literal(value=1, literal_type='integer'))
        iteration = (iteration + 1);
        // SPL: CALL write_file(f'{@log_dir}/draft_{@iteration}.md', current)
        writeFile(`${log_dir}/draft_${iteration}.md`, current);
        // SPL: LOGGING f'Refined | iteration={@iteration}'
        console.log(`Refined | iteration=${iteration}`);
      }
    }
    // SPL: LOGGING f'\nMax iterations reached | iterations={@iteration}'
    console.log(`
Max iterations reached | iterations=${iteration}`);
    // SPL: CALL write_file(f'{@log_dir}/final.md', current)
    writeFile(`${log_dir}/final.md`, current);
    // SPL: COMMIT current
    return { result: current, status: 'max_iterations', iterations: iteration };
  } catch (e) {
    // SPL: EXCEPTION
    if (e instanceof SPLError) {
      switch (e.splType) {
      case 'MaxIterationsReached':
        // SPL: WHEN MaxIterationsReached THEN
        // SPL: CALL write_file(f'{@log_dir}/final.md', current)
        writeFile(`${log_dir}/final.md`, current);
        // SPL: COMMIT current
        return { result: current, status: 'partial', iterations: iteration };
        break;
      case 'BudgetExceeded':
        // SPL: WHEN BudgetExceeded THEN
        // SPL: COMMIT current
        return { result: current, status: 'budget_limit', iterations: iteration };
        break;
      }
    }
    throw e;
  }
}

// ── CLI entry point ──────────────────────────────────────────────────────────

function parseArgs(): Record<string, string> {
  const args: Record<string, string> = {};
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 2) {
    if (argv[i]?.startsWith('--')) args[argv[i].slice(2)] = argv[i + 1] ?? '';
  }
  return args;
}

async function main(): Promise<void> {
  const args = parseArgs();
  const start = Date.now();
  const task = args['task'] ?? 'What are the benefits of meditation?';
  const output_budget = parseInt(args['output-budget'] ?? '2000');
  const max_iterations = parseInt(args['max-iterations'] ?? '3');
  const writer_model = args['writer-model'] ?? 'llama3.2';
  const critic_model = args['critic-model'] ?? 'llama3.2';
  const log_dir = args['log-dir'] ?? 'cookbook/05_self_refine/logs-spl';
  const ollamaHost = args['ollama-host'] ?? 'http://localhost:11434';
  const r = await selfRefine(task, output_budget, max_iterations, writer_model, critic_model, log_dir, ollamaHost);
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`\nDone | status=${r.status}  iterations=${r.iterations}  elapsed=${elapsed}s`);
  console.log('\n' + '='.repeat(60));
  console.log(r.result);
}

main().catch(console.error);

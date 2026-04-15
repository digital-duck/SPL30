"""
SPL 3.0 → TypeScript deterministic transpiler.

Generates a standalone, zero-dependency TypeScript file that:
  - Calls Ollama directly via fetch() (Node 18+ / browser compatible)
  - Uses async/await throughout
  - Uses Promise.all() for CALL PARALLEL
  - Uses try/catch with SPLError for EXCEPTION handlers
  - Uses process.argv for CLI args (no external packages)
  - Runs with: npx tsx <file>.ts --task "..."
"""

import re
from spl.ast_nodes import (
    CreateFunctionStatement, WorkflowStatement, AssignmentStatement,
    LoggingStatement, CallStatement, WhileStatement, EvaluateStatement,
    CommitStatement, Literal, ParamRef, Condition, GenerateIntoStatement,
    GenerateClause, NamedArg, ExceptionHandler,
)
from spl3.ast_nodes import (
    NoneLiteral, UnaryOp, CompoundCondition,
    CallParallelStatement, CallParallelBranch,
)

# ── Header template ───────────────────────────────────────────────────────────

_HEADER = """\
// splc-generated: deterministic typescript target
// Run: npx tsx {filename} --task "What are the benefits of meditation?"

import {{ writeFileSync, mkdirSync }} from 'node:fs';
import {{ dirname }} from 'node:path';

// ── Runtime types & helpers ───────────────────────────────────────────────────

interface WorkflowResult {{
  result: string;
  status: string;
  iterations: number;
}}

class SPLError extends Error {{
  constructor(public splType: string, message?: string) {{
    super(message ?? splType);
    this.name = 'SPLError';
  }}
}}

/** Positional prompt formatter — replaces {{param}} placeholders left-to-right. */
function fmt(template: string, ...args: (string | number)[]): string {{
  let i = 0;
  return template.replace(/\\{{[^}}]+\\}}/g, () => String(args[i++] ?? ''));
}}

async function generate(
  ollamaHost: string,
  model: string,
  prompt: string,
  numPredict = 0,
): Promise<string> {{
  const body: Record<string, unknown> = {{ model, prompt, stream: false }};
  if (numPredict > 0) body['options'] = {{ num_predict: numPredict }};
  const res = await fetch(`${{ollamaHost}}/api/generate`, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(body),
  }});
  if (!res.ok) {{
    const raw = await res.text();
    throw new Error(`Ollama HTTP ${{res.status}}: ${{raw}}`);
  }}
  const data = await res.json() as {{ response: string }};
  return (data.response ?? '').trim();
}}

function writeFile(path: string, content: string): void {{
  try {{
    mkdirSync(dirname(path), {{ recursive: true }});
    writeFileSync(path, content, 'utf-8');
  }} catch (e) {{
    console.error(`writeFile: ${{e}}`);
  }}
}}
"""

_PARSE_ARGS = """\
function parseArgs(): Record<string, string> {
  const args: Record<string, string> = {};
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 2) {
    if (argv[i]?.startsWith('--')) args[argv[i].slice(2)] = argv[i + 1] ?? '';
  }
  return args;
}
"""


class TypeScriptTranspiler:
    def __init__(self, recipe_name: str):
        self.recipe_name = recipe_name
        self.prompts: dict = {}                 # name → body
        self.workflow_inputs: dict = {}         # workflow_name → [param_name, ...]
        self.indent_level = 0
        self.current_wf_vars: dict = {}
        self._call_idx = 0                      # per-workflow tmp-var counter for CALL results

    def indent(self) -> str:
        return "  " * self.indent_level

    # ── Public entry point ────────────────────────────────────────────────────

    def transpile(self, program) -> str:
        # Pass 1: collect prompts + workflow signatures
        for stmt in program.statements:
            if isinstance(stmt, CreateFunctionStatement):
                self.prompts[stmt.name] = stmt.body
            if isinstance(stmt, WorkflowStatement):
                self.workflow_inputs[stmt.name] = [p.name.lstrip('@') for p in stmt.inputs]

        filename = f"{self.recipe_name}_ts.ts"
        lines = [_HEADER.format(filename=filename), ""]

        # Prompt constants — escape backticks for TS template literals; keep {param} intact
        lines.append("// ── Prompt templates ────────────────────────────────────────────────────────\n")
        for name, body in self.prompts.items():
            safe = body.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            lines.append(f"const {name}Prompt = `{safe}`;\n")

        lines.append("// ── Workflows ────────────────────────────────────────────────────────────────\n")

        for stmt in program.statements:
            if isinstance(stmt, WorkflowStatement):
                lines.append(self.transpile_workflow(stmt))
                lines.append("")

        # CLI entry point
        lines.append("// ── CLI entry point ──────────────────────────────────────────────────────────\n")
        lines.append(_PARSE_ARGS)

        last_wf = [s for s in program.statements if isinstance(s, WorkflowStatement)][-1]
        lines.append(self.generate_main(last_wf))
        lines.append("main().catch(console.error);\n")

        return "\n".join(lines)

    # ── Workflow ──────────────────────────────────────────────────────────────

    def transpile_workflow(self, wf: WorkflowStatement) -> str:
        self._call_idx = 0
        name = self.to_camel_case(wf.name)

        # Build parameter list with TypeScript types and defaults
        params = []
        param_names: set = set()
        for p in wf.inputs:
            ts_type = "number" if p.param_type in ("INTEGER", "INT", "FLOAT") else "string"
            pname = p.name.lstrip('@')
            param_names.add(pname)
            if p.default_value is not None:
                default = self._ts_default(p)
                params.append(f"{pname}: {ts_type} = {default}")
            else:
                params.append(f"{pname}: {ts_type}")
        params.append("ollamaHost = 'http://localhost:11434'")

        sig_params = ",\n  ".join(params)
        sig = f"// SPL: WORKFLOW {wf.name}\nasync function {name}(\n  {sig_params},\n): Promise<WorkflowResult> {{"

        self.indent_level = 1
        body_lines = []

        # Collect local variables (exclude params)
        vars_to_declare: dict = {}

        def collect_vars(stmts):
            for s in stmts:
                if isinstance(s, AssignmentStatement):
                    vars_to_declare[s.variable.lstrip('@')] = 'string'
                if isinstance(s, GenerateIntoStatement):
                    vars_to_declare[s.target_variable.lstrip('@')] = 'string'
                if isinstance(s, CallStatement) and s.target_variable:
                    tv = s.target_variable.lstrip('@')
                    if tv != 'NONE':
                        vars_to_declare[tv] = 'string'
                if isinstance(s, CallParallelStatement):
                    for b in s.branches:
                        if b.target_var:
                            vars_to_declare[b.target_var.lstrip('@')] = 'string'
                for attr in ('body', 'else_statements'):
                    sub = getattr(s, attr, None)
                    if sub:
                        collect_vars(sub)
                if hasattr(s, 'when_clauses'):
                    for c in s.when_clauses:
                        collect_vars(c.statements)

        collect_vars(wf.body)

        # Infer integer types from INPUT params
        for p in wf.inputs:
            pname = p.name.lstrip('@')
            if p.param_type in ("INTEGER", "INT") and pname in vars_to_declare:
                vars_to_declare[pname] = 'number'

        # Infer integer types from integer literal assignments
        def infer_types(stmts):
            for s in stmts:
                if isinstance(s, AssignmentStatement):
                    vn = s.variable.lstrip('@')
                    if vn in vars_to_declare:
                        if isinstance(s.expression, Literal) and isinstance(s.expression.value, int):
                            vars_to_declare[vn] = 'number'
                for attr in ('body', 'else_statements'):
                    sub = getattr(s, attr, None)
                    if sub:
                        infer_types(sub)
                if hasattr(s, 'when_clauses'):
                    for c in s.when_clauses:
                        infer_types(c.statements)

        infer_types(wf.body)
        if "iteration" in vars_to_declare:
            vars_to_declare["iteration"] = 'number'

        for pname in param_names:
            vars_to_declare.pop(pname, None)

        self.current_wf_vars = vars_to_declare

        # Emit variable declarations with zero-value defaults (needed for catch scope)
        for vname in sorted(vars_to_declare):
            ts_type = vars_to_declare[vname]
            zero = '0' if ts_type == 'number' else "''"
            body_lines.append(f"{self.indent()}let {vname}: {ts_type} = {zero};")
        if vars_to_declare:
            body_lines.append("")

        # Wrap body in try/catch when EXCEPTION handlers exist
        if wf.exception_handlers:
            body_lines.append(f"{self.indent()}try {{")
            self.indent_level += 1
            for stmt in wf.body:
                body_lines.append(self.transpile_statement(stmt))
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}} catch (e) {{")
            self.indent_level += 1
            body_lines.append(f"{self.indent()}// SPL: EXCEPTION")
            body_lines.append(f"{self.indent()}if (e instanceof SPLError) {{")
            self.indent_level += 1
            body_lines.append(f"{self.indent()}switch (e.splType) {{")
            for handler in wf.exception_handlers:
                body_lines.append(f"{self.indent()}case '{handler.exception_type}':")
                self.indent_level += 1
                body_lines.append(f"{self.indent()}// SPL: WHEN {handler.exception_type} THEN")
                for sub in handler.statements:
                    body_lines.append(self.transpile_statement(sub))
                body_lines.append(f"{self.indent()}break;")
                self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}")
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}")
            body_lines.append(f"{self.indent()}throw e;")
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}")
        else:
            for stmt in wf.body:
                body_lines.append(self.transpile_statement(stmt))

        self.indent_level = 0
        return sig + "\n" + "\n".join(body_lines) + "\n}"

    # ── Statement dispatcher ──────────────────────────────────────────────────

    def transpile_statement(self, stmt) -> str:
        ind = self.indent()

        if isinstance(stmt, AssignmentStatement):
            expr = self.transpile_expression(stmt.expression)
            return f"{ind}{self._spl_comment(stmt)}\n{ind}{stmt.variable.lstrip('@')} = {expr};"

        if isinstance(stmt, LoggingStatement):
            return f"{ind}{self._spl_comment(stmt)}\n{ind}console.log({self._ts_log_expr(stmt.expression)});"

        if isinstance(stmt, CallStatement):
            if stmt.procedure_name == "write_file":
                args = [self.transpile_expression(a) for a in stmt.arguments]
                return f"{ind}{self._spl_comment(stmt)}\n{ind}writeFile({', '.join(args)});"

            proc = self.to_camel_case(stmt.procedure_name)
            callee_params = self.workflow_inputs.get(stmt.procedure_name, [])
            resolved = self._resolve_call_args(stmt.arguments, callee_params)

            target = (stmt.target_variable or '').lstrip('@')
            spl_cmt = self._spl_comment(stmt)
            if target and target != 'NONE':
                tmp = f"_r{self._call_idx}"
                self._call_idx += 1
                return (
                    f"{ind}{spl_cmt}\n"
                    f"{ind}const {tmp} = await {proc}({', '.join(resolved)}, ollamaHost);\n"
                    f"{ind}{target} = {tmp}.result;"
                )
            else:
                return f"{ind}{spl_cmt}\n{ind}await {proc}({', '.join(resolved)}, ollamaHost);"

        if isinstance(stmt, GenerateIntoStatement):
            clause = stmt.generate_clause
            model = self._ts_model_expr(clause.model)
            args = [self.transpile_expression(a) for a in clause.arguments]
            budget = self._ts_budget_expr(clause)
            prompt_call = f"fmt({clause.function_name}Prompt, {', '.join(args)})" if args else f"{clause.function_name}Prompt"
            target = stmt.target_variable.lstrip('@')
            generate_call = f"await generate(ollamaHost, {model}, {prompt_call}, {budget})"
            return (
                f"{ind}{self._spl_comment(stmt)}\n"
                f"{ind}{target} = {generate_call};"
            )

        if isinstance(stmt, WhileStatement):
            cond = self.transpile_expression(stmt.condition)
            res = [f"{ind}{self._spl_comment(stmt)}", f"{ind}while ({cond}) {{"]
            self.indent_level += 1
            for sub in stmt.body:
                res.append(self.transpile_statement(sub))
            self.indent_level -= 1
            res.append(f"{ind}}}")
            return "\n".join(res)

        if isinstance(stmt, EvaluateStatement):
            expr = self.transpile_expression(stmt.expression)
            res = [f"{ind}{self._spl_comment(stmt)}"]
            first = True
            for clause in stmt.when_clauses:
                keyword = "if" if first else "} else if"
                first = False
                cond_obj = clause.condition
                if hasattr(cond_obj, 'semantic_value'):
                    sem = cond_obj.semantic_value
                    if sem.startswith("contains:"):
                        match_str = sem[len("contains:"):]
                        res.append(f"{ind}{keyword} ({expr}.includes('{match_str}')) {{")
                    else:
                        res.append(f"{ind}{keyword} ({expr} === '{sem}') {{")
                else:
                    cond = self.transpile_expression(cond_obj)
                    res.append(f"{ind}{keyword} ({cond}) {{")
                self.indent_level += 1
                for sub in clause.statements:
                    res.append(self.transpile_statement(sub))
                self.indent_level -= 1

            if stmt.else_statements:
                res.append(f"{ind}}} else {{")
                self.indent_level += 1
                for sub in stmt.else_statements:
                    res.append(self.transpile_statement(sub))
                self.indent_level -= 1
            res.append(f"{ind}}}")
            return "\n".join(res)

        if isinstance(stmt, CommitStatement):
            val = self.transpile_expression(stmt.expression)
            status_val = "'complete'"
            iters_val = "iteration" if "iteration" in self.current_wf_vars else "0"
            if hasattr(stmt, 'options') and stmt.options:
                if 'status' in stmt.options:
                    status_val = self.transpile_expression(stmt.options['status'])
                if 'iterations' in stmt.options:
                    iters_val = self.transpile_expression(stmt.options['iterations'])
            return (
                f"{ind}{self._spl_comment(stmt)}\n"
                f"{ind}return {{ result: {val}, status: {status_val}, iterations: {iters_val} }};"
            )

        if isinstance(stmt, CallParallelStatement):
            return self._transpile_call_parallel(stmt)

        return f"{ind}// TODO: {type(stmt).__name__}"

    def _transpile_call_parallel(self, stmt: CallParallelStatement) -> str:
        """CALL PARALLEL → Promise.all([...])"""
        ind = self.indent()
        n = len(stmt.branches)
        tmp_vars = [f"_rP{i+1}" for i in range(n)]

        lines = [f"{ind}{self._spl_comment(stmt)}"]

        # Build Promise.all call
        calls = []
        for branch in stmt.branches:
            proc = self.to_camel_case(branch.workflow_name)
            callee_params = self.workflow_inputs.get(branch.workflow_name, [])
            resolved = self._resolve_call_args(branch.arguments, callee_params)
            calls.append(f"{proc}({', '.join(resolved)}, ollamaHost)")

        if n == 1:
            lines.append(f"{ind}const [{tmp_vars[0]}] = await Promise.all([{calls[0]}]);")
        else:
            lines.append(f"{ind}const [{', '.join(tmp_vars)}] = await Promise.all([")
            for call in calls:
                lines.append(f"{ind}  {call},")
            lines.append(f"{ind}]);")

        # Unpack results
        for i, branch in enumerate(stmt.branches):
            if branch.target_var:
                target = branch.target_var.lstrip('@')
                lines.append(f"{ind}{target} = {tmp_vars[i]}.result;")

        return "\n".join(lines)

    # ── Expression transpiler ─────────────────────────────────────────────────

    def transpile_expression(self, expr) -> str:
        if isinstance(expr, str):
            return expr.lstrip('@') if expr.startswith('@') else f"'{expr}'"
        if isinstance(expr, Literal):
            if isinstance(expr.value, str):
                return f"'{expr.value}'"
            if isinstance(expr.value, bool):
                return 'true' if expr.value else 'false'
            return str(expr.value)
        if isinstance(expr, ParamRef):
            return expr.name.lstrip('@')
        if isinstance(expr, NoneLiteral):
            return "''"
        if isinstance(expr, NamedArg):
            return self.transpile_expression(expr.value)
        if hasattr(expr, 'template'):   # FStringLiteral — convert to TS template literal
            ts_str = re.sub(r'\{@(\w+)\}', lambda m: '${' + m.group(1) + '}', expr.template)
            ts_str = ts_str.replace('`', '\\`')
            return f"`{ts_str}`"
        if hasattr(expr, 'left') and hasattr(expr, 'right') and hasattr(expr, 'op'):  # BinaryOp
            return f"({self.transpile_expression(expr.left)} {expr.op} {self.transpile_expression(expr.right)})"
        if isinstance(expr, Condition):
            return f"{self.transpile_expression(expr.left)} {expr.operator} {self.transpile_expression(expr.right)}"
        if isinstance(expr, UnaryOp):
            return f"!({self.transpile_expression(expr.operand)})"
        if isinstance(expr, CompoundCondition):
            op = "&&" if expr.operator == 'AND' else "||"
            return f"({self.transpile_expression(expr.left)} {op} {self.transpile_expression(expr.right)})"
        return f"/* {type(expr).__name__} */"

    # ── TypeScript-specific helpers ───────────────────────────────────────────

    def _ts_log_expr(self, expr) -> str:
        """Convert a LOGGING expression to a TS console.log argument."""
        if hasattr(expr, 'template'):   # FStringLiteral
            ts_str = re.sub(r'\{@(\w+)\}', lambda m: '${' + m.group(1) + '}', expr.template)
            ts_str = ts_str.replace('`', '\\`')
            return f"`{ts_str}`"
        if hasattr(expr, 'value'):      # Literal string
            escaped = str(expr.value).replace("'", "\\'")
            return f"'{escaped}'"
        return self.transpile_expression(expr)

    def _ts_model_expr(self, model_expr) -> str:
        """Resolve USING MODEL expression to a TS expression."""
        if model_expr is None:
            return "'llama3.2'"
        if isinstance(model_expr, str):
            return model_expr.lstrip('@') if model_expr.startswith('@') else f"'{model_expr}'"
        return self.transpile_expression(model_expr)

    def _ts_budget_expr(self, clause) -> str:
        """Resolve WITH OUTPUT BUDGET expression to a TS number expression."""
        budget = getattr(clause, 'output_budget', None)
        if budget is None:
            return "0"
        if isinstance(budget, int):
            return str(budget)
        if isinstance(budget, Literal):
            return str(budget.value)
        if isinstance(budget, ParamRef):
            return budget.name.lstrip('@')
        if isinstance(budget, str) and budget.startswith('@'):
            return budget.lstrip('@')
        return self.transpile_expression(budget)

    def _ts_default(self, p) -> str:
        """Convert an INPUT parameter default to a TypeScript literal."""
        if p.default_value is None:
            return "''" if p.param_type not in ("INTEGER", "INT", "FLOAT") else "0"
        if isinstance(p.default_value, Literal):
            v = p.default_value.value
            if isinstance(v, str):
                return f"'{v}'"
            if isinstance(v, bool):
                return 'true' if v else 'false'
            return str(v)
        return "''"

    # ── Issue 4: named-arg resolution ────────────────────────────────────────

    def _resolve_call_args(self, arguments: list, callee_params: list) -> list:
        has_named = any(isinstance(a, NamedArg) for a in arguments)
        if not has_named or not callee_params:
            return [self.transpile_expression(a) for a in arguments]

        result = {p: None for p in callee_params}
        named_keys: set = set()
        for arg in arguments:
            if isinstance(arg, NamedArg):
                result[arg.name] = self.transpile_expression(arg.value)
                named_keys.add(arg.name)

        pos_idx = 0
        for arg in arguments:
            if isinstance(arg, NamedArg):
                continue
            while pos_idx < len(callee_params) and callee_params[pos_idx] in named_keys:
                pos_idx += 1
            if pos_idx < len(callee_params):
                result[callee_params[pos_idx]] = self.transpile_expression(arg)
                pos_idx += 1

        return [result[p] if result[p] is not None else "''" for p in callee_params]

    # ── SPL traceability comments ─────────────────────────────────────────────

    def _spl_comment(self, stmt) -> str:
        if isinstance(stmt, GenerateIntoStatement):
            c = stmt.generate_clause
            args = ", ".join(self._spl_expr(a) for a in c.arguments)
            model_part = f" USING MODEL {self._spl_expr(c.model)}" if getattr(c, 'model', None) else ""
            budget = getattr(c, 'output_budget', None)
            budget_part = f" WITH OUTPUT BUDGET {budget} TOKENS" if budget else ""
            return f"// SPL: GENERATE {c.function_name}({args}){model_part}{budget_part} INTO {stmt.target_variable}"
        if isinstance(stmt, AssignmentStatement):
            return f"// SPL: {stmt.variable} := {self._spl_expr(stmt.expression)}"
        if isinstance(stmt, LoggingStatement):
            return f"// SPL: LOGGING {self._spl_expr(stmt.expression)}"
        if isinstance(stmt, CallStatement):
            args = ", ".join(self._spl_expr(a) for a in stmt.arguments)
            into = f" INTO {stmt.target_variable}" if stmt.target_variable else ""
            return f"// SPL: CALL {stmt.procedure_name}({args}){into}"
        if isinstance(stmt, CommitStatement):
            return f"// SPL: COMMIT {self._spl_expr(stmt.expression)}"
        if isinstance(stmt, EvaluateStatement):
            return f"// SPL: EVALUATE {self._spl_expr(stmt.expression)} ..."
        if isinstance(stmt, WhileStatement):
            return f"// SPL: WHILE {self._spl_expr(stmt.condition)} DO"
        if isinstance(stmt, CallParallelStatement):
            parts = [
                f"{b.workflow_name}({', '.join(self._spl_expr(a) for a in b.arguments)}) INTO {b.target_var}"
                for b in stmt.branches
            ]
            return f"// SPL: CALL PARALLEL {', '.join(parts)} END"
        return f"// SPL: {type(stmt).__name__}"

    def _spl_expr(self, expr) -> str:
        if expr is None:
            return ""
        if isinstance(expr, str):
            return expr
        if isinstance(expr, Literal):
            return f"'{expr.value}'" if isinstance(expr.value, str) else str(expr.value)
        if isinstance(expr, ParamRef):
            return expr.name
        if isinstance(expr, NoneLiteral):
            return "NONE"
        if isinstance(expr, NamedArg):
            return f"{expr.name}={self._spl_expr(expr.value)}"
        if hasattr(expr, 'template'):
            return "f'" + expr.template.replace('\n', '\\n') + "'"
        if isinstance(expr, Condition):
            return f"{self._spl_expr(expr.left)} {expr.operator} {self._spl_expr(expr.right)}"
        if isinstance(expr, UnaryOp):
            return f"NOT {self._spl_expr(expr.operand)}"
        if isinstance(expr, CompoundCondition):
            return f"{self._spl_expr(expr.left)} {expr.operator} {self._spl_expr(expr.right)}"
        return str(expr)

    # ── Shared helpers ────────────────────────────────────────────────────────

    def to_camel_case(self, snake_str: str) -> str:
        parts = snake_str.split('_')
        return parts[0] + ''.join(x.title() for x in parts[1:])

    # ── main() / CLI entry point ──────────────────────────────────────────────

    def generate_main(self, wf: WorkflowStatement) -> str:
        func_name = self.to_camel_case(wf.name)
        arg_lines = []
        call_args = []

        for p in wf.inputs:
            name_ts = p.name.lstrip('@')
            flag = name_ts.replace('_', '-')
            default = self._ts_default(p)
            is_num = p.param_type in ("INTEGER", "INT", "FLOAT")

            if is_num:
                arg_lines.append(f"  const {name_ts} = parseInt(args['{flag}'] ?? '{default.strip(chr(39))}');")
            else:
                arg_lines.append(f"  const {name_ts} = args['{flag}'] ?? {default};")
            call_args.append(name_ts)

        arg_lines.append("  const ollamaHost = args['ollama-host'] ?? 'http://localhost:11434';")
        call_args.append("ollamaHost")

        args_str = "\n".join(arg_lines)
        call_str = ", ".join(call_args)

        return f"""async function main(): Promise<void> {{
  const args = parseArgs();
  const start = Date.now();
{args_str}
  const r = await {func_name}({call_str});
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`\\nDone | status=${{r.status}}  iterations=${{r.iterations}}  elapsed=${{elapsed}}s`);
  console.log('\\n' + '='.repeat(60));
  console.log(r.result);
}}
"""

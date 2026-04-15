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


class GoTranspiler:
    def __init__(self, recipe_name: str):
        self.recipe_name = recipe_name
        self.prompts = {}
        self.workflow_inputs = {}   # workflow_name → [param_name, ...]  (Issue 4)
        self.indent_level = 0
        self.current_wf_vars = {}
        self._in_exception_handler = False   # Issue 3: COMMIT → named-return assignment inside defer

    def indent(self):
        return "  " * self.indent_level

    # ── Public entry point ────────────────────────────────────────────────────

    def transpile(self, program) -> str:
        # ── Pass 1: collect prompts + workflow signatures ─────────────────────
        for stmt in program.statements:
            if isinstance(stmt, CreateFunctionStatement):
                self.prompts[stmt.name] = stmt.body
            if isinstance(stmt, WorkflowStatement):
                self.workflow_inputs[stmt.name] = [p.name.lstrip('@') for p in stmt.inputs]

        # Detect CALL PARALLEL to conditionally add "sync" import  (Issue 2)
        use_sync = any(
            self._contains_parallel(s.body)
            for s in program.statements
            if isinstance(s, WorkflowStatement)
        )

        # ── Pass 2: emit Go source ─────────────────────────────────────────────
        imports = [
            '  "bytes"',
            '  "encoding/json"',
            '  "flag"',
            '  "fmt"',
            '  "io"',
            '  "log"',
            '  "net/http"',
            '  "os"',
            '  "path/filepath"',
            '  "strings"',
            '  "time"',
        ]
        if use_sync:
            imports.append('  "sync"')

        lines = [
            "// splc-generated: deterministic go target",
            "package main",
            "",
            "import (",
        ] + imports + [
            ")",
            "",
        ]

        # Prompts — Issue 5 fix: escape backticks BEFORE substituting %s
        for name, body in self.prompts.items():
            body_fmt = body.replace("`", "` + \"`\" + `")   # 1. escape backticks
            body_fmt = re.sub(r'\{(\w+)\}', '%s', body_fmt)  # 2. {param} → %s
            lines.append(f"const {name}Prompt = `{body_fmt}`")
            lines.append("")

        # Ollama client — Issue 6: read error body on non-200
        lines.extend([
            "type generateRequest struct {",
            '  Model  string `json:"model"`',
            '  Prompt string `json:"prompt"`',
            '  Stream bool   `json:"stream"`',
            "}",
            "",
            "type generateResponse struct {",
            '  Response string `json:"response"`',
            "}",
            "",
            "func generate(ollamaHost, model, prompt string) (string, error) {",
            "  body, err := json.Marshal(generateRequest{",
            "    Model:  model,",
            "    Prompt: prompt,",
            "    Stream: false,",
            "  })",
            "  if err != nil { return \"\", err }",
            '  resp, err := http.Post(ollamaHost+"/api/generate", "application/json", bytes.NewReader(body))',
            "  if err != nil { return \"\", err }",
            "  defer resp.Body.Close()",
            "  if resp.StatusCode != http.StatusOK {",
            "    raw, _ := io.ReadAll(resp.Body)",
            '    return "", fmt.Errorf("ollama HTTP %d: %s", resp.StatusCode, raw)',
            "  }",
            "  var out generateResponse",
            "  if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return \"\", err }",
            "  return strings.TrimSpace(out.Response), nil",
            "}",
            "",
        ])

        # writeFile helper — Issue 7: propagate errors via log.Printf
        lines.extend([
            "func writeFile(path, content string) {",
            "  if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {",
            '    log.Printf("writeFile: mkdir %s: %v", path, err)',
            "    return",
            "  }",
            "  if err := os.WriteFile(path, []byte(content), 0644); err != nil {",
            '    log.Printf("writeFile: %v", err)',
            "  }",
            "}",
            "",
        ])

        # Workflows
        for stmt in program.statements:
            if isinstance(stmt, WorkflowStatement):
                lines.append(self.transpile_workflow(stmt))
                lines.append("")

        # main() — uses the last workflow as entry point
        last_wf = [s for s in program.statements if isinstance(s, WorkflowStatement)][-1]
        lines.append(self.generate_main(last_wf))

        return "\n".join(lines)

    # ── Workflow ──────────────────────────────────────────────────────────────

    def transpile_workflow(self, wf: WorkflowStatement) -> str:
        name = self.to_camel_case(wf.name)
        params = []
        param_names = set()
        for p in wf.inputs:
            ptype = "int" if p.param_type in ("INTEGER", "INT") else "string"
            pname = p.name.lstrip('@')
            params.append(f"{pname} {ptype}")
            param_names.add(pname)
        params.append("ollamaHost string")

        sig = f"func {name}({', '.join(params)}) (result string, status string, iterations int, err error) {{"
        self.indent_level = 1
        body_lines = []

        # Collect all local variables needing declaration
        vars_to_declare = {}

        def collect_vars(stmts):
            for s in stmts:
                if isinstance(s, AssignmentStatement):
                    vars_to_declare[s.variable.lstrip('@')] = "string"
                if isinstance(s, GenerateIntoStatement):
                    vars_to_declare[s.target_variable.lstrip('@')] = "string"
                if isinstance(s, CallStatement) and s.target_variable:
                    vars_to_declare[s.target_variable.lstrip('@')] = "string"
                if isinstance(s, CallParallelStatement):
                    for b in s.branches:
                        if b.target_var:
                            vars_to_declare[b.target_var.lstrip('@')] = "string"
                if hasattr(s, 'body'):
                    collect_vars(s.body)
                if hasattr(s, 'when_clauses'):
                    for c in s.when_clauses:
                        collect_vars(c.statements)
                if hasattr(s, 'else_statements'):
                    collect_vars(s.else_statements or [])

        collect_vars(wf.body)

        # Issue 9: infer int type from INTEGER input params
        for p in wf.inputs:
            pname = p.name.lstrip('@')
            if p.param_type in ("INTEGER", "INT") and pname in vars_to_declare:
                vars_to_declare[pname] = "int"

        # Issue 9: infer int type from integer literal assignments
        def infer_types(stmts):
            for s in stmts:
                if isinstance(s, AssignmentStatement):
                    vname = s.variable.lstrip('@')
                    if vname in vars_to_declare:
                        if isinstance(s.expression, Literal) and isinstance(s.expression.value, int):
                            vars_to_declare[vname] = "int"
                if hasattr(s, 'body'):
                    infer_types(s.body)
                if hasattr(s, 'when_clauses'):
                    for c in s.when_clauses:
                        infer_types(c.statements)
                if hasattr(s, 'else_statements'):
                    infer_types(s.else_statements or [])

        infer_types(wf.body)
        # Legacy name-based fallback kept for backward compat
        if "iteration" in vars_to_declare:
            vars_to_declare["iteration"] = "int"

        # Remove params — they're already in the function signature
        for pname in param_names:
            vars_to_declare.pop(pname, None)

        self.current_wf_vars = vars_to_declare

        for vname in sorted(vars_to_declare):
            body_lines.append(f"{self.indent()}var {vname} {vars_to_declare[vname]}")

        # Issue 3: EXCEPTION handlers → defer/recover block before body
        if wf.exception_handlers:
            body_lines.append("")
            body_lines.append(f"{self.indent()}// SPL: EXCEPTION")
            body_lines.append(f"{self.indent()}defer func() {{")
            self.indent_level += 1
            body_lines.append(f"{self.indent()}if r := recover(); r != nil {{")
            self.indent_level += 1
            body_lines.append(f"{self.indent()}type splErr interface {{ SPLType() string }}")
            body_lines.append(f"{self.indent()}if e, ok := r.(splErr); ok {{")
            self.indent_level += 1
            body_lines.append(f"{self.indent()}switch e.SPLType() {{")
            self._in_exception_handler = True
            for handler in wf.exception_handlers:
                body_lines.append(f"{self.indent()}case \"{handler.exception_type}\":")
                self.indent_level += 1
                body_lines.append(f"{self.indent()}// SPL: WHEN {handler.exception_type} THEN")
                for sub in handler.statements:
                    body_lines.append(self.transpile_statement(sub))
                self.indent_level -= 1
            self._in_exception_handler = False
            body_lines.append(f"{self.indent()}}}")
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}")
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}")
            self.indent_level -= 1
            body_lines.append(f"{self.indent()}}}()")
            body_lines.append("")

        for stmt in wf.body:
            body_lines.append(self.transpile_statement(stmt))

        self.indent_level = 0
        return sig + "\n" + "\n".join(body_lines) + "\n}"

    # ── Statement dispatcher ──────────────────────────────────────────────────

    def transpile_statement(self, stmt) -> str:
        ind = self.indent()

        if isinstance(stmt, AssignmentStatement):
            # Issue 1: SPL traceability comment
            expr = self.transpile_expression(stmt.expression)
            return f"{ind}{self._spl_comment(stmt)}\n{ind}{stmt.variable.lstrip('@')} = {expr}"

        if isinstance(stmt, LoggingStatement):
            expr = stmt.expression
            if hasattr(expr, 'template'):   # FStringLiteral
                msg_fmt = re.sub(r'\{@(\w+)\}', '%v', expr.template).replace("\n", "\\n").replace('"', '\\"')
                vars_match = re.findall(r'\{@(\w+)\}', expr.template)
                vars_str = ", " + ", ".join(vars_match) if vars_match else ""
                return f'{ind}{self._spl_comment(stmt)}\n{ind}log.Printf("{msg_fmt}"{vars_str})'
            elif hasattr(expr, 'value'):    # Literal
                msg_val = str(expr.value).replace("\n", "\\n").replace('"', '\\"')
                return f'{ind}{self._spl_comment(stmt)}\n{ind}log.Printf("{msg_val}")'
            return f'{ind}{self._spl_comment(stmt)}\n{ind}log.Printf("%v", {self.transpile_expression(expr)})'

        if isinstance(stmt, CallStatement):
            if stmt.procedure_name == "write_file":
                args = [self.transpile_expression(a) for a in stmt.arguments]
                return f"{ind}{self._spl_comment(stmt)}\n{ind}writeFile({', '.join(args)})"

            proc = self.to_camel_case(stmt.procedure_name)
            target = stmt.target_variable.lstrip('@') if stmt.target_variable else "_"
            # Issue 4: resolve named args by callee parameter list
            callee_params = self.workflow_inputs.get(stmt.procedure_name, [])
            resolved = self._resolve_call_args(stmt.arguments, callee_params)
            return (
                f"{ind}{self._spl_comment(stmt)}\n"
                f"{ind}{target}, _, _, err = {proc}({', '.join(resolved)}, ollamaHost)\n"
                f"{ind}if err != nil {{ return \"\", \"error\", 0, err }}"
            )

        if isinstance(stmt, GenerateIntoStatement):
            clause = stmt.generate_clause
            model_expr = clause.model
            if isinstance(model_expr, str):
                model = model_expr.lstrip("@") if model_expr.startswith("@") else f'"{model_expr}"'
            else:
                model = self.transpile_expression(model_expr) if model_expr else '"llama3.2"'

            args = [self.transpile_expression(a) for a in clause.arguments]
            prompt_call = f"fmt.Sprintf({clause.function_name}Prompt, {', '.join(args)})"
            target = stmt.target_variable.lstrip('@')
            return (
                f"{ind}{self._spl_comment(stmt)}\n"
                f"{ind}{target}, err = generate(ollamaHost, {model}, {prompt_call})\n"
                f"{ind}if err != nil {{ return \"\", \"error\", 0, err }}"
            )

        if isinstance(stmt, WhileStatement):
            cond = self.transpile_expression(stmt.condition)
            res = [f"{ind}{self._spl_comment(stmt)}", f"{ind}for {cond} {{"]
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
                        res.append(f"{ind}{keyword} strings.Contains({expr}, \"{match_str}\") {{")
                    else:
                        res.append(f"{ind}{keyword} {expr} == \"{sem}\" {{")
                else:
                    cond = self.transpile_expression(cond_obj)
                    res.append(f"{ind}{keyword} {expr} == {cond} {{")
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
            status_val = "\"complete\""
            iters_val = "iteration" if "iteration" in self.current_wf_vars else "0"
            if hasattr(stmt, 'options') and stmt.options:
                if 'status' in stmt.options:
                    status_val = self.transpile_expression(stmt.options['status'])
                if 'iterations' in stmt.options:
                    iters_val = self.transpile_expression(stmt.options['iterations'])
            if self._in_exception_handler:
                # Inside defer func() — assign to named returns, cannot use return statement
                return (
                    f"{ind}{self._spl_comment(stmt)}\n"
                    f"{ind}result = {val}\n"
                    f"{ind}status = {status_val}\n"
                    f"{ind}iterations = {iters_val}"
                )
            return f"{ind}{self._spl_comment(stmt)}\n{ind}return {val}, {status_val}, {iters_val}, nil"

        # Issue 2: CALL PARALLEL → goroutines + sync.WaitGroup
        if isinstance(stmt, CallParallelStatement):
            return self._transpile_call_parallel(stmt)

        return f"{ind}// TODO: {type(stmt).__name__}"

    def _transpile_call_parallel(self, stmt: CallParallelStatement) -> str:
        """Issue 2: Emit goroutines + sync.WaitGroup for CALL PARALLEL."""
        ind = self.indent()
        n = len(stmt.branches)
        err_vars = [f"pErr{i+1}" for i in range(n)]

        lines = [f"{ind}{self._spl_comment(stmt)}"]
        lines.append(f"{ind}var {', '.join(err_vars)} error")
        lines.append(f"{ind}var wg sync.WaitGroup")
        lines.append(f"{ind}wg.Add({n})")

        for i, branch in enumerate(stmt.branches):
            proc = self.to_camel_case(branch.workflow_name)
            target = branch.target_var.lstrip('@') if branch.target_var else "_"
            callee_params = self.workflow_inputs.get(branch.workflow_name, [])
            resolved = self._resolve_call_args(branch.arguments, callee_params)
            ev = err_vars[i]
            lines.append(
                f"{ind}go func() {{ defer wg.Done(); "
                f"{target}, _, _, {ev} = {proc}({', '.join(resolved)}, ollamaHost) }}()"
            )

        lines.append(f"{ind}wg.Wait()")
        for ev in err_vars:
            lines.append(f"{ind}if {ev} != nil {{ return \"\", \"error\", 0, {ev} }}")

        return "\n".join(lines)

    # ── Expression transpiler ─────────────────────────────────────────────────

    def transpile_expression(self, expr) -> str:
        if isinstance(expr, str):
            return expr.lstrip("@") if expr.startswith("@") else f'"{expr}"'
        if isinstance(expr, Literal):
            return f'"{expr.value}"' if isinstance(expr.value, str) else str(expr.value).lower()
        if isinstance(expr, ParamRef):
            return expr.name.lstrip('@')
        if isinstance(expr, NoneLiteral):
            return '""'
        if isinstance(expr, NamedArg):
            # Fallback: named args are resolved in _resolve_call_args; here just emit value
            return self.transpile_expression(expr.value)
        if hasattr(expr, 'template'):   # FStringLiteral
            msg_fmt = re.sub(r'\{@(\w+)\}', '%v', expr.template)
            vars_match = re.findall(r'\{@(\w+)\}', expr.template)
            if vars_match:
                return f'fmt.Sprintf("{msg_fmt}", {", ".join(vars_match)})'
            return f'"{expr.template}"'
        if hasattr(expr, 'left') and hasattr(expr, 'right') and hasattr(expr, 'op'):   # BinaryOp
            return f"({self.transpile_expression(expr.left)} {expr.op} {self.transpile_expression(expr.right)})"
        if isinstance(expr, Condition):
            return f"{self.transpile_expression(expr.left)} {expr.operator} {self.transpile_expression(expr.right)}"
        if isinstance(expr, UnaryOp):
            return f"!({self.transpile_expression(expr.operand)})"
        if isinstance(expr, CompoundCondition):
            op = "&&" if expr.operator == 'AND' else "||"
            return f"({self.transpile_expression(expr.left)} {op} {self.transpile_expression(expr.right)})"
        return f"/* {type(expr).__name__} {str(expr)} */"

    # ── Issue 1: SPL traceability comments ───────────────────────────────────

    def _spl_comment(self, stmt) -> str:
        """Reconstruct the original SPL statement as a // SPL: traceability comment."""
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
        """Convert an expression back to SPL-like source for traceability comments."""
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

    # ── Issue 4: named-arg resolution ────────────────────────────────────────

    def _resolve_call_args(self, arguments: list, callee_params: list) -> list:
        """Resolve a mix of positional and named args to an ordered Go argument list.

        Named args are mapped by name; positional args fill the remaining slots
        left-to-right. Falls back to pure-positional when callee signature unknown.
        """
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
            # Skip already-named slots
            while pos_idx < len(callee_params) and callee_params[pos_idx] in named_keys:
                pos_idx += 1
            if pos_idx < len(callee_params):
                result[callee_params[pos_idx]] = self.transpile_expression(arg)
                pos_idx += 1

        return [result[p] if result[p] is not None else '""' for p in callee_params]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _contains_parallel(self, stmts) -> bool:
        for s in stmts:
            if isinstance(s, CallParallelStatement):
                return True
            for attr in ('body', 'else_statements'):
                sub = getattr(s, attr, None)
                if sub and self._contains_parallel(sub):
                    return True
            if hasattr(s, 'when_clauses'):
                for c in s.when_clauses:
                    if self._contains_parallel(c.statements):
                        return True
        return False

    def to_camel_case(self, snake_str: str) -> str:
        parts = snake_str.split('_')
        return parts[0] + ''.join(x.title() for x in parts[1:])

    # ── main() generator ──────────────────────────────────────────────────────

    def generate_main(self, wf: WorkflowStatement) -> str:
        func_name = self.to_camel_case(wf.name)
        flags = []
        call_args = []

        for p in wf.inputs:
            name_go = p.name.lstrip('@')
            flag_name = name_go.replace('_', '-')
            # Issue 10: default = '""' not 'string' when no default provided
            default = '""'
            if isinstance(p.default_value, Literal):
                default = self.transpile_expression(p.default_value)

            if p.param_type in ("INTEGER", "INT"):
                int_default = default if default != '""' else "0"
                flags.append(f'  {name_go} := flag.Int("{flag_name}", {int_default}, "{name_go}")')
                call_args.append(f"*{name_go}")
            else:
                flags.append(f'  {name_go} := flag.String("{flag_name}", {default}, "{name_go}")')
                call_args.append(f"*{name_go}")

        # --ollama-host flag (matches targets-ref/go convention)
        flags.append('  ollamaHost := flag.String("ollama-host", "http://localhost:11434", "Ollama server URL")')
        call_args.append("*ollamaHost")

        flags_str = "\n".join(flags)
        return f"""func main() {{
{flags_str}
  flag.Parse()
  start := time.Now()
  res, status, iters, err := {func_name}({', '.join(call_args)})
  if err != nil {{ log.Fatal(err) }}
  log.Printf("Done | status=%s  iterations=%d  elapsed=%.1fs", status, iters, time.Since(start).Seconds())
  fmt.Printf("\\n%s\\n%s\\n", strings.Repeat("=", 60), res)
}}
"""

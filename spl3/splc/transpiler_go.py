import sys
import re
from pathlib import Path
from spl.ast_nodes import CreateFunctionStatement, WorkflowStatement, AssignmentStatement, LoggingStatement, CallStatement, WhileStatement, EvaluateStatement, CommitStatement, Literal, ParamRef, Condition, GenerateIntoStatement, GenerateClause
from spl3.ast_nodes import NoneLiteral, UnaryOp, CompoundCondition

class GoTranspiler:
    def __init__(self, recipe_name: str):
        self.recipe_name = recipe_name
        self.prompts = {}
        self.indent_level = 0

    def indent(self):
        return "  " * self.indent_level

    def transpile(self, program):
        # First pass: collect functions (prompts)
        for stmt in program.statements:
            if isinstance(stmt, CreateFunctionStatement):
                self.prompts[stmt.name] = stmt.body

        # Second pass: generate code
        lines = [
            "// splc-generated: deterministic go target",
            f"package main",
            "",
            'import (',
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
            ')',
            "",
        ]

        # Prompts
        for name, body in self.prompts.items():
            # Convert {param} to %s for fmt.Sprintf
            body_fmt = re.sub(r'\{(\w+)\}', '%s', body)
            # Escape backticks for Go raw strings
            body_fmt = body_fmt.replace("`", "` + \"`\" + `")
            lines.append(f"const {name}Prompt = `{body_fmt}`")
            lines.append("")

        # Ollama client & helpers
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
            "  if resp.StatusCode != http.StatusOK { return \"\", fmt.Errorf(\"ollama error: %d\", resp.StatusCode) }",
            "  var out generateResponse",
            "  if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return \"\", err }",
            "  return strings.TrimSpace(out.Response), nil",
            "}",
            "",
            "func writeFile(path, content string) {",
            "  os.MkdirAll(filepath.Dir(path), 0755)",
            "  os.WriteFile(path, []byte(content), 0644)",
            "}",
            "",
        ])

        # Workflows
        for stmt in program.statements:
            if isinstance(stmt, WorkflowStatement):
                lines.append(self.transpile_workflow(stmt))
                lines.append("")

        # Main (for the last workflow)
        last_workflow = [s for s in program.statements if isinstance(s, WorkflowStatement)][-1]
        lines.append(self.generate_main(last_workflow))

        return "\n".join(lines)

    def transpile_workflow(self, wf: WorkflowStatement):
        name = self.to_camel_case(wf.name)
        params = []
        for p in wf.inputs:
            ptype = "string"
            if p.param_type in ("INTEGER", "INT"): ptype = "int"
            params.append(f"{p.name.lstrip('@')} {ptype}")
        
        # Add common params
        params.extend(["ollamaHost string"])
        
        res_line = f"func {name}({', '.join(params)}) (result string, status string, iterations int, err error) {{"
        self.indent_level = 1
        body_lines = []
        for stmt in wf.body:
            body_lines.append(self.transpile_statement(stmt))
        self.indent_level = 0
        return res_line + "\n" + "\n".join(body_lines) + "\n}"

    def transpile_statement(self, stmt):
        ind = self.indent()
        if isinstance(stmt, AssignmentStatement):
            expr = self.transpile_expression(stmt.expression)
            return f"{ind}{stmt.variable.lstrip('@')} = {expr}"
        
        if isinstance(stmt, LoggingStatement):
            expr = stmt.expression
            if hasattr(expr, 'template'): # FStringLiteral
                msg = expr.template
                msg_fmt = re.sub(r'\{@(\w+)\}', '%v', msg)
                vars_match = re.findall(r'\{@(\w+)\}', msg)
                vars_str = ", " + ", ".join(vars_match) if vars_match else ""
                return f'{ind}log.Printf("{msg_fmt}"{vars_str})'
            elif hasattr(expr, 'value'): # Literal
                return f'{ind}log.Printf("{expr.value}")'
            return f'{ind}log.Printf("%v", {self.transpile_expression(expr)})'

        if isinstance(stmt, CallStatement):
            args = [self.transpile_expression(arg) for arg in stmt.arguments]
            if stmt.procedure_name == "write_file":
                return f"{ind}writeFile({', '.join(args)})"
            
            proc = self.to_camel_case(stmt.procedure_name)
            target = stmt.target_variable.lstrip('@') if stmt.target_variable else "_"
            # Handle return values (simplified)
            return f"{ind}{target}, _, _, err = {proc}({', '.join(args)}, ollamaHost)\n{ind}if err != nil {{ return \"\", \"error\", 0, err }}"

        if isinstance(stmt, GenerateIntoStatement):
            clause = stmt.generate_clause
            model = self.transpile_expression(clause.model) if clause.model else "writerModel" # fallback
            # Special case for self_refine models
            if "@writer_model" in str(clause.model): model = "writerModel"
            if "@critic_model" in str(clause.model): model = "criticModel"
            
            args = [self.transpile_expression(arg) for arg in clause.arguments]
            prompt_call = f"fmt.Sprintf({clause.function_name}Prompt, {', '.join(args)})"
            target = stmt.target_variable.lstrip('@')
            return f"{ind}{target}, err = generate(ollamaHost, {model}, {prompt_call})\n{ind}if err != nil {{ return \"\", \"error\", 0, err }}"

        if isinstance(stmt, WhileStatement):
            cond = self.transpile_expression(stmt.condition)
            res = [f"{ind}for {cond} {{"]
            self.indent_level += 1
            for sub in stmt.body:
                res.append(self.transpile_statement(sub))
            self.indent_level -= 1
            res.append(f"{ind}}}")
            return "\n".join(res)

        if isinstance(stmt, EvaluateStatement):
            expr = self.transpile_expression(stmt.expression)
            res = []
            first = True
            for clause in stmt.when_clauses:
                keyword = "if" if first else "} else if"
                first = False
                # Handle SemanticCondition like 'contains:[APPROVED]'
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
            status = "\"complete\""
            iters = "iteration"
            # Extract WITH status = ... iterations = ...
            if hasattr(stmt, 'options') and stmt.options:
                if 'status' in stmt.options:
                    status = self.transpile_expression(stmt.options['status'])
                if 'iterations' in stmt.options:
                    iters = self.transpile_expression(stmt.options['iterations'])
            
            return f"{ind}return {val}, {status}, {iters}, nil"

        return f"{ind}// TODO: {type(stmt).__name__}"

    def transpile_expression(self, expr):
        if isinstance(expr, Literal):
            if isinstance(expr.value, str):
                return f'"{expr.value}"'
            return str(expr.value).lower()
        if isinstance(expr, ParamRef):
            return expr.name.lstrip('@')
        if isinstance(expr, NoneLiteral):
            return '""'
        if isinstance(expr, Condition):
            left = self.transpile_expression(expr.left)
            right = self.transpile_expression(expr.right)
            return f"{left} {expr.operator} {right}"
        if isinstance(expr, UnaryOp):
            return f"!({self.transpile_expression(expr.operand)})"
        if isinstance(expr, CompoundCondition):
            left = self.transpile_expression(expr.left)
            right = self.transpile_expression(expr.right)
            op = "&&" if expr.operator == 'AND' else "||"
            return f"({left} {op} {right})"
        return f"/* {type(expr).__name__} {str(expr)} */"

    def to_camel_case(self, snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    def generate_main(self, wf: WorkflowStatement):
        name = self.to_camel_case(wf.name)
        # We need to match flags to parameters
        flags = []
        call_args = []
        for p in wf.inputs:
            name_go = p.name.lstrip('@')
            flag_name = name_go.replace('_', '-')
            default = "string"
            if isinstance(p.default_value, Literal):
                default = self.transpile_expression(p.default_value)
            
            if p.param_type in ("INTEGER", "INT"):
                flags.append(f'  {name_go} := flag.Int("{flag_name}", {default or 0}, "{name_go}")')
                call_args.append(f"*{name_go}")
            else:
                default_val = default or '""'
                flags.append(f'  {name_go} := flag.String("{flag_name}", {default_val}, "{name_go}")')
                call_args.append(f"*{name_go}")

        flags_str = "\n".join(flags)
        call_args.append('"http://localhost:11434"')
        
        return f"""
func main() {{
{flags_str}
  flag.Parse()
  res, status, iters, err := {name}({', '.join(call_args)})
  if err != nil {{ log.Fatal(err) }}
  fmt.Printf("Status: %s, Iters: %d\\n%s\\n", status, iters, res)
}}
"""

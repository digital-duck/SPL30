import sys
from pathlib import Path
from spl.lexer import Lexer
from spl3.parser import SPL3Parser

def dump_ast(spl_file):
    source = Path(spl_file).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    parser = SPL3Parser(tokens)
    program = parser.parse()
    
    for stmt in program.statements:
        print_node(stmt)

def print_node(node, indent=0):
    prefix = "  " * indent
    attrs = []
    if hasattr(node, 'name'): attrs.append(f"name={node.name}")
    if hasattr(node, 'procedure_name'): attrs.append(f"proc={node.procedure_name}")
    if hasattr(node, 'variable_name'): attrs.append(f"var={node.variable_name}")
    if hasattr(node, 'target_variable'): attrs.append(f"target={node.target_variable}")
    
    attr_str = f" ({', '.join(attrs)})" if attrs else ""
    print(f"{prefix}{type(node).__name__}{attr_str}")
    
    # Check for list-like body attributes
    for attr in ['statements', 'body', 'else_statements']:
        if hasattr(node, attr):
            val = getattr(node, attr)
            if isinstance(val, list):
                if attr != 'statements' or not isinstance(node, (list)): # avoid recursion if node itself is list
                    if val:
                        print(f"{prefix}  {attr}:")
                        for sub in val:
                            print_node(sub, indent + 2)
    
    if hasattr(node, 'cases') and isinstance(node.cases, list):
        for case in node.cases:
            print(f"{prefix}  CASE:")
            print_node(case, indent + 2)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        dump_ast(sys.argv[1])
    else:
        print("Usage: python dump_ast.py <file.spl>")

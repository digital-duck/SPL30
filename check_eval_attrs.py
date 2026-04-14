import sys
from pathlib import Path
from spl.lexer import Lexer
from spl3.parser import SPL3Parser
from spl.ast_nodes import EvaluateStatement

def main(spl_file):
    source = Path(spl_file).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    parser = SPL3Parser(tokens)
    program = parser.parse()
    
    for stmt in program.statements:
        if hasattr(stmt, 'body'):
            for sub in stmt.body:
                if isinstance(sub, EvaluateStatement):
                    print(f"Evaluate: {sub}")
                    print(f"Attributes: {dir(sub)}")
                    return
                if hasattr(sub, 'body'): # Check nested
                    for sub2 in sub.body:
                        if isinstance(sub2, EvaluateStatement):
                             print(f"Evaluate: {sub2}")
                             print(f"Attributes: {dir(sub2)}")
                             return

if __name__ == "__main__":
    main(sys.argv[1])

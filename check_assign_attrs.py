import sys
from pathlib import Path
from spl.lexer import Lexer
from spl3.parser import SPL3Parser
from spl.ast_nodes import AssignmentStatement

def main(spl_file):
    source = Path(spl_file).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    parser = SPL3Parser(tokens)
    program = parser.parse()
    
    for stmt in program.statements:
        if hasattr(stmt, 'body'):
            for sub in stmt.body:
                if isinstance(sub, AssignmentStatement):
                    print(f"Assignment: {sub}")
                    print(f"Attributes: {dir(sub)}")
                    return

if __name__ == "__main__":
    main(sys.argv[1])

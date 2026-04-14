import sys
from pathlib import Path
from spl.lexer import Lexer
from spl3.parser import SPL3Parser
from spl.ast_nodes import WorkflowStatement

def main(spl_file):
    source = Path(spl_file).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    parser = SPL3Parser(tokens)
    program = parser.parse()
    
    for stmt in program.statements:
        if isinstance(stmt, WorkflowStatement):
            print(f"Workflow: {stmt.name}")
            print(f"Attributes: {dir(stmt)}")
            break

if __name__ == "__main__":
    main(sys.argv[1])

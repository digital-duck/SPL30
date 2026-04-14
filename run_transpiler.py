import sys
from pathlib import Path
from spl.lexer import Lexer
from spl3.parser import SPL3Parser
from spl3.splc.transpiler_go import GoTranspiler

def main(spl_file):
    source = Path(spl_file).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    parser = SPL3Parser(tokens)
    program = parser.parse()
    
    transpiler = GoTranspiler(Path(spl_file).stem)
    go_code = transpiler.transpile(program)
    
    out_file = Path(spl_file).with_suffix(".go")
    out_file.write_text(go_code, encoding="utf-8")
    print(f"Generated {out_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python run_transpiler.py <file.spl>")

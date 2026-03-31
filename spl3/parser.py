"""SPL 3.0 Parser — extends SPL 2.0 parser with new type system and syntax.

New capabilities over SPL 2.0:
  - NONE / NULL literal  →  Literal(value=None, literal_type='none')
  - { a, b, c }          →  SetLiteral  (no colon → SET; colon → MAP)
  - SET as type annotation  (SET is a keyword token in SPL 2.0; handled here)
  - INT, FLOAT, IMAGE, AUDIO, VIDEO type annotations  (IDENTIFIER tokens)
  - IMPORT 'file.spl'    →  ImportStatement
  - CALL PARALLEL ... END  →  CallParallelStatement

SPL 2.0 backward compatibility is fully preserved:
  - All existing MAP literals { 'k': v } continue to work.
  - {} (empty braces) remains a MAP literal (consistent with Python).
  - All SPL 2.0 type annotations (TEXT, NUMBER, BOOL, LIST, MAP, STORAGE)
    are unchanged.
"""

from __future__ import annotations

from spl.tokens import TokenType
from spl.parser import Parser as SPL2Parser
from spl.ast_nodes import (
    MapLiteral, Parameter, StorageSpec, Expression,
    CallStatement,
)

from spl3.ast_nodes import (
    NoneLiteral, SetLiteral, ImportStatement,
    CallParallelBranch, CallParallelStatement,
)


class SPL3Parser(SPL2Parser):
    """SPL 3.0 recursive descent parser, extending SPL 2.0."""

    # ------------------------------------------------------------------ #
    # Statement dispatch                                                   #
    # ------------------------------------------------------------------ #

    def _parse_statement(self):
        """Dispatch to the appropriate statement parser.

        Handles SPL 3.0 additions:
          IMPORT 'file.spl'
        before falling through to SPL 2.0 dispatch.
        """
        tok = self._current()

        # IMPORT 'file.spl'
        if tok.type == TokenType.IDENTIFIER and tok.value.lower() == "import":
            return self._parse_import_statement()

        return super()._parse_statement()

    # ------------------------------------------------------------------ #
    # IMPORT statement                                                     #
    # ------------------------------------------------------------------ #

    def _parse_import_statement(self) -> ImportStatement:
        """Parse IMPORT 'file.spl'"""
        self._advance()  # consume 'import' identifier
        path = self._expect(TokenType.STRING).value
        return ImportStatement(path=path)

    # ------------------------------------------------------------------ #
    # CALL PARALLEL override                                               #
    # ------------------------------------------------------------------ #

    def _parse_call_statement(self):
        """Parse CALL [PARALLEL] ...

        CALL workflow(@args) INTO @var              → CallStatement (SPL 2.0)
        CALL PARALLEL workflow1(...) INTO @a,       → CallParallelStatement
                      workflow2(...) INTO @b
        END
        """
        self._expect(TokenType.CALL)
        tok = self._current()

        # Detect PARALLEL keyword (comes through as IDENTIFIER)
        if tok.type == TokenType.IDENTIFIER and tok.value.lower() == "parallel":
            self._advance()  # consume 'parallel'
            return self._parse_call_parallel_body()

        # Normal CALL — re-implement (can't call super because we already
        # consumed the CALL token; reconstruct the same logic)
        proc_name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.LPAREN)
        arguments: list[Expression] = []
        if not self._check(TokenType.RPAREN):
            arguments.append(self._parse_call_argument())
            while self._check(TokenType.COMMA):
                self._advance()
                arguments.append(self._parse_call_argument())
        self._expect(TokenType.RPAREN)

        target = None
        if self._check(TokenType.INTO):
            self._advance()
            self._expect(TokenType.AT)
            target = self._expect_identifier_or_keyword().value

        return CallStatement(
            procedure_name=proc_name,
            arguments=arguments,
            target_variable=target,
        )

    def _parse_call_parallel_body(self) -> CallParallelStatement:
        """Parse the branch list after CALL PARALLEL ... END"""
        branches: list[CallParallelBranch] = []
        while not self._check(TokenType.END) and not self._check(TokenType.EOF):
            branch = self._parse_parallel_branch()
            branches.append(branch)
            if self._check(TokenType.COMMA):
                self._advance()  # optional comma between branches
        self._expect(TokenType.END)
        return CallParallelStatement(branches=branches)

    def _parse_parallel_branch(self) -> CallParallelBranch:
        """Parse a single  workflow_name(@args) INTO @var  branch."""
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.LPAREN)
        arguments: list[Expression] = []
        if not self._check(TokenType.RPAREN):
            arguments.append(self._parse_call_argument())
            while self._check(TokenType.COMMA):
                self._advance()
                arguments.append(self._parse_call_argument())
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.INTO)
        self._expect(TokenType.AT)
        target = self._expect_identifier_or_keyword().value
        return CallParallelBranch(
            workflow_name=name,
            arguments=arguments,
            target_var=target,
        )

    # ------------------------------------------------------------------ #
    # Expression primary — NONE literal + SET vs MAP disambiguation        #
    # ------------------------------------------------------------------ #

    def _parse_primary(self) -> Expression:
        """Parse a primary expression.

        Intercepts before delegating to SPL 2.0:
          1. NONE / NULL literal tokens (IDENTIFIER with value none/null)
          2. { } brace literals — disambiguates MAP vs SET
        """
        tok = self._current()

        # NONE / NULL literal
        if tok.type == TokenType.IDENTIFIER and tok.value.upper() in ("NONE", "NULL"):
            self._advance()
            return NoneLiteral()

        # { } — MAP or SET depending on first element
        if tok.type == TokenType.LBRACE:
            return self._parse_brace_literal()

        # Everything else: SPL 2.0 handles it
        return super()._parse_primary()

    def _parse_brace_literal(self):
        """Parse { } as either a MapLiteral or SetLiteral.

        Disambiguation rule (same as Python):
          {}            → empty MapLiteral
          {key: val}    → MapLiteral  (colon after first element)
          {elem, elem}  → SetLiteral  (comma after first element)
        """
        self._advance()  # consume {

        # Empty braces → MAP (consistent with Python {})
        if self._check(TokenType.RBRACE):
            self._advance()
            return MapLiteral(pairs=[])

        # Parse first element
        first = self._parse_expression()

        if self._check(TokenType.COLON):
            # {key: val, ...} → MAP
            self._advance()  # consume :
            val = self._parse_expression()
            pairs = [(first, val)]
            while self._check(TokenType.COMMA):
                self._advance()
                if self._check(TokenType.RBRACE):
                    break  # trailing comma
                key = self._parse_expression()
                self._expect(TokenType.COLON)
                val = self._parse_expression()
                pairs.append((key, val))
            self._expect(TokenType.RBRACE)
            return MapLiteral(pairs=pairs)

        else:
            # {elem, ...} → SET
            elements = [first]
            while self._check(TokenType.COMMA):
                self._advance()
                if self._check(TokenType.RBRACE):
                    break  # trailing comma
                elements.append(self._parse_expression())
            self._expect(TokenType.RBRACE)
            return SetLiteral(elements=elements)

    # ------------------------------------------------------------------ #
    # Workflow / procedure parameter — handle SET keyword as type          #
    # ------------------------------------------------------------------ #

    def _parse_workflow_param(self) -> Parameter:
        """Parse @name [type] [DEFAULT value].

        Extends SPL 2.0 to recognise TokenType.SET as a valid type annotation
        (SET is a reserved keyword in SPL 2.0 for the SET @var = expr alias,
        so it arrives as TokenType.SET rather than TokenType.IDENTIFIER).

        All other type annotations (INT, FLOAT, IMAGE, AUDIO, VIDEO, NONE,
        TEXT, NUMBER, BOOL, LIST, MAP) are plain IDENTIFIER tokens and are
        already handled by the SPL 2.0 method.
        """
        self._expect(TokenType.AT)
        name = self._expect_identifier_or_keyword().value
        param_type = None
        default_value = None

        if self._check(TokenType.IDENTIFIER):
            if self._current().value.upper() == "STORAGE":
                self._advance()  # consume STORAGE
                param_type = "STORAGE"
                if self._check(TokenType.LPAREN):
                    self._advance()  # consume (
                    backend = self._expect(TokenType.IDENTIFIER).value
                    self._expect(TokenType.COMMA)
                    path = self._expect(TokenType.STRING).value
                    self._expect(TokenType.RPAREN)
                    default_value = StorageSpec(backend=backend, path=path)
            else:
                param_type = self._advance().value  # TEXT, NUMBER, BOOL, LIST, MAP, INT, FLOAT, IMAGE …

        elif self._check(TokenType.SET):
            # SET is a keyword token, not IDENTIFIER — accept as type annotation
            param_type = self._advance().value  # "set"

        if self._check(TokenType.DEFAULT):
            self._advance()
            default_value = self._parse_expression()

        return Parameter(name=name, param_type=param_type, default_value=default_value)

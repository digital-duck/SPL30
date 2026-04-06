"""Tests for SPL 3.0 extended type system.

Covers:
  - NONE / NULL literal parsing and evaluation
  - SET literal parsing and evaluation (vs MAP disambiguation)
  - INT / FLOAT type annotations and coercion
  - IMAGE / AUDIO / VIDEO type annotations (pass-through)
  - SET as type annotation in workflow params
  - IMPORT statement parsing
  - SPL3Type enum helpers

Run: pytest tests/test_types.py -v
"""

import json
import pytest

# ------------------------------------------------------------------ #
# Helpers: parse + evaluate without hitting an LLM                   #
# ------------------------------------------------------------------ #

def _parse(source: str):
    """Lex + parse SPL3 source, return the parsed Program."""
    from spl.lexer import Lexer
    from spl.parser import SPL3Parser
    tokens = Lexer(source).tokenize()
    return SPL3Parser(tokens).parse()


def _eval_expr_source(source: str) -> str:
    """Evaluate a standalone expression source string.

    Wraps the expression in a minimal workflow assignment so we can
    use the executor's _eval_expression without an LLM call.
    """
    from spl.lexer import Lexer
    from spl.parser import SPL3Parser
    from spl.executor import SPL3Executor

    # Wrap in assignment: @_result := <expr>
    wrapped = f"@_result := {source}"
    tokens = Lexer(wrapped).tokenize()
    program = SPL3Parser(tokens).parse()
    # Program has one AssignmentStatement
    stmt = program.statements[0]

    # Create a minimal state and executor to evaluate the expression
    from spl.executor import WorkflowState
    state = WorkflowState()

    # Build a minimal adapter stub — never called for pure expression eval
    class NullAdapter:
        pass

    executor = SPL3Executor(adapter=NullAdapter())  # type: ignore[arg-type]
    return executor._eval_expression(stmt.expression, state)


# ================================================================== #
# NONE / NULL literal                                                 #
# ================================================================== #

class TestNoneLiteral:

    def test_none_parses(self):
        from spl.ast_nodes import NoneLiteral
        program = _parse("@x := NONE")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, NoneLiteral)

    def test_null_alias_parses(self):
        """NULL is a case-insensitive alias for NONE."""
        from spl.ast_nodes import NoneLiteral
        program = _parse("@x := NULL")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, NoneLiteral)

    def test_none_lowercase_parses(self):
        from spl.ast_nodes import NoneLiteral
        program = _parse("@x := none")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, NoneLiteral)

    def test_none_evaluates_to_empty_string(self):
        result = _eval_expr_source("NONE")
        assert result == ""

    def test_null_evaluates_to_empty_string(self):
        result = _eval_expr_source("NULL")
        assert result == ""

    def test_none_as_default_value(self):
        """NONE can be used as a DEFAULT value in INPUT params."""
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @threshold FLOAT DEFAULT NONE\n"
            "    OUTPUT: @result TEXT\n"
            "DO\n"
            "    @result := 'ok'\n"
            "    COMMIT @result\n"
            "END"
        )
        from spl.ast_nodes import WorkflowStatement
        from spl.ast_nodes import NoneLiteral
        stmt = program.statements[0]
        assert isinstance(stmt, WorkflowStatement)
        param = stmt.inputs[0]
        assert param.name == "threshold"
        assert isinstance(param.default_value, NoneLiteral)


# ================================================================== #
# SET literal                                                         #
# ================================================================== #

class TestSetLiteral:

    def test_set_literal_parses(self):
        from spl.ast_nodes import SetLiteral
        program = _parse("@tags := {'python', 'sql', 'linux'}")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, SetLiteral)
        assert len(stmt.expression.elements) == 3

    def test_set_evaluates_to_sorted_json_array(self):
        result = _eval_expr_source("{'python', 'sql', 'linux'}")
        parsed = json.loads(result)
        assert parsed == ["linux", "python", "sql"]  # sorted

    def test_set_deduplicates(self):
        result = _eval_expr_source("{'apple', 'banana', 'apple'}")
        parsed = json.loads(result)
        assert parsed == ["apple", "banana"]
        assert len(parsed) == 2

    def test_empty_braces_is_map(self):
        """Empty {} → MapLiteral, consistent with Python."""
        from spl.ast_nodes import MapLiteral
        program = _parse("@x := {}")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, MapLiteral)

    def test_braces_with_colon_is_map(self):
        """{'key': 'val'} → MapLiteral (colon present)."""
        from spl.ast_nodes import MapLiteral
        program = _parse("@x := {'key': 'val', 'other': 'thing'}")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, MapLiteral)
        assert len(stmt.expression.pairs) == 2

    def test_set_trailing_comma(self):
        """Trailing comma in set literal is tolerated."""
        from spl.ast_nodes import SetLiteral
        program = _parse("@tags := {'a', 'b', 'c',}")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, SetLiteral)
        assert len(stmt.expression.elements) == 3

    def test_single_element_set(self):
        """Single-element: no comma → actually parsed as MAP-like expression.
        A single brace {expr} with no colon and no comma falls through to
        a single-element set — edge case handled gracefully."""
        from spl.ast_nodes import SetLiteral
        # Single element followed by } has no comma → parsed as SET with 1 element
        program = _parse("@x := {'only'}")
        stmt = program.statements[0]
        assert isinstance(stmt.expression, SetLiteral)
        assert len(stmt.expression.elements) == 1


# ================================================================== #
# INT / FLOAT type annotations and coercion                           #
# ================================================================== #

class TestNumericTypes:

    def test_int_annotation_parsed(self):
        """INT type annotation is stored as param_type string."""
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @count INT\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert isinstance(stmt, WorkflowStatement)
        assert stmt.inputs[0].param_type.upper() == "INT"

    def test_float_annotation_parsed(self):
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @score FLOAT\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert stmt.inputs[0].param_type.upper() == "FLOAT"

    def test_integer_alias_annotation(self):
        """INTEGER is a valid alias for INT."""
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @n INTEGER\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert stmt.inputs[0].param_type.upper() == "INTEGER"

    @pytest.mark.asyncio
    async def test_int_coercion_integer_string(self):
        """INT-typed param: '42' → coerced to '42'."""
        from spl.lexer import Lexer
        from spl.parser import SPL3Parser
        from spl.executor import SPL3Executor

        source = (
            "WORKFLOW w\n"
            "    INPUT: @n INT\n"
            "    OUTPUT: @result TEXT\n"
            "DO\n"
            "    @result := @n\n"
            "    COMMIT @result\n"
            "END"
        )
        tokens = Lexer(source).tokenize()
        program = SPL3Parser(tokens).parse()
        stmt = program.statements[0]

        class EchoAdapter:
            async def generate(self, prompt, **kw):
                from spl.adapters.base import GenerationResult
                return GenerationResult(content=prompt, model="echo",
                                        input_tokens=0, output_tokens=0,
                                        latency_ms=0)

        executor = SPL3Executor(adapter=EchoAdapter())  # type: ignore[arg-type]
        result = await executor.execute_workflow(stmt, params={"n": "42"})
        assert result.output["n"] == "42"

    @pytest.mark.asyncio
    async def test_int_coercion_float_string(self):
        """INT-typed param: '7.9' → truncated to '7'."""
        from spl.lexer import Lexer
        from spl.parser import SPL3Parser
        from spl.executor import SPL3Executor

        source = (
            "WORKFLOW w\n"
            "    INPUT: @n INT\n"
            "    OUTPUT: @result TEXT\n"
            "DO\n"
            "    @result := @n\n"
            "    COMMIT @result\n"
            "END"
        )
        tokens = Lexer(source).tokenize()
        stmt = SPL3Parser(tokens).parse().statements[0]

        class EchoAdapter:
            async def generate(self, prompt, **kw):
                from spl.adapters.base import GenerationResult
                return GenerationResult(content=prompt, model="echo",
                                        input_tokens=0, output_tokens=0,
                                        latency_ms=0)

        executor = SPL3Executor(adapter=EchoAdapter())  # type: ignore[arg-type]
        result = await executor.execute_workflow(stmt, params={"n": "7.9"})
        assert result.output["n"] == "7"

    @pytest.mark.asyncio
    async def test_float_coercion(self):
        """FLOAT-typed param: '3.14' stored as '3.14'."""
        from spl.lexer import Lexer
        from spl.parser import SPL3Parser
        from spl.executor import SPL3Executor

        source = (
            "WORKFLOW w\n"
            "    INPUT: @score FLOAT\n"
            "    OUTPUT: @result TEXT\n"
            "DO\n"
            "    @result := @score\n"
            "    COMMIT @result\n"
            "END"
        )
        tokens = Lexer(source).tokenize()
        stmt = SPL3Parser(tokens).parse().statements[0]

        class EchoAdapter:
            async def generate(self, prompt, **kw):
                from spl.adapters.base import GenerationResult
                return GenerationResult(content=prompt, model="echo",
                                        input_tokens=0, output_tokens=0,
                                        latency_ms=0)

        executor = SPL3Executor(adapter=EchoAdapter())  # type: ignore[arg-type]
        result = await executor.execute_workflow(stmt, params={"score": "3.14"})
        assert result.output["score"] == "3.14"

    def test_number_annotation_still_works(self):
        """SPL 2.0 NUMBER annotation is unchanged."""
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @x NUMBER\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert stmt.inputs[0].param_type.upper() == "NUMBER"


# ================================================================== #
# Multimodal type annotations: IMAGE, AUDIO, VIDEO                   #
# ================================================================== #

class TestMultimodalTypes:

    @pytest.mark.parametrize("type_name", ["IMAGE", "AUDIO", "VIDEO"])
    def test_multimodal_annotation_parsed(self, type_name):
        """IMAGE / AUDIO / VIDEO are valid type annotations."""
        source = (
            f"WORKFLOW w\n"
            f"    INPUT: @media {type_name}\n"
            f"    OUTPUT: @answer TEXT\n"
            f"DO COMMIT 'ok' END"
        )
        program = _parse(source)
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert isinstance(stmt, WorkflowStatement)
        assert stmt.inputs[0].param_type.upper() == type_name

    @pytest.mark.asyncio
    @pytest.mark.parametrize("type_name", ["IMAGE", "AUDIO", "VIDEO"])
    async def test_multimodal_param_passed_through(self, type_name):
        """Multimodal params pass through unchanged — no coercion."""
        from spl.lexer import Lexer
        from spl.parser import SPL3Parser
        from spl.executor import SPL3Executor

        source = (
            f"WORKFLOW w\n"
            f"    INPUT: @media {type_name}\n"
            f"    OUTPUT: @result TEXT\n"
            f"DO\n"
            f"    @result := @media\n"
            f"    COMMIT @result\n"
            f"END"
        )
        tokens = Lexer(source).tokenize()
        stmt = SPL3Parser(tokens).parse().statements[0]

        class EchoAdapter:
            async def generate(self, prompt, **kw):
                from spl.adapters.base import GenerationResult
                return GenerationResult(content=prompt, model="echo",
                                        input_tokens=0, output_tokens=0,
                                        latency_ms=0)

        executor = SPL3Executor(adapter=EchoAdapter())  # type: ignore[arg-type]
        media_value = "/path/to/file.jpg"
        result = await executor.execute_workflow(stmt, params={"media": media_value})
        assert result.output["media"] == media_value


# ================================================================== #
# SET as type annotation                                              #
# ================================================================== #

class TestSetTypeAnnotation:

    def test_set_annotation_parsed(self):
        """SET is a keyword token (TokenType.SET) but valid as type annotation."""
        program = _parse(
            "WORKFLOW w\n"
            "    INPUT: @tags SET\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        from spl.ast_nodes import WorkflowStatement
        stmt = program.statements[0]
        assert isinstance(stmt, WorkflowStatement)
        # param_type value is the raw token value ("set" lowercase)
        assert stmt.inputs[0].param_type.upper() == "SET"


# ================================================================== #
# IMPORT statement                                                    #
# ================================================================== #

class TestImportStatement:

    def test_import_parses(self):
        from spl.ast_nodes import ImportStatement
        program = _parse("IMPORT 'lib/agents.spl'")
        assert len(program.statements) == 1
        stmt = program.statements[0]
        assert isinstance(stmt, ImportStatement)
        assert stmt.path == "lib/agents.spl"

    def test_import_before_workflow(self):
        from spl.ast_nodes import ImportStatement
        from spl.ast_nodes import WorkflowStatement
        source = (
            "IMPORT 'shared/validators.spl'\n"
            "WORKFLOW my_workflow\n"
            "    INPUT: @text TEXT\n"
            "    OUTPUT: @result TEXT\n"
            "DO COMMIT 'ok' END"
        )
        program = _parse(source)
        assert len(program.statements) == 2
        assert isinstance(program.statements[0], ImportStatement)
        assert isinstance(program.statements[1], WorkflowStatement)

    def test_import_loader_resolves_file(self, tmp_path):
        """load_workflows_from_file follows IMPORT and loads referenced workflows."""
        from spl._loader import load_workflows_from_file

        # Create a shared library file
        lib_file = tmp_path / "lib.spl"
        lib_file.write_text(
            "WORKFLOW helper\n"
            "    INPUT: @x TEXT\n"
            "    OUTPUT: @y TEXT\n"
            "DO\n"
            "    @y := @x\n"
            "    COMMIT @y\n"
            "END\n"
        )

        # Create main file that imports the library
        main_file = tmp_path / "main.spl"
        main_file.write_text(
            f"IMPORT 'lib.spl'\n"
            "WORKFLOW main_flow\n"
            "    INPUT: @text TEXT\n"
            "    OUTPUT: @result TEXT\n"
            "DO\n"
            "    @result := @text\n"
            "    COMMIT @result\n"
            "END\n"
        )

        defns = load_workflows_from_file(main_file)
        names = [d.name for d in defns]
        assert "helper" in names
        assert "main_flow" in names

    def test_import_circular_detected(self, tmp_path, caplog):
        """Circular IMPORT is detected and skipped with a warning."""
        import logging
        from spl._loader import load_workflows_from_file

        a = tmp_path / "a.spl"
        b = tmp_path / "b.spl"
        a.write_text("IMPORT 'b.spl'\nWORKFLOW wf_a INPUT: @x TEXT OUTPUT: @y TEXT DO COMMIT 'a' END")
        b.write_text("IMPORT 'a.spl'\nWORKFLOW wf_b INPUT: @x TEXT OUTPUT: @y TEXT DO COMMIT 'b' END")

        with caplog.at_level(logging.WARNING, logger="spl.loader"):
            defns = load_workflows_from_file(a)

        assert "Circular" in caplog.text
        names = [d.name for d in defns]
        # At least one workflow loaded; circular ref skipped
        assert len(names) >= 1


# ================================================================== #
# SPL3Type enum helpers                                               #
# ================================================================== #

class TestSPL3Type:

    def test_from_str_canonical(self):
        from spl.types import SPL3Type
        assert SPL3Type.from_str("TEXT") == SPL3Type.TEXT
        assert SPL3Type.from_str("INT") == SPL3Type.INT
        assert SPL3Type.from_str("FLOAT") == SPL3Type.FLOAT
        assert SPL3Type.from_str("NONE") == SPL3Type.NONE
        assert SPL3Type.from_str("SET") == SPL3Type.SET
        assert SPL3Type.from_str("IMAGE") == SPL3Type.IMAGE

    def test_from_str_aliases(self):
        from spl.types import SPL3Type
        assert SPL3Type.from_str("BOOLEAN") == SPL3Type.BOOL
        assert SPL3Type.from_str("NULL") == SPL3Type.NONE
        assert SPL3Type.from_str("INTEGER") == SPL3Type.INT
        assert SPL3Type.from_str("STR") == SPL3Type.TEXT
        assert SPL3Type.from_str("DICT") == SPL3Type.MAP
        assert SPL3Type.from_str("STRUCT") == SPL3Type.DATACLASS

    def test_from_str_case_insensitive(self):
        from spl.types import SPL3Type
        assert SPL3Type.from_str("text") == SPL3Type.TEXT
        assert SPL3Type.from_str("Float") == SPL3Type.FLOAT
        assert SPL3Type.from_str("none") == SPL3Type.NONE

    def test_from_str_unknown_raises(self):
        from spl.types import SPL3Type
        with pytest.raises(ValueError, match="Unknown SPL type"):
            SPL3Type.from_str("BANANA")

    def test_is_multimodal(self):
        from spl.types import SPL3Type
        assert SPL3Type.IMAGE.is_multimodal
        assert SPL3Type.AUDIO.is_multimodal
        assert SPL3Type.VIDEO.is_multimodal
        assert not SPL3Type.TEXT.is_multimodal
        assert not SPL3Type.INT.is_multimodal

    def test_is_collection(self):
        from spl.types import SPL3Type
        assert SPL3Type.LIST.is_collection
        assert SPL3Type.SET.is_collection
        assert SPL3Type.MAP.is_collection
        assert not SPL3Type.TEXT.is_collection

    def test_is_numeric(self):
        from spl.types import SPL3Type
        assert SPL3Type.INT.is_numeric
        assert SPL3Type.FLOAT.is_numeric
        assert SPL3Type.NUMBER.is_numeric
        assert not SPL3Type.TEXT.is_numeric

    def test_python_equivalent(self):
        from spl.types import SPL3Type
        assert SPL3Type.INT.python_equivalent == "int"
        assert SPL3Type.FLOAT.python_equivalent == "float"
        assert SPL3Type.NONE.python_equivalent == "None"
        assert SPL3Type.SET.python_equivalent == "set"
        assert SPL3Type.IMAGE.python_equivalent == "bytes | str"


# ================================================================== #
# Coerce helpers                                                      #
# ================================================================== #

class TestCoerceHelpers:

    def test_coerce_to_int_integer_string(self):
        from spl.types import coerce_to_int
        assert coerce_to_int("42") == 42

    def test_coerce_to_int_float_string(self):
        from spl.types import coerce_to_int
        assert coerce_to_int("7.9") == 7

    def test_coerce_to_int_invalid_raises(self):
        from spl.types import coerce_to_int
        with pytest.raises(ValueError):
            coerce_to_int("not_a_number")

    def test_coerce_to_float(self):
        from spl.types import coerce_to_float
        assert coerce_to_float("3.14") == pytest.approx(3.14)
        assert coerce_to_float("42") == pytest.approx(42.0)

    def test_coerce_to_float_invalid_raises(self):
        from spl.types import coerce_to_float
        with pytest.raises(ValueError):
            coerce_to_float("not_a_number")

    def test_is_none_value(self):
        from spl.types import is_none_value
        assert is_none_value("")
        assert is_none_value("none")
        assert is_none_value("null")
        assert is_none_value("NONE")
        assert is_none_value("NULL")
        assert not is_none_value("0")
        assert not is_none_value("false")
        assert not is_none_value("hello")

"""SPL 3.0 Type System — extended type registry over SPL 2.0.

SPL is designed to feel natural to developers from three backgrounds:

  SQL        → SELECT, WITH, GENERATE, EVALUATE, typed columns
  Python     → @var, BOOL, LIST, MAP, INT, FLOAT, NONE, SET, DATACLASS
  Linux/bash → workflow pipelines, IMPORT, CALL PARALLEL, exit channels

The type system extends SPL 2.0 in four directions:

  1. Numeric precision split: NUMBER → INT | FLOAT
  2. Null semantics:           NONE (first-class null literal)
  3. Collection complement:    SET (unordered unique; LIST is ordered)
  4. Multimodal I/O:           IMAGE | AUDIO | VIDEO (for Liquid AI LFM)
  5. Structured records:       DATACLASS (named field structs, v3.1+)

SPL 2.0 compatibility:
  All SPL 2.0 type annotations (TEXT, NUMBER, BOOL, LIST, MAP, STORAGE)
  remain valid and unchanged in SPL 3.0.  NUMBER is kept as an alias
  that accepts both int and float values.

Python analogue mapping (for Python developers):

  +------------------+-------------+------------------------------------------+
  | SPL 3.0 type     | Python type | Notes                                    |
  +------------------+-------------+------------------------------------------+
  | TEXT             | str         | unchanged from v2.0                      |
  | INT              | int         | new; replaces NUMBER for integer values  |
  | FLOAT            | float       | new; replaces NUMBER for float values    |
  | NUMBER           | int|float   | v2.0 compat alias; accepts both          |
  | BOOL             | bool        | unchanged; TRUE/FALSE literals           |
  | LIST             | list        | unchanged; [a, b, c] literal             |
  | MAP              | dict        | unchanged; {'k': v} literal              |
  | SET              | set         | new; {a, b, c} literal (no colon → SET) |
  | NONE             | None        | new; NONE literal                        |
  | IMAGE            | bytes/path  | new; multimodal input/output             |
  | AUDIO            | bytes/path  | new; multimodal input/output             |
  | VIDEO            | bytes/path  | new; multimodal input/output             |
  | STORAGE          | Connection  | unchanged; STORAGE(sqlite, 'path')       |
  | DATACLASS        | dataclass   | planned v3.1; CREATE TYPE ... AS (...)   |
  +------------------+-------------+------------------------------------------+

Syntax examples:

  -- NONE literal (null value)
  @result := NONE

  -- INT and FLOAT type annotations
  WORKFLOW count_tokens
      INPUT:  @text TEXT, @limit INT DEFAULT 4096
      OUTPUT: @ratio FLOAT

  -- SET literal  ({...} without colons → SET; with colons → MAP)
  @seen := {'apple', 'banana', 'cherry'}

  -- Multimodal INPUT for Liquid AI LFM adapter
  WORKFLOW describe_image
      INPUT:  @photo IMAGE, @question TEXT DEFAULT 'What is in this image?'
      OUTPUT: @answer TEXT
  DO
      GENERATE vision_describe(@photo, @question) INTO @answer
      COMMIT @answer
  END

  -- DATACLASS (v3.1 design, not yet implemented)
  CREATE TYPE Review AS (
      score   FLOAT,
      verdict TEXT,
      passed  BOOL
  )

  WORKFLOW evaluate_code
      INPUT:  @code TEXT
      OUTPUT: @review Review
  DO
      GENERATE reviewer(@code) INTO @review
      COMMIT @review
  END
"""

from __future__ import annotations
from enum import Enum


class SPL3Type(Enum):
    """Canonical SPL 3.0 type identifiers.

    Used as the value of Parameter.param_type after parsing.
    The parser stores the raw keyword string; call SPL3Type.from_str()
    to normalize and validate it.
    """

    # ----------------------------------------------------------------
    # Scalar types (inherited from SPL 2.0)
    # ----------------------------------------------------------------
    TEXT    = "TEXT"     # str — prompt text, LLM output, identifiers
    NUMBER  = "NUMBER"   # int|float — v2.0 compat alias (kept forever)
    BOOL    = "BOOL"     # bool — TRUE / FALSE literals

    # ----------------------------------------------------------------
    # Scalar types (new in SPL 3.0)
    # ----------------------------------------------------------------
    INT     = "INT"      # int — integer; loop counters, token counts
    FLOAT   = "FLOAT"    # float — scores, ratios, temperatures
    NONE    = "NONE"     # None — explicit null / unset value

    # ----------------------------------------------------------------
    # Collection types
    # ----------------------------------------------------------------
    LIST    = "LIST"     # list  — ordered, allows duplicates [a, b, c]
    SET     = "SET"      # set   — unordered, unique {a, b, c}
    MAP     = "MAP"      # dict  — key/value {'k': v}

    # ----------------------------------------------------------------
    # Multimodal types (new in SPL 3.0 — for Liquid AI LFM adapter)
    # ----------------------------------------------------------------
    IMAGE   = "IMAGE"    # image — file path or base64-encoded bytes
    AUDIO   = "AUDIO"    # audio — file path or base64-encoded bytes
    VIDEO   = "VIDEO"    # video — file path or base64-encoded bytes

    # ----------------------------------------------------------------
    # Compound / special types (inherited from SPL 2.0)
    # ----------------------------------------------------------------
    STORAGE = "STORAGE"  # StorageConnection — STORAGE(sqlite, 'path')

    # ----------------------------------------------------------------
    # Structured record type (planned SPL 3.1 — not yet implemented)
    # ----------------------------------------------------------------
    DATACLASS = "DATACLASS"  # typed named-field struct via CREATE TYPE

    # ------------------------------------------------------------------
    # Aliases: accept common alternate spellings
    # ------------------------------------------------------------------
    #   BOOLEAN → BOOL   (USER-GUIDE uses BOOLEAN; design doc uses BOOL)
    #   NULL    → NONE   (SQL convention)
    #   INTEGER → INT    (SQL/Python convention)
    #   STR     → TEXT   (Python convention)
    #   DICT    → MAP    (Python convention)
    # These are handled in from_str() below, not as enum members.

    @classmethod
    def from_str(cls, s: str) -> "SPL3Type":
        """Normalize a raw type annotation string to an SPL3Type.

        Accepts both v2.0 spelling and v3.0 aliases.

        >>> SPL3Type.from_str("BOOLEAN")
        <SPL3Type.BOOL: 'BOOL'>
        >>> SPL3Type.from_str("null")
        <SPL3Type.NONE: 'NONE'>
        """
        normalized = s.upper().strip()
        _aliases: dict[str, str] = {
            "BOOLEAN": "BOOL",
            "NULL":    "NONE",
            "INTEGER": "INT",
            "STR":     "TEXT",
            "STRING":  "TEXT",
            "DICT":    "MAP",
            "STRUCT":  "DATACLASS",
        }
        canonical = _aliases.get(normalized, normalized)
        try:
            return cls(canonical)
        except ValueError:
            raise ValueError(
                f"Unknown SPL type {s!r}. "
                f"Valid types: {[t.value for t in cls]}"
            )

    @property
    def is_multimodal(self) -> bool:
        """True for IMAGE, AUDIO, VIDEO — requires multimodal LLM adapter."""
        return self in (SPL3Type.IMAGE, SPL3Type.AUDIO, SPL3Type.VIDEO)

    @property
    def is_collection(self) -> bool:
        """True for LIST, SET, MAP."""
        return self in (SPL3Type.LIST, SPL3Type.SET, SPL3Type.MAP)

    @property
    def is_numeric(self) -> bool:
        """True for INT, FLOAT, NUMBER."""
        return self in (SPL3Type.INT, SPL3Type.FLOAT, SPL3Type.NUMBER)

    @property
    def python_equivalent(self) -> str:
        """Python type annotation string for documentation purposes."""
        _map = {
            SPL3Type.TEXT:      "str",
            SPL3Type.NUMBER:    "int | float",
            SPL3Type.BOOL:      "bool",
            SPL3Type.INT:       "int",
            SPL3Type.FLOAT:     "float",
            SPL3Type.NONE:      "None",
            SPL3Type.LIST:      "list",
            SPL3Type.SET:       "set",
            SPL3Type.MAP:       "dict",
            SPL3Type.IMAGE:     "bytes | str",
            SPL3Type.AUDIO:     "bytes | str",
            SPL3Type.VIDEO:     "bytes | str",
            SPL3Type.STORAGE:   "StorageConnection",
            SPL3Type.DATACLASS: "dataclass",
        }
        return _map[self]


# ----------------------------------------------------------------
# Runtime coercion helpers
# ----------------------------------------------------------------

def coerce_to_int(value: str) -> int:
    """Coerce a string value to Python int (for INT-typed params)."""
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            raise ValueError(f"Cannot coerce {value!r} to INT")


def coerce_to_float(value: str) -> float:
    """Coerce a string value to Python float (for FLOAT-typed params)."""
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot coerce {value!r} to FLOAT")


def is_none_value(value: str) -> bool:
    """Return True if the string value represents a NONE/null.

    SPL stores all variables as strings; NONE serializes to the empty
    string ''.  This helper centralizes that convention so callers don't
    need to know the internal representation.
    """
    return value == "" or value.lower() in ("none", "null")


# ----------------------------------------------------------------
# Token keywords for the SPL 3.0 lexer extension
# ----------------------------------------------------------------

#: New keyword → token mapping to add on top of SPL 2.0 KEYWORDS dict.
#: Keys are lowercase (lexer normalizes input before lookup).
SPL3_TYPE_KEYWORDS: dict[str, str] = {
    # NONE / NULL
    "none": "NONE",
    "null": "NONE",    # SQL-style alias

    # Multimodal
    "image": "IMAGE",
    "audio": "AUDIO",
    "video": "VIDEO",

    # IMPORT and PARALLEL are the two new SPL 3.0 syntax keywords
    # (already in grammar-additions.ebnf); listed here for completeness.
    "import":   "IMPORT",
    "parallel": "PARALLEL",
}

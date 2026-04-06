"""SQLite persistence layer for the text2SPL knowledge base.

Two tables:
  scripts    — every generated SPL script with compiler settings and a
               (name, version) logical key that supports iterative refinement
  executions — every run of a script with inputs (YAML), output, and runtime
               settings

input_params is stored as YAML (not JSON) because:
- YAML handles long multi-line text cleanly with literal block scalars (|)
- YAML is human-readable in raw DB inspection or exported files
- YAML avoids JSON's nested-quote escaping issues

The (name, version) pair is the natural unique key:
- Same name → auto-incremented version each time you regenerate
- Lets you track how a script evolves as you refine its description
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

DB_PATH = Path(__file__).parent / "data" / "knowledge.db"

# New-installation DDL — columns include name + version.
# The unique index is created in _migrate() so it works for both
# fresh installs and upgrades from the old (no-name) schema.
DDL = """
CREATE TABLE IF NOT EXISTS scripts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL DEFAULT '',
    version          INTEGER NOT NULL DEFAULT 1,
    description      TEXT    NOT NULL,
    mode             TEXT    NOT NULL,
    spl_code         TEXT    NOT NULL,
    spl_file         TEXT,
    compiler_adapter TEXT,
    compiler_model   TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS executions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id    INTEGER NOT NULL REFERENCES scripts(id),
    input_params TEXT,
    output       TEXT,
    return_code  INTEGER,
    run_adapter  TEXT,
    run_model    TEXT,
    latency_ms   INTEGER,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def encode_params(params: dict[str, str]) -> str:
    """Encode a params dict as a YAML literal block string."""
    return yaml.dump(params, allow_unicode=True, default_flow_style=False)


def decode_params(raw: str | None) -> dict[str, str]:
    """Decode a YAML params string back to a dict."""
    if not raw:
        return {}
    result = yaml.safe_load(raw)
    return result if isinstance(result, dict) else {}


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply schema upgrades for databases created before name/version existed."""
    # Add columns if missing
    for col_sql in [
        "ALTER TABLE scripts ADD COLUMN name    TEXT    NOT NULL DEFAULT ''",
        "ALTER TABLE scripts ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
    ]:
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Give unique names to any rows left with an empty name (old data)
    old_rows = conn.execute(
        "SELECT id FROM scripts WHERE name = ''"
    ).fetchall()
    for row in old_rows:
        conn.execute(
            "UPDATE scripts SET name = ? WHERE id = ?",
            (f"script_{row['id']}", row["id"]),
        )

    # Safe to add the unique index now that all names are non-empty
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_name_version "
        "ON scripts(name, version)"
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def init_db() -> None:
    conn = _conn()
    conn.executescript(DDL)   # executescript auto-commits
    _migrate(conn)
    conn.commit()
    conn.close()


def current_version(name: str) -> int | None:
    """Return the current max version for the given name, or None if it doesn't exist."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT MAX(version) FROM scripts WHERE name = ?", (name,)
        ).fetchone()
        return row[0]  # None when no rows exist


def next_version(name: str) -> int:
    """Return the next version number for the given script name."""
    v = current_version(name)
    return 1 if v is None else v + 1


def save_script(
    name: str,
    description: str,
    mode: str,
    spl_code: str,
    spl_file: str | None,
    compiler_adapter: str | None,
    compiler_model: str | None,
    overwrite: bool = False,
) -> int:
    """Save a script and return its row id.

    overwrite=False (default): auto-increment version (new row).
    overwrite=True: update the latest existing version in-place;
                    if no version exists yet, inserts v1.
    """
    with _conn() as conn:
        if overwrite:
            existing = conn.execute(
                "SELECT id, version FROM scripts WHERE name = ? ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE scripts SET description=?, mode=?, spl_code=?, spl_file=?, "
                    "compiler_adapter=?, compiler_model=?, created_at=datetime('now') "
                    "WHERE id=?",
                    (description, mode, spl_code, spl_file,
                     compiler_adapter, compiler_model, existing["id"]),
                )
                return existing["id"]

        # Default path: insert as a new version
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM scripts WHERE name = ?", (name,)
        ).fetchone()[0] + 1
        cur = conn.execute(
            "INSERT INTO scripts "
            "(name, version, description, mode, spl_code, spl_file, compiler_adapter, compiler_model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, version, description, mode, spl_code, spl_file, compiler_adapter, compiler_model),
        )
        return cur.lastrowid  # type: ignore[return-value]


def save_execution(
    script_id: int,
    input_params: dict[str, str],
    output: str | None,
    return_code: int,
    run_adapter: str | None,
    run_model: str | None,
    latency_ms: int,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO executions "
            "(script_id, input_params, output, return_code, run_adapter, run_model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                script_id,
                encode_params(input_params),
                output,
                return_code,
                run_adapter,
                run_model,
                latency_ms,
            ),
        )


def get_scripts() -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM scripts ORDER BY name, version"
        ).fetchall()


def get_script(script_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()


def get_executions(script_id: int) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM executions WHERE script_id = ? ORDER BY created_at DESC",
            (script_id,),
        ).fetchall()


def get_all_executions() -> list[sqlite3.Row]:
    """All executions joined with script name/version (for aggregate views)."""
    with _conn() as conn:
        return conn.execute(
            """
            SELECT e.*, s.name, s.version, s.description, s.mode
            FROM executions e
            JOIN scripts s ON s.id = e.script_id
            ORDER BY e.created_at DESC
            """
        ).fetchall()


# ── Import / Export ────────────────────────────────────────────────────────────

def export_knowledge() -> str:
    """Serialise the full knowledge base to a YAML string.

    Format::

        scripts:
          - name: summarize_doc
            version: 1
            description: ...
            mode: prompt
            spl_code: |
              PROMPT ...
            compiler_adapter: claude_cli
            compiler_model: null
            created_at: "2026-03-23 10:00:00"
            executions:
              - input_params:
                  document: |
                    Long document text here...
                output: "The summary."
                return_code: 0
                run_adapter: ollama
                run_model: gemma3
                latency_ms: 1234
                created_at: "2026-03-23 10:01:00"
    """
    scripts = get_scripts()
    records = []
    for s in scripts:
        execs = get_executions(s["id"])
        exec_records = [
            {
                "input_params": decode_params(e["input_params"]),
                "output": e["output"],
                "return_code": e["return_code"],
                "run_adapter": e["run_adapter"],
                "run_model": e["run_model"],
                "latency_ms": e["latency_ms"],
                "created_at": e["created_at"],
            }
            for e in execs
        ]
        records.append(
            {
                "name": s["name"],
                "version": s["version"],
                "description": s["description"],
                "mode": s["mode"],
                "spl_code": s["spl_code"],
                "spl_file": s["spl_file"],
                "compiler_adapter": s["compiler_adapter"],
                "compiler_model": s["compiler_model"],
                "created_at": s["created_at"],
                "executions": exec_records,
            }
        )
    header = (
        f"# text2SPL Knowledge Base Export\n"
        f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"# Format: https://github.com/digital-duck/SPL20\n\n"
    )
    return header + yaml.dump(
        {"scripts": records},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def import_knowledge(yaml_str: str) -> tuple[int, int]:
    """Import a YAML knowledge base export, skipping duplicate (name, version) pairs.

    Returns (scripts_added, executions_added).
    """
    data = yaml.safe_load(yaml_str)
    scripts_added = 0
    executions_added = 0

    conn = _conn()
    try:
        for s in data.get("scripts", []):
            cur = conn.execute(
                "INSERT OR IGNORE INTO scripts "
                "(name, version, description, mode, spl_code, spl_file, "
                " compiler_adapter, compiler_model, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s["name"], s["version"], s["description"], s["mode"],
                    s["spl_code"], s.get("spl_file"),
                    s.get("compiler_adapter"), s.get("compiler_model"),
                    s.get("created_at"),
                ),
            )
            if cur.rowcount == 0:
                continue  # duplicate — skip its executions too
            script_id = cur.lastrowid
            scripts_added += 1
            for e in s.get("executions", []):
                conn.execute(
                    "INSERT INTO executions "
                    "(script_id, input_params, output, return_code, "
                    " run_adapter, run_model, latency_ms, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        script_id,
                        encode_params(e.get("input_params") or {}),
                        e.get("output"),
                        e.get("return_code"),
                        e.get("run_adapter"),
                        e.get("run_model"),
                        e.get("latency_ms"),
                        e.get("created_at"),
                    ),
                )
                executions_added += 1
        conn.commit()
    finally:
        conn.close()

    return scripts_added, executions_added

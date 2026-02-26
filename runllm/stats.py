from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from runllm.models import UsageMetrics


SCHEMA_VERSION = 1


def _default_db_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    root = base / "runllm"
    root.mkdir(parents=True, exist_ok=True)
    return root / "stats.db"


class StatsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_path TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    output_schema_ok INTEGER NOT NULL,
                    input_schema_ok INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def record_run(
        self,
        *,
        app_path: str,
        app_name: str,
        model: str,
        success: bool,
        output_schema_ok: bool,
        input_schema_ok: bool,
        usage: UsageMetrics,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(app_path, app_name, model, success, output_schema_ok, input_schema_ok, latency_ms, prompt_tokens, completion_tokens, total_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app_path,
                    app_name,
                    model,
                    int(success),
                    int(output_schema_ok),
                    int(input_schema_ok),
                    usage.latency_ms,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                ),
            )

    def aggregate(self, *, app_path: str, model: str | None = None) -> dict[str, float | int | str | None]:
        where = "WHERE app_path = ?"
        params: list[object] = [app_path]
        if model:
            where += " AND model = ?"
            params.append(model)
        query = f"""
            SELECT
                COUNT(*) as total_runs,
                SUM(success) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count,
                AVG(output_schema_ok) * 100.0 as output_schema_compliance_pct,
                AVG(input_schema_ok) * 100.0 as input_schema_compliance_pct,
                AVG(latency_ms) as avg_latency_ms,
                AVG(prompt_tokens) as avg_prompt_tokens,
                AVG(completion_tokens) as avg_completion_tokens,
                MAX(completion_tokens) as max_completion_tokens,
                AVG(CASE WHEN total_tokens > 0 THEN (latency_ms / total_tokens) * 1000 ELSE NULL END) as ms_per_1k_tokens
            FROM runs
            {where}
        """
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        if row is None or row[0] == 0:
            return {
                "app_path": app_path,
                "model": model,
                "total_runs": 0,
            }
        return {
            "app_path": app_path,
            "model": model,
            "total_runs": int(row[0] or 0),
            "success_count": int(row[1] or 0),
            "failure_count": int(row[2] or 0),
            "output_schema_compliance_pct": float(row[3] or 0.0),
            "input_schema_compliance_pct": float(row[4] or 0.0),
            "avg_latency_ms": float(row[5] or 0.0),
            "avg_prompt_tokens": float(row[6] or 0.0),
            "avg_completion_tokens": float(row[7] or 0.0),
            "max_completion_tokens": int(row[8] or 0),
            "ms_per_1k_tokens": float(row[9] or 0.0),
        }

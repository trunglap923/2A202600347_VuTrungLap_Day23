"""Checkpointer adapter."""

from __future__ import annotations

from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:  # noqa: ANN401
    """Return a LangGraph checkpointer."""
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    if kind == "sqlite":
        import sqlite3
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            msg = "SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite"
            raise RuntimeError(msg) from exc
        
        # In langgraph-checkpoint-sqlite 3.x, we pass a connection
        # Using check_same_thread=False for broader compatibility in local dev
        conn = sqlite3.connect(database_url or "checkpoints.db", check_same_thread=False)
        return SqliteSaver(conn=conn)
    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            msg = "Postgres checkpointer requires: pip install langgraph-checkpoint-postgres"
            raise RuntimeError(msg) from exc
        return PostgresSaver.from_conn_string(database_url or "")
    raise ValueError(f"Unknown checkpointer kind: {kind}")

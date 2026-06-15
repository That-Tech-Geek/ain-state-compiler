"""
Checkpoint Engine
=================
Persistent cursor store for incremental ingest.

Saves the last-fetched position for each source+key pair so that:
  - Subsequent runs fetch ONLY new data (incremental mode)
  - Crashed/interrupted runs can resume from where they stopped
  - Full-history mode bypasses checkpoints entirely

Storage: JSON file at {project_dir}/checkpoints.json
         Also mirrored to SQLite sync_checkpoints table (if DB initialized).

Usage:
    cp = Checkpoint(project_dir)

    # Save cursor after each page
    cp.save("slack", "channel-C01234", "1685000000.000000")

    # Load on resume -- returns None if no checkpoint exists
    ts = cp.load("slack", "channel-C01234")

    # Wipe everything for a --full-history run
    cp.clear_all()

    # Wipe single source
    cp.clear("slack")
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional


CHECKPOINT_FILE = "checkpoints.json"


class Checkpoint:
    """
    Manages read/write of ingest cursors.

    Thread-safe: each write flushes to disk immediately (atomic rename).
    """

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self._path = os.path.join(project_dir, CHECKPOINT_FILE)
        self._data: dict = self._load_file()

    # ──────────────────────────────────────────────────────────
    # Core API
    # ──────────────────────────────────────────────────────────

    def load(self, source: str, key: str) -> Optional[str]:
        """
        Returns the stored cursor for (source, key), or None if not found.

        Args:
            source: "slack" | "jira" | "gmail"
            key:    channel_id, issue_key, mailbox name, etc.
        """
        return self._data.get(source, {}).get(key, {}).get("cursor")

    def save(self, source: str, key: str, cursor: str) -> None:
        """
        Saves a cursor for (source, key).

        Args:
            source: "slack" | "jira" | "gmail"
            key:    channel_id, issue_key, mailbox name, etc.
            cursor: Opaque string (Slack next_cursor, Jira startAt, Gmail UID, etc.)
        """
        if source not in self._data:
            self._data[source] = {}
        self._data[source][key] = {
            "cursor": cursor,
            "fetched_at": datetime.utcnow().isoformat(),
        }
        self._flush()

    def clear(self, source: str) -> None:
        """Removes all checkpoints for a specific source."""
        if source in self._data:
            del self._data[source]
            self._flush()
            print(f"[*] Checkpoint cleared for source: {source}")

    def clear_all(self) -> None:
        """Wipes ALL checkpoints. Use for --full-history mode."""
        self._data = {}
        self._flush()
        print("[*] All checkpoints cleared. Next ingest will fetch full history.")

    def get_summary(self) -> dict:
        """Returns a human-readable summary of all stored checkpoints."""
        summary = {}
        for source, keys in self._data.items():
            summary[source] = {
                k: v.get("fetched_at", "unknown") for k, v in keys.items()
            }
        return summary

    def has_any(self, source: str) -> bool:
        """Returns True if any checkpoint exists for this source."""
        return bool(self._data.get(source))

    # ──────────────────────────────────────────────────────────
    # SQLite Mirror (for Supabase-compatible cloud sync)
    # ──────────────────────────────────────────────────────────

    def sync_to_db(self, db_path: str) -> None:
        """
        Mirrors all checkpoints into the sync_checkpoints SQLite table.
        Called at end of ingest run so Supabase can also see cursor state.
        """
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_checkpoints (
                    source      TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    cursor      TEXT NOT NULL,
                    fetched_at  TEXT NOT NULL,
                    PRIMARY KEY (source, key)
                )
            """)
            for source, keys in self._data.items():
                for key, meta in keys.items():
                    conn.execute(
                        """INSERT OR REPLACE INTO sync_checkpoints
                           (source, key, cursor, fetched_at) VALUES (?, ?, ?, ?)""",
                        (source, key, meta.get("cursor", ""), meta.get("fetched_at", "")),
                    )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[!] Checkpoint DB sync error: {e}")

    def load_from_db(self, db_path: str) -> None:
        """
        Loads checkpoints from the SQLite table (used when JSON file is missing
        but the DB exists, e.g. after a pip reinstall).
        """
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute("SELECT source, key, cursor, fetched_at FROM sync_checkpoints").fetchall()
            conn.close()
            for source, key, cursor, fetched_at in rows:
                if source not in self._data:
                    self._data[source] = {}
                # Only restore if no JSON checkpoint already exists
                if key not in self._data[source]:
                    self._data[source][key] = {"cursor": cursor, "fetched_at": fetched_at}
        except Exception:
            pass  # table may not exist yet

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────

    def _load_file(self) -> dict:
        """Loads checkpoints.json from disk. Returns empty dict if missing."""
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _flush(self) -> None:
        """Atomically writes checkpoint data to disk."""
        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception as e:
            print(f"[!] Checkpoint flush error: {e}")

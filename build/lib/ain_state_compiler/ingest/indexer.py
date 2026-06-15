"""
Fast Context Indexer
Stores ALL ingested events in a SQLite database with:
  - FTS5 full-text search (SQLite built-in, zero deps)
  - Deterministic UUID per event (source + native ID = no duplicates)
  - Inverted tag/keyword index for O(1) topic lookup
  - JSON snapshot per event for lossless retrieval
  - Process tracking table (ingestion runs, status, stats)

Design goals:
  - Zero context loss: every field stored raw in JSON, FTS indexes all text
  - ASAP retrieval: FTS5 BM25 ranking + inverted index = sub-ms queries
  - Idempotent: re-running ingest won't duplicate records (INSERT OR IGNORE)
  - Offline: pure SQLite, no external search engine

Schema:
  events(id, source, native_id, channel, author, timestamp, subject, body, raw_json, ingested_at)
  events_fts(content=events) -- FTS5 virtual table
  tag_index(tag, event_id) -- inverted keyword index
  ingest_runs(id, started_at, finished_at, source, records_added, status, notes)
"""

import os
import sqlite3
import json
import hashlib
import re
from datetime import datetime


FTS_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "was", "are", "be", "by", "from", "that", "this",
    "it", "as", "not", "we", "they", "he", "she", "i", "you", "have",
    "has", "had", "will", "would", "can", "could", "should", "all", "also",
}


def _make_event_id(source, native_id):
    """Deterministic UUID-like ID: sha1(source:native_id)[:16]"""
    raw = f"{source}:{native_id}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _extract_keywords(text, max_kw=30):
    """
    Extracts top keywords from text for the inverted index.
    Simple frequency-based approach -- no external NLP needed.
    """
    words = re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower())
    freq = {}
    for w in words:
        if w not in FTS_STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    # Sort by frequency descending, take top N
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:max_kw]]


class ContextIndexer:
    """
    Fast context indexer backed by SQLite FTS5.

    Usage:
        idx = ContextIndexer("/path/to/project")
        idx.init_db()
        run_id = idx.start_run("slack")
        idx.index_batch(records, run_id)
        idx.finish_run(run_id, records_added=n)

    Query:
        results = idx.search("analytics v2 deployment", limit=10)
        results = idx.search_by_tag("analytics_v2", limit=20)
    """

    def __init__(self, project_dir):
        self.db_path = os.path.join(project_dir, "context_index.db")
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-65536")  # 64MB cache
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_db(self):
        """Create schema if not exists. Idempotent."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id          TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                native_id   TEXT NOT NULL,
                channel     TEXT DEFAULT '',
                author      TEXT DEFAULT '',
                timestamp   TEXT DEFAULT '',
                subject     TEXT DEFAULT '',
                body        TEXT DEFAULT '',
                raw_json    TEXT NOT NULL,
                ingested_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_events_native
                ON events (source, native_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts
                USING fts5(
                    id UNINDEXED,
                    source,
                    channel,
                    author,
                    subject,
                    body,
                    content='events',
                    content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 1'
                );

            CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
                INSERT INTO events_fts(rowid, id, source, channel, author, subject, body)
                VALUES (new.rowid, new.id, new.source, new.channel, new.author, new.subject, new.body);
            END;

            CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
                INSERT INTO events_fts(events_fts, rowid, id, source, channel, author, subject, body)
                VALUES ('delete', old.rowid, old.id, old.source, old.channel, old.author, old.subject, old.body);
            END;

            CREATE TABLE IF NOT EXISTS tag_index (
                tag         TEXT NOT NULL,
                event_id    TEXT NOT NULL,
                PRIMARY KEY (tag, event_id)
            );

            CREATE INDEX IF NOT EXISTS idx_tag ON tag_index (tag);

            CREATE TABLE IF NOT EXISTS ingest_runs (
                id              TEXT PRIMARY KEY,
                started_at      TEXT NOT NULL,
                finished_at     TEXT DEFAULT '',
                source          TEXT NOT NULL,
                records_added   INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'RUNNING',
                notes           TEXT DEFAULT ''
            );
        """)
        conn.commit()
        print(f"[+] Context index initialized: {self.db_path}")

    def start_run(self, source):
        """Records the start of an ingestion run. Returns run_id."""
        run_id = _make_event_id("run", f"{source}_{datetime.utcnow().isoformat()}")
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO ingest_runs (id, started_at, source, status) VALUES (?, ?, ?, 'RUNNING')",
            (run_id, datetime.utcnow().isoformat(), source),
        )
        conn.commit()
        return run_id

    def finish_run(self, run_id, records_added=0, status="COMPLETE", notes=""):
        """Marks an ingestion run as finished."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE ingest_runs SET finished_at=?, records_added=?, status=?, notes=? WHERE id=?",
            (datetime.utcnow().isoformat(), records_added, status, notes, run_id),
        )
        conn.commit()

    def index_batch(self, records, run_id=None):
        """
        Indexes a batch of event records.

        Each record must be a dict with at minimum:
            id (str), source (str)

        Additional recognized fields (all optional):
            native_id, channel, author, timestamp, subject, body

        Returns: (inserted, skipped) counts.
        """
        conn = self._get_conn()
        inserted = 0
        skipped = 0

        for rec in records:
            source = rec.get("source", "unknown")
            native_id = str(rec.get("id") or rec.get("native_id") or rec.get("ts") or "")
            event_id = _make_event_id(source, native_id)

            channel = str(rec.get("_channel_name") or rec.get("channel") or rec.get("project") or "")
            author = str(
                rec.get("author") or rec.get("user") or rec.get("sender") or
                rec.get("assignee") or rec.get("reporter") or ""
            )
            timestamp = str(rec.get("ts") or rec.get("created") or rec.get("date") or rec.get("ingested_at") or "")
            subject = str(rec.get("subject") or rec.get("title") or rec.get("summary") or "")
            body = str(rec.get("body") or rec.get("text") or rec.get("description") or rec.get("comments") or "")

            raw_json = json.dumps(rec, ensure_ascii=False, default=str)
            ingested_at = rec.get("_ingested_at") or rec.get("ingested_at") or datetime.utcnow().isoformat()

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO events
                       (id, source, native_id, channel, author, timestamp, subject, body, raw_json, ingested_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, source, native_id, channel, author, timestamp, subject, body, raw_json, ingested_at),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    inserted += 1
                    # Index keywords
                    combined_text = f"{subject} {body} {channel} {author}"
                    keywords = _extract_keywords(combined_text)
                    for kw in keywords:
                        conn.execute(
                            "INSERT OR IGNORE INTO tag_index (tag, event_id) VALUES (?, ?)",
                            (kw, event_id),
                        )
                else:
                    skipped += 1
            except Exception as e:
                print(f"[!] Indexer error on record {native_id}: {e}")

        conn.commit()
        return inserted, skipped

    def search(self, query_text, limit=20, source=None):
        """
        Full-text search using FTS5 BM25 ranking.
        Returns list of matching event dicts, ranked by relevance.
        """
        conn = self._get_conn()

        # Sanitize query for FTS5: wrap in quotes if multi-word
        safe_query = query_text.replace('"', '""')
        terms = safe_query.split()
        if len(terms) > 1:
            fts_query = " OR ".join(f'"{t}"' for t in terms if t)
        else:
            fts_query = safe_query

        try:
            if source:
                rows = conn.execute(
                    """SELECT e.id, e.source, e.channel, e.author, e.timestamp,
                              e.subject, e.body, e.raw_json,
                              bm25(events_fts) as score
                       FROM events_fts
                       JOIN events e ON e.id = events_fts.id
                       WHERE events_fts MATCH ? AND e.source = ?
                       ORDER BY score
                       LIMIT ?""",
                    (fts_query, source, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT e.id, e.source, e.channel, e.author, e.timestamp,
                              e.subject, e.body, e.raw_json,
                              bm25(events_fts) as score
                       FROM events_fts
                       JOIN events e ON e.id = events_fts.id
                       WHERE events_fts MATCH ?
                       ORDER BY score
                       LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError as e:
            print(f"[!] FTS search error: {e}. Query: {fts_query}")
            return []

    def search_by_tag(self, tag, limit=20):
        """
        Tag-based retrieval using the inverted keyword index.
        O(1) lookup. Returns matching events.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT e.id, e.source, e.channel, e.author, e.timestamp, e.subject, e.body
               FROM tag_index t
               JOIN events e ON e.id = t.event_id
               WHERE t.tag = ?
               ORDER BY e.timestamp DESC
               LIMIT ?""",
            (tag.lower(), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self):
        """Returns indexing statistics."""
        conn = self._get_conn()
        stats = {}
        stats["total_events"] = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        stats["total_tags"] = conn.execute("SELECT COUNT(DISTINCT tag) FROM tag_index").fetchone()[0]
        stats["by_source"] = {}
        for row in conn.execute("SELECT source, COUNT(*) as n FROM events GROUP BY source").fetchall():
            stats["by_source"][row["source"]] = row["n"]
        runs = conn.execute(
            "SELECT * FROM ingest_runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()
        stats["recent_runs"] = [dict(r) for r in runs]
        return stats

    def get_event_by_id(self, event_id):
        """Retrieve full raw event by ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if row:
            return dict(row)
        return None

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

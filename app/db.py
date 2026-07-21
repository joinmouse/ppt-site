"""SQLite storage with WAL and a write lock."""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from . import config

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db() -> None:
    import os
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS hashes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          hash TEXT UNIQUE NOT NULL,
          used INTEGER DEFAULT 0,
          used_at TEXT,
          job_id TEXT,
          note TEXT,
          created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY,
          hash TEXT NOT NULL,
          description TEXT NOT NULL,
          pages TEXT,
          style TEXT NOT NULL,
          files TEXT,
          status TEXT DEFAULT 'queued',
          result_url TEXT,
          error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL)""")


def create_hashes(count: int, note: str) -> list[str]:
    out = []
    with _lock, _conn() as c:
        for _ in range(count):
            h = uuid.uuid4().hex
            c.execute("INSERT INTO hashes(hash, note, created_at) VALUES(?,?,?)",
                      (h, note, _now()))
            out.append(h)
    return out


def check_hash(h: str) -> dict:
    with _lock, _conn() as c:
        row = c.execute("SELECT used FROM hashes WHERE hash=?", (h,)).fetchone()
    if row is None:
        return {"valid": False, "reason": "not_found"}
    if row["used"]:
        return {"valid": False, "reason": "used"}
    return {"valid": True}


def consume_hash(h: str, job_id: str) -> bool:
    """Atomically mark hash used. Returns False if already consumed."""
    with _lock, _conn() as c:
        cur = c.execute(
            "UPDATE hashes SET used=1, used_at=?, job_id=? WHERE hash=? AND used=0",
            (_now(), job_id, h))
        return cur.rowcount == 1


def create_job(job_id: str, h: str, description: str, pages: str, style: str, files: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO jobs(id, hash, description, pages, style, files, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (job_id, h, description, pages, style, files, _now(), _now()))


def get_job(job_id: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def next_queued_job() -> dict | None:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
    return dict(row) if row else None


def queue_position(job_id: str) -> int:
    with _lock, _conn() as c:
        job = c.execute("SELECT created_at, status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job or job["status"] != "queued":
            return 0
        n = c.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status='queued' AND created_at < ?",
            (job["created_at"],)).fetchone()
    return n["n"]


def update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))


def list_hashes(filter_: str = "all") -> dict:
    q = "SELECT * FROM hashes"
    if filter_ == "used":
        q += " WHERE used=1"
    elif filter_ == "unused":
        q += " WHERE used=0"
    q += " ORDER BY id DESC LIMIT 1000"
    with _lock, _conn() as c:
        items = [dict(r) for r in c.execute(q).fetchall()]
        stats = c.execute(
            "SELECT COUNT(*) total, COALESCE(SUM(used),0) used FROM hashes").fetchone()
    return {"items": items,
            "stats": {"total": stats["total"], "used": stats["used"],
                      "unused": stats["total"] - stats["used"]}}

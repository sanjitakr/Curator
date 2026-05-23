import sqlite3
import time

import os
DB_PATH = os.path.expanduser("~/.local/share/rss-reader/rss.db")
TWO_WEEKS = 14 * 24 * 3600


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url       TEXT PRIMARY KEY,
                title     TEXT,
                source    TEXT,
                tag       TEXT,
                timestamp REAL,
                summary   TEXT,
                status    TEXT DEFAULT 'unread'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS deleted_urls (
                url TEXT PRIMARY KEY
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                url     TEXT PRIMARY KEY,
                name    TEXT,
                tag     TEXT,
                type    TEXT DEFAULT 'rss',
                enabled INTEGER DEFAULT 1
            )
        """)


# ── feeds ──────────────────────────────────────────────────────────────────

def add_feed(url: str, tag: str, name: str = "", feed_type: str = "rss"):
    init_db()
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO feeds (url, name, tag, type, enabled) VALUES (?,?,?,?,1)",
            (url, name or url, tag, feed_type),
        )


def remove_feed(url: str):
    """Remove a feed and all its articles from the database."""
    init_db()
    with conn() as c:
        # find the feed name/source to delete matching articles
        row = c.execute("SELECT name FROM feeds WHERE url=?", (url,)).fetchone()
        if row:
            c.execute("DELETE FROM articles WHERE source=?", (row["name"],))
        c.execute("DELETE FROM feeds WHERE url=?", (url,))


def get_feeds():
    init_db()
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM feeds ORDER BY tag, name").fetchall()]


def get_categories():
    init_db()
    with conn() as c:
        rows = c.execute("SELECT DISTINCT tag FROM feeds ORDER BY tag").fetchall()
        return [r["tag"] for r in rows]


# ── articles ───────────────────────────────────────────────────────────────

def save_articles(items):
    init_db()
    cutoff = time.time() - TWO_WEEKS
    with conn() as c:
        blocked = {r["url"] for r in c.execute("SELECT url FROM deleted_urls").fetchall()}
        saved = 0
        for item in items:
            if item.url in blocked or item.timestamp < cutoff:
                continue
            c.execute(
                """INSERT OR IGNORE INTO articles
                   (url, title, source, tag, timestamp, summary, status)
                   VALUES (?,?,?,?,?,?,'unread')""",
                (item.url, item.title, item.source, item.tag, item.timestamp, item.summary),
            )
            result = c.execute("SELECT changes()").fetchone()[0]; saved += result
    return saved


def purge_old():
    """Delete articles older than 2 weeks."""
    init_db()
    cutoff = time.time() - TWO_WEEKS
    with conn() as c:
        cur = c.execute("DELETE FROM articles WHERE timestamp < ?", (cutoff,))
        return cur.rowcount


def get_latest(tag: str = None):
    init_db()
    with conn() as c:
        if tag:
            rows = c.execute(
                "SELECT * FROM articles WHERE status='unread' AND tag=? ORDER BY timestamp DESC",
                (tag,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM articles WHERE status='unread' ORDER BY timestamp DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def mark_viewed(url: str):
    init_db()
    with conn() as c:
        c.execute("DELETE FROM articles WHERE url=?", (url,))
        c.execute("INSERT OR IGNORE INTO deleted_urls (url) VALUES (?)", (url,))


def search_articles(keyword: str):
    init_db()
    kw = f"%{keyword}%"
    with conn() as c:
        rows = c.execute(
            """SELECT title, url, tag FROM articles
               WHERE title LIKE ? OR summary LIKE ? OR tag LIKE ?
               ORDER BY timestamp DESC""",
            (kw, kw, kw),
        ).fetchall()
        return [dict(r) for r in rows]
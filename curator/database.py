import os
import sqlite3
import time

def _db_path() -> str:
    if os.name=="nt":# Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "curator", "curator.db")
    
    if os.uname().sysname == "Darwin":
        return os.path.expanduser("~/Library/Application Support/curator/curator.db")
    
    return os.path.expanduser("~/.local/share/curator/curator.db")  # Linux

DB_PATH=_db_path()
TWO_WEEKS =14*24*3600

def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c=sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                url     TEXT PRIMARY KEY,
                name    TEXT,
                tag     TEXT,
                type    TEXT    DEFAULT 'rss',
                enabled INTEGER DEFAULT 1
            )
        """)
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
            CREATE TABLE IF NOT EXISTS dismissed (
                url TEXT PRIMARY KEY
            )
        """)


def add_feed(url: str, tag: str, name: str = "", feed_type: str = "rss"):
    init_db()
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO feeds (url, name, tag, type, enabled) VALUES (?,?,?,?,1)",(url, name or url, tag.upper(), feed_type),)


def remove_feed(url: str):
    init_db()
    with _conn() as c:
        row = c.execute("SELECT name FROM feeds WHERE url=?", (url,)).fetchone()
        if row:
            c.execute("DELETE FROM articles WHERE source=?", (row["name"],))
        c.execute("DELETE FROM feeds WHERE url=?", (url,))


def get_feeds() -> list[dict]:
    init_db()
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM feeds ORDER BY tag, name").fetchall()]


def get_categories() -> list[str]:
    init_db()
    with _conn() as c:
        return [r["tag"] for r in c.execute("SELECT DISTINCT tag FROM feeds ORDER BY tag").fetchall()]



def save_articles(items) -> int:
    init_db()
    cutoff = time.time() - TWO_WEEKS
    with _conn() as c:
        blocked = {r["url"] for r in c.execute("SELECT url FROM dismissed").fetchall()}
        saved   = 0
        for item in items:
            if item.url in blocked or item.timestamp < cutoff:
                continue
            c.execute("""INSERT OR IGNORE INTO articles
                   (url, title, source, tag, timestamp, summary, status)
                   VALUES (?,?,?,?,?,?,'unread')""",(item.url, item.title, item.source,item.tag, item.timestamp, item.summary),
            )
            saved += c.execute("SELECT changes()").fetchone()[0]
    return saved


def purge_old() -> int:
    init_db()
    cutoff = time.time() - TWO_WEEKS
    with _conn() as c:
        cur = c.execute("DELETE FROM articles WHERE timestamp < ?", (cutoff,))
        return cur.rowcount


def get_latest(tag: str = None) -> list[dict]:
    init_db()
    with _conn() as c:
        if tag:
            rows = c.execute(
                "SELECT * FROM articles WHERE status='unread' AND tag=?"
                " ORDER BY timestamp DESC",
                (tag,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM articles WHERE status='unread'"
                " ORDER BY timestamp DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def mark_viewed(url: str):
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM articles WHERE url=?", (url,))
        c.execute("INSERT OR IGNORE INTO dismissed (url) VALUES (?)", (url,))


def search_articles(keyword: str) -> list[dict]:
    init_db()
    kw = f"%{keyword}%"
    with _conn() as c:
        rows = c.execute(
            """SELECT title, url, tag, source, timestamp FROM articles
               WHERE title LIKE ? OR summary LIKE ? OR tag LIKE ? OR source LIKE ?
               ORDER BY timestamp DESC""",
            (kw, kw, kw, kw),
        ).fetchall()
        return [dict(r) for r in rows]

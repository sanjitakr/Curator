from dataclasses import dataclass
import time
import re
import feedparser
from rss_reader import database as db

TWO_WEEKS = 14 * 24 * 3600


@dataclass
class FeedItem:
    title: str
    source: str
    url: str
    timestamp: float
    status: str
    tag: str
    summary: str = ""


def _youtube_url(url: str) -> str:
    if "feeds/videos.xml" in url:
        return url
    if re.match(r"^UC[\w-]{21}$", url):
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={url}"
    m = re.search(r"/channel/(UC[\w-]{21})", url)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    m = re.search(r"[?&]user=([^&]+)", url)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?user={m.group(1)}"
    raise ValueError(f"Cannot derive YouTube RSS from: {url}")


def _spotify_url(url: str) -> str:
    m = re.search(r"spotify\.com/show/([A-Za-z0-9]+)", url)
    if m:
        return f"https://anchor.fm/s/{m.group(1)}/podcast/rss"
    return url  # assume direct RSS


def _resolve(feed: dict) -> str:
    ftype = feed.get("type", "rss").lower()
    url = feed["url"]
    if ftype == "youtube":
        return _youtube_url(url)
    if ftype == "spotify":
        return _spotify_url(url)
    return url


def fetch_all() -> tuple[int, list[str]]:
    """Fetch from all enabled feeds, purge old rows, return (saved, errors)."""
    purged = db.purge_old()
    feeds = db.get_feeds()
    enabled = [f for f in feeds if f.get("enabled", 1)]

    cutoff = time.time() - TWO_WEEKS
    all_items = []
    errors = []

    for feed in enabled:
        try:
            rss_url = _resolve(feed)
            parsed = feedparser.parse(rss_url)
            for entry in parsed.entries:
                pt = entry.get("published_parsed") or entry.get("updated_parsed")
                ts = time.mktime(pt) if pt else time.time()
                if ts < cutoff:
                    continue
                all_items.append(FeedItem(
                    title=entry.get("title", "No Title"),
                    source=feed["name"],
                    url=entry.get("link", ""),
                    timestamp=ts,
                    tag=feed["tag"],
                    status="unread",
                    summary=entry.get("summary", ""),
                ))
        except Exception as e:
            errors.append(f"{feed['name']}: {e}")

    saved = db.save_articles(all_items)
    return saved, errors

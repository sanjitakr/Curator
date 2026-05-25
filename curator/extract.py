import re
import time
from dataclasses import dataclass, field
import feedparser
from curator import database as db
TWO_WEEKS = 14*24*3600

@dataclass
class FeedItem:
    title:     str
    source:    str
    url:       str
    timestamp: float
    tag:       str
    status:    str  = "unread"
    summary:   str  = ""


def _youtube_rss(url: str) -> str:
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
    raise ValueError(
        f"Could not derive a YouTube RSS URL from: {url}\n"
        "Tip: use the channel URL  https://www.youtube.com/channel/UC..."
    )


def _spotify_rss(url: str) -> str:
    m = re.search(r"spotify\.com/show/([A-Za-z0-9]+)", url)
    if m:
        return f"https://anchor.fm/s/{m.group(1)}/podcast/rss"
    return url 


def _resolve_url(feed: dict) -> str:
    ftype = feed.get("type", "rss").lower()
    url   = feed["url"]
    if ftype == "youtube":
        return _youtube_rss(url)
    if ftype == "spotify":
        return _spotify_rss(url)
    return url 

def fetch_all() -> tuple[int, list[str]]:
    db.purge_old()

    feeds   = [f for f in db.get_feeds() if f.get("enabled", 1)]
    cutoff  = time.time() - TWO_WEEKS
    items:  list[FeedItem] = []
    errors: list[str]      = []

    for feed in feeds:
        try:
            rss_url= _resolve_url(feed)
            parsed= feedparser.parse(rss_url)

            for entry in parsed.entries:
                pt= entry.get("published_parsed") or entry.get("updated_parsed")
                ts= time.mktime(pt) if pt else time.time()
                if ts < cutoff:
                    continue
                items.append(FeedItem(
                    title=entry.get("title", "No title"),
                    source=feed["name"],
                    url= entry.get("link", ""),
                    timestamp=ts,
                    tag=feed["tag"],
                    summary=entry.get("summary", ""),
                ))

        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")

    saved=db.save_articles(items)
    return saved, errors

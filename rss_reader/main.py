#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import typer
from rss_reader import database as db
from rss_reader import extract
app = typer.Typer(name="rss", help="Personal RSS reader", add_completion=False)
@app.command("add-feed")
def add_feed(url: str = typer.Argument(..., help="Feed URL"),
    category: str = typer.Argument(..., help="Category / tag"),
    name: str = typer.Argument("", help="Display name (optional, defaults to URL)"),
    feed_type: str = typer.Option("rss", "--type", "-t", help="rss | youtube | spotify | blog"),):
    """Add a new feed."""
    db.add_feed(url=url, tag=category, name=name or url, feed_type=feed_type)
    typer.echo(f"✓ Added feed: {name or url}  [{category}]")

@app.command("remove-feed")
def remove_feed(url: str = typer.Argument(..., help="Feed URL to remove"),):
    """Remove a feed and all its articles."""
    db.remove_feed(url)
    typer.echo(f"✓ Removed feed and its articles: {url}")

@app.command("display-category")
def display_category():
    """List all categories and their feeds."""
    feeds = db.get_feeds()
    if not feeds:
        typer.echo("No feeds configured.")
        raise typer.Exit()
    by_cat: dict[str, list] = {}
    for f in feeds:
        by_cat.setdefault(f["tag"], []).append(f)
    for cat, flist in sorted(by_cat.items()):
        typer.echo(f"\n[{cat}]")
        for f in flist:
            status = "✓" if f["enabled"] else "✗"
            typer.echo(f"  {status} {f['name']}  {f['url']}")


@app.command("latest")
def latest(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """Show latest unread articles."""
    rows = db.get_latest(tag=category)
    if not rows:
        typer.echo("No unread articles.")
        raise typer.Exit()
    for r in rows:
        typer.echo(f"[{r['tag']}] {r['title']}\n  {r['url']}\n")


@app.command("fetch")
def fetch():
    """Fetch new articles from all enabled feeds (past 2 weeks only)."""
    typer.echo("Fetching…")
    saved, errors = extract.fetch_all()
    typer.echo(f"✓ Saved {saved} new article(s).")
    for e in errors:
        typer.echo(f"  ✗ {e}", err=True)


@app.command("mark-viewed")
def mark_viewed(
    url: str = typer.Argument(..., help="Article URL to dismiss permanently"),
):
    """Dismiss an article — it will never reappear."""
    db.mark_viewed(url)
    typer.echo(f"✓ Dismissed: {url}")


@app.command("search")
def search(
    keyword: str = typer.Argument(..., help="Keyword to search for"),
):
    """Search articles by keyword — shows title, URL, category."""
    rows = db.search_articles(keyword)
    if not rows:
        typer.echo(f"No results for '{keyword}'.")
        raise typer.Exit()
    for r in rows:
        typer.echo(f"[{r['tag']}] {r['title']}\n  {r['url']}\n")


@app.command("ui")
def ui():
    """Launch the interactive TUI."""
    from rss_reader.tui import RSSApp
    RSSApp().run()


if __name__ == "__main__":
    app()